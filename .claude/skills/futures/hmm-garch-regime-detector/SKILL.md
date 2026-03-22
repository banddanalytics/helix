---
name: hmm-garch-regime-detector
description: >
  Implement the hybrid Hidden Markov Model (HMM) and GARCH pipeline for market regime
  detection. Covers GARCH(1,1) emission probability modeling for conditional heteroskedasticity,
  Baum-Welch algorithm for transition matrix estimation, Probability Density Function (PDF)
  threshold calibration for regime switching, Viterbi decoding for optimal state sequences,
  and regime classification into trending/mean-reverting/volatile states. Use this skill
  whenever working on: regime detection models, HMM implementation, GARCH volatility modeling,
  Baum-Welch parameter estimation, volatility clustering analysis, market state classification,
  or any task involving the regime detection layer of the trading system. Also trigger when
  the user mentions "HMM", "GARCH", "regime detection", "Baum-Welch", "emission probability",
  "volatility clustering", "state transition", "Viterbi", or "conditional heteroskedasticity".
---

# HMM-GARCH Regime Detector Skill

## Purpose

This skill defines the complete mathematical framework and implementation specification for
detecting market regimes using a hybrid Hidden Markov Model with GARCH-modeled emission
distributions. The regime detector is the master switch for the entire alpha generation
subsystem — it determines which strategies are active at any given time.

## Mathematical Framework

### Regime Definitions

The model identifies K=3 latent states:

| State | Label           | Characteristics                              | Active Strategies           |
|-------|-----------------|----------------------------------------------|-----------------------------|
| S₁    | Trending        | Low vol, persistent directional moves        | ML Momentum, Carry          |
| S₂    | Mean-Reverting  | Moderate vol, oscillating around equilibrium  | Cointegration, Pairs        |
| S₃    | Crisis/Volatile | High vol, fat tails, correlation breakdown   | Reduce exposure, hedge only |

### HMM Formal Definition

The HMM is defined by the tuple λ = (A, B, π) where:

**Transition Matrix A** (K × K):
```
A = [ a₁₁  a₁₂  a₁₃ ]     where aᵢⱼ = P(Sₜ = j | Sₜ₋₁ = i)
    [ a₂₁  a₂₂  a₂₃ ]     Row-stochastic: Σⱼ aᵢⱼ = 1 ∀i
    [ a₃₁  a₃₂  a₃₃ ]
```

**Emission Distribution B** (GARCH-modeled, not Gaussian):
```
bⱼ(oₜ) = P(oₜ | Sₜ = j) = fGARCH(oₜ; μⱼ, σ²ₜ|ⱼ)
```

Where σ²ₜ|ⱼ is the conditional variance under state j, modeled by GARCH(1,1).

**Initial State Distribution π**:
```
πⱼ = P(S₁ = j), where Σⱼ πⱼ = 1
```

### GARCH(1,1) Emission Model

For each state j ∈ {1, 2, 3}, the conditional variance follows:

```
σ²ₜ|ⱼ = ωⱼ + αⱼ · ε²ₜ₋₁ + βⱼ · σ²ₜ₋₁|ⱼ

where:
  ωⱼ > 0           (state-specific intercept/base volatility)
  αⱼ ≥ 0           (ARCH coefficient — reaction to shocks)
  βⱼ ≥ 0           (GARCH coefficient — volatility persistence)
  αⱼ + βⱼ < 1      (stationarity constraint)
  εₜ = rₜ - μⱼ     (return innovation under state j)
```

The emission PDF for state j at time t:

```
bⱼ(rₜ) = (1 / √(2π · σ²ₜ|ⱼ)) · exp(-(rₜ - μⱼ)² / (2 · σ²ₜ|ⱼ))
```

**State-Specific Parameter Priors (initial calibration):**

| State | μⱼ (drift)  | ωⱼ (base vol) | αⱼ (shock react) | βⱼ (persistence) |
|-------|-------------|----------------|-------------------|-------------------|
| S₁    | ±0.0002     | 1e-6           | 0.05              | 0.90              |
| S₂    | ~0.0        | 5e-6           | 0.10              | 0.85              |
| S₃    | ~0.0        | 2e-5           | 0.20              | 0.75              |

