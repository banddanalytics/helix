---
name: hmm-garch-regime-detector
description: >
  Implement the hybrid Hidden Markov Model (HMM) and GARCH pipeline for market regime
  detection. This skill is STAGE-AGNOSTIC — it operates on return series from any data
  source (Forex broker bars in Stage A, CME tick-derived bars in Stage B). Covers
  GARCH(1,1) emission probability modeling for conditional heteroskedasticity, Baum-Welch
  algorithm for transition matrix estimation, PDF threshold calibration for regime
  switching, Viterbi decoding for optimal state sequences, and regime classification into
  trending/mean-reverting/volatile states. The regime detector is the master switch for
  the entire alpha generation subsystem. Use this skill whenever working on: regime
  detection, HMM, GARCH, Baum-Welch, emission probability, volatility clustering, state
  transitions, Viterbi, or conditional heteroskedasticity.
---

# HMM-GARCH Regime Detector Skill

## Purpose

This skill defines the market regime detection pipeline using a hybrid HMM with
GARCH-modeled emissions. The regime detector governs which strategies are active
at any given time.

**Stage-agnostic design:** This skill consumes a 1D array of log returns. It does not
know or care whether those returns come from MT5 Forex bars or CME futures ticks.
The data pipeline feeds it returns via the ArcticDB read path; the execution adapter
feeds it real-time returns via ZeroMQ. The math is identical in both stages.

## Regime Definitions (K=3 States)

| State | Label           | Characteristics                         | Active Strategies (Stage A)      | Active Strategies (Stage B)         |
|-------|-----------------|-----------------------------------------|----------------------------------|-------------------------------------|
| S₁    | Trending        | Low vol, persistent direction           | ML Price Momentum, Carry         | ML Momentum + Orderflow, Carry      |
| S₂    | Mean-Reverting  | Moderate vol, oscillation               | Cointegration Pairs              | Cointegration Pairs                 |
| S₃    | Crisis/Volatile | High vol, fat tails, corr breakdown     | Reduce exposure, hedge only      | Reduce exposure, hedge only         |

## Mathematical Framework

### HMM Definition: λ = (A, B, π)

**Transition Matrix A** (K × K):
```
A = [ a₁₁  a₁₂  a₁₃ ]     where aᵢⱼ = P(Sₜ = j | Sₜ₋₁ = i)
    [ a₂₁  a₂₂  a₂₃ ]     Row-stochastic: Σⱼ aᵢⱼ = 1 ∀i
    [ a₃₁  a₃₂  a₃₃ ]
```

**Emission Distribution B** (GARCH-modeled):
```
bⱼ(oₜ) = P(oₜ | Sₜ = j) = fGARCH(oₜ; μⱼ, σ²ₜ|ⱼ)
```

### GARCH(1,1) per State

```
σ²ₜ|ⱼ = ωⱼ + αⱼ · ε²ₜ₋₁ + βⱼ · σ²ₜ₋₁|ⱼ

where:
  ωⱼ > 0, αⱼ ≥ 0, βⱼ ≥ 0, αⱼ + βⱼ < 1 (stationarity)
  εₜ = rₜ - μⱼ (return innovation under state j)

Emission PDF:
  bⱼ(rₜ) = (1 / √(2π · σ²ₜ|ⱼ)) · exp(-(rₜ - μⱼ)² / (2 · σ²ₜ|ⱼ))
```

### Baum-Welch Algorithm (EM)

**E-Step (Forward-Backward):**
```
Forward:  α₁(j) = πⱼ · bⱼ(o₁)
          αₜ(j) = [Σᵢ αₜ₋₁(i) · aᵢⱼ] · bⱼ(oₜ)

Backward: βₜ(i) = 1 for t=T
          βₜ(i) = Σⱼ aᵢⱼ · bⱼ(oₜ₊₁) · βₜ₊₁(j)

Posterior: γₜ(j) = αₜ(j) · βₜ(j) / P(O|λ)
```

**M-Step:**
```
π̂ⱼ = γ₁(j)
âᵢⱼ = Σₜ ξₜ(i,j) / Σₜ γₜ(i)
μ̂ⱼ = Σₜ γₜ(j) · oₜ / Σₜ γₜ(j)
GARCH params: weighted MLE per state
```

**Convergence:** |Δ log P(O|λ)| < 1e-6

### Viterbi Decoding