### Baum-Welch Algorithm (EM for HMM)

The Baum-Welch algorithm iteratively estimates λ = (A, B, π) by maximizing the
likelihood P(O | λ) where O = {o₁, o₂, ..., oₜ} is the observed return sequence.

**E-Step: Forward-Backward**

Forward variable:
```
α₁(j) = πⱼ · bⱼ(o₁)
αₜ(j) = [Σᵢ αₜ₋₁(i) · aᵢⱼ] · bⱼ(oₜ)     for t = 2, ..., T
```

Backward variable:
```
βₜ(i) = 1                                   for t = T
βₜ(i) = Σⱼ aᵢⱼ · bⱼ(oₜ₊₁) · βₜ₊₁(j)     for t = T-1, ..., 1
```

Posterior state probability:
```
γₜ(j) = P(Sₜ = j | O, λ) = αₜ(j) · βₜ(j) / P(O | λ)
```

Posterior transition probability:
```
ξₜ(i,j) = P(Sₜ = i, Sₜ₊₁ = j | O, λ) = αₜ(i) · aᵢⱼ · bⱼ(oₜ₊₁) · βₜ₊₁(j) / P(O | λ)
```

**M-Step: Parameter Re-estimation**

```
π̂ⱼ = γ₁(j)

âᵢⱼ = Σₜ₌₁ᵀ⁻¹ ξₜ(i,j) / Σₜ₌₁ᵀ⁻¹ γₜ(i)

μ̂ⱼ = Σₜ γₜ(j) · oₜ / Σₜ γₜ(j)

GARCH params (ω̂ⱼ, α̂ⱼ, β̂ⱼ) re-estimated via weighted MLE:
  maximize Σₜ γₜ(j) · log bⱼ(oₜ; ωⱼ, αⱼ, βⱼ)
  subject to: ωⱼ > 0, αⱼ ≥ 0, βⱼ ≥ 0, αⱼ + βⱼ < 1
```

**Convergence:** Iterate E-step and M-step until |log P(O | λ⁽ⁿ⁾) - log P(O | λ⁽ⁿ⁻¹⁾)| < ε (ε = 1e-6).

### Viterbi Decoding

For the most likely state sequence S* = {s₁*, s₂*, ..., sₜ*}:

```
δ₁(j) = log πⱼ + log bⱼ(o₁)
δₜ(j) = maxᵢ [δₜ₋₁(i) + log aᵢⱼ] + log bⱼ(oₜ)
ψₜ(j) = argmaxᵢ [δₜ₋₁(i) + log aᵢⱼ]

Backtrack: sₜ* = argmaxⱼ δₜ(j), sₜ₋₁* = ψₜ(sₜ*), ...
```

### Regime Switch Detection via PDF Thresholds

A regime transition is triggered when the filtered probability crosses calibrated thresholds:

```
Regime switch from i to j activated when:
  P(Sₜ = j | O₁:ₜ) > τ_enter(j)   AND   P(Sₜ = i | O₁:ₜ) < τ_exit(i)

Default thresholds:
  τ_enter(S₁) = 0.70  (enter Trending)
  τ_enter(S₂) = 0.65  (enter Mean-Reverting)
  τ_enter(S₃) = 0.60  (enter Crisis — lower threshold for faster detection)
  τ_exit(*)   = 0.30   (exit any state)
```

**Hysteresis Buffer:** To prevent rapid oscillation between states, enforce a minimum
dwell time of 20 bars in any state before allowing a transition. This prevents the
Baum-Welch posterior from causing whipsaw state changes on noisy data.

## Implementation Pseudocode

```python
import numpy as np
from arch import arch_model
from hmmlearn import hmm
from numba import njit

class HMMGARCHRegimeDetector:
    def __init__(self, n_states: int = 3, min_dwell: int = 20):
        self.n_states = n_states
        self.min_dwell = min_dwell
        self.garch_params = {}  # {state: (omega, alpha, beta, mu)}
        self.transition_matrix = None
        self.initial_probs = None
        self.thresholds = {
            'enter': [0.70, 0.65, 0.60],
            'exit': 0.30
        }

    def fit(self, returns: np.ndarray):
        """
        Two-stage fitting:
        1. Fit base HMM with Gaussian emissions to get initial state assignments
        2. Fit GARCH(1,1) per state, then re-run Baum-Welch with GARCH emissions
        """
        # Stage 1: Initial HMM fit (Gaussian emissions)
        base_hmm = hmm.GaussianHMM(n_components=self.n_states, covariance_type='diag')
        base_hmm.fit(returns.reshape(-1, 1))
        initial_states = base_hmm.predict(returns.reshape(-1, 1))

        # Stage 2: Fit GARCH per state
        for state in range(self.n_states):
            state_returns = returns[initial_states == state]
            if len(state_returns) < 100:
                continue
            garch = arch_model(state_returns, vol='Garch', p=1, q=1, dist='normal')
            res = garch.fit(disp='off')
            self.garch_params[state] = {
                'omega': res.params['omega'],
                'alpha': res.params['alpha[1]'],
                'beta': res.params['beta[1]'],
                'mu': res.params['mu']
            }

        # Stage 3: Custom Baum-Welch with GARCH emissions
        self.transition_matrix = base_hmm.transmat_
        self.initial_probs = base_hmm.startprob_
        self._baum_welch_garch(returns)

    def _garch_emission_prob(self, returns: np.ndarray, state: int) -> np.ndarray:
        """Compute GARCH(1,1) emission probabilities for a given state."""
        p = self.garch_params[state]
        T = len(returns)
        sigma2 = np.empty(T)
        sigma2[0] = p['omega'] / (1 - p['alpha'] - p['beta'])  # unconditional var

        for t in range(1, T):
            eps = returns[t-1] - p['mu']
            sigma2[t] = p['omega'] + p['alpha'] * eps**2 + p['beta'] * sigma2[t-1]

        # Gaussian PDF with time-varying variance
        probs = (1.0 / np.sqrt(2 * np.pi * sigma2)) * \
                np.exp(-0.5 * (returns - p['mu'])**2 / sigma2)
        return probs

    def predict_online(self, returns_history: np.ndarray) -> dict:
        """
        Online regime prediction using forward algorithm only.
        PiT compliant: uses data up to T to produce state probs at T.
        """
        T = len(returns_history)

        # Compute emission probs for all states
        emissions = np.zeros((T, self.n_states))
        for j in range(self.n_states):
            emissions[:, j] = self._garch_emission_prob(returns_history, j)

        # Forward pass only (no backward — online/real-time)
        alpha = np.zeros((T, self.n_states))
        alpha[0] = self.initial_probs * emissions[0]
        alpha[0] /= alpha[0].sum()

        for t in range(1, T):
            for j in range(self.n_states):
                alpha[t, j] = np.sum(alpha[t-1] * self.transition_matrix[:, j]) * emissions[t, j]
            alpha[t] /= alpha[t].sum()  # normalize to prevent underflow

        # Current state probabilities
        state_probs = alpha[-1]
        current_regime = np.argmax(state_probs)

        return {
            'state_probs': state_probs,
            'current_regime': current_regime,
            'regime_label': ['trending', 'mean_reverting', 'crisis'][current_regime],
            'confidence': state_probs[current_regime]
        }
```

## Online vs Offline Usage

- **Offline (backtesting):** Full Baum-Welch + Viterbi on complete dataset. PiT enforced
  by running on `.shift(1)` data and assigning labels to current row.
- **Online (live):** Forward algorithm only (no backward pass). Update GARCH parameters
  via exponentially weighted recursive update every N bars (N=1000 default).

## Recalibration Protocol

- Full Baum-Welch re-estimation: Weekly (Sunday maintenance window)
- GARCH parameter update: Every 1000 bars (recursive weighted MLE)
- Transition matrix smoothing: Apply Dirichlet prior to prevent zero-probability transitions

Read `prompts/` for tool-specific implementation prompts.