```
δ₁(j) = log πⱼ + log bⱼ(o₁)
δₜ(j) = maxᵢ [δₜ₋₁(i) + log aᵢⱼ] + log bⱼ(oₜ)
Backtrack: sₜ* = argmaxⱼ δₜ(j)
```

### Regime Switch Thresholds

```
Enter state j: P(Sₜ = j | O₁:ₜ) > τ_enter(j)
Exit state i:  P(Sₜ = i | O₁:ₜ) < τ_exit(i)

Defaults:
  τ_enter(S₁=Trending) = 0.70
  τ_enter(S₂=MeanRev)  = 0.65
  τ_enter(S₃=Crisis)   = 0.60  (lower for faster detection)
  τ_exit(any)           = 0.30

Hysteresis: minimum 20 bars in any state before allowing transition
```

## Implementation

```python
from hmmlearn import hmm
from arch import arch_model

class HMMGARCHRegimeDetector:
    """
    Stage-agnostic regime detector.
    Input: 1D numpy array of log returns
    Output: regime labels and state probabilities
    """

    def __init__(self, n_states=3, min_dwell=20):
        self.n_states = n_states
        self.min_dwell = min_dwell
        self.garch_params = {}
        self.transition_matrix = None
        self.initial_probs = None

    def fit(self, returns: np.ndarray):
        """Two-stage fitting: Gaussian HMM → per-state GARCH → custom Baum-Welch."""
        # Stage 1: Initial Gaussian HMM
        base = hmm.GaussianHMM(n_components=self.n_states, covariance_type='diag',
                                n_iter=100, tol=0.01)
        base.fit(returns.reshape(-1, 1))
        states = base.predict(returns.reshape(-1, 1))

        # Stage 2: Fit GARCH per state
        for s in range(self.n_states):
            state_returns = returns[states == s]
            if len(state_returns) < 100:
                continue
            garch = arch_model(state_returns, vol='Garch', p=1, q=1, dist='normal')
            res = garch.fit(disp='off')
            self.garch_params[s] = {
                'omega': res.params['omega'],
                'alpha': res.params['alpha[1]'],
                'beta': res.params['beta[1]'],
                'mu': res.params['mu']
            }

        self.transition_matrix = base.transmat_
        self.initial_probs = base.startprob_

    def predict_online(self, returns: np.ndarray) -> dict:
        """Forward-only regime prediction. PiT compliant."""
        T = len(returns)
        emissions = np.zeros((T, self.n_states))
        for j in range(self.n_states):
            emissions[:, j] = self._garch_emission(returns, j)

        alpha = np.zeros((T, self.n_states))
        alpha[0] = self.initial_probs * emissions[0]
        alpha[0] /= alpha[0].sum()

        for t in range(1, T):
            for j in range(self.n_states):
                alpha[t, j] = np.sum(alpha[t-1] * self.transition_matrix[:, j]) \
                              * emissions[t, j]
            alpha[t] /= alpha[t].sum()

        state_probs = alpha[-1]
        regime = np.argmax(state_probs)
        return {
            'state_probs': state_probs,
            'current_regime': regime,
            'label': ['trending', 'mean_reverting', 'crisis'][regime],
            'confidence': state_probs[regime]
        }

    def _garch_emission(self, returns, state):
        p = self.garch_params[state]
        T = len(returns)
        sigma2 = np.empty(T)
        sigma2[0] = p['omega'] / (1 - p['alpha'] - p['beta'])
        for t in range(1, T):
            eps = returns[t-1] - p['mu']
            sigma2[t] = p['omega'] + p['alpha'] * eps**2 + p['beta'] * sigma2[t-1]
        return (1 / np.sqrt(2 * np.pi * sigma2)) * \
               np.exp(-0.5 * (returns - p['mu'])**2 / sigma2)
```

## Recalibration Schedule

- Full Baum-Welch: weekly (Sunday maintenance window)
- GARCH parameters: every 1000 bars (recursive weighted MLE)
- Transition matrix: Dirichlet prior smoothing to prevent zero probabilities

## Implementation Structure

```
./src/alpha/regime/
  __init__.py
  hmm_garch.py          (HMMGARCHRegimeDetector class)
  emissions.py          (GARCH emission PDF computation)
  baum_welch.py         (Custom EM with GARCH emissions)
  viterbi.py            (Offline decoding)
  online_filter.py      (Forward-only real-time filter)
  calibration.py        (Weekly recalibration)
./tests/alpha/
  test_regime_detector.py
  test_pit_compliance.py
```
