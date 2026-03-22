---
name: cvar-risk-optimizer
description: >
  Implement the risk management layer using Conditional Value-at-Risk (CVaR) for tail-event
  convex optimization, Kelly Criterion for dynamic position sizing, and Equity Curve Trading
  (ECT) for strategy viability governance. Covers CVaR integral computation, convex optimization
  via CVXPY, fractional Kelly sizing with regime-dependent adjustments, ECT moving average
  sandboxing protocol, portfolio-level risk aggregation, and drawdown circuit breakers. Use
  this skill whenever working on: risk management, position sizing, CVaR computation, Kelly
  Criterion, portfolio optimization, drawdown management, strategy sandboxing, tail risk
  analysis, or any task involving the risk layer. Also trigger when the user mentions "CVaR",
  "Value at Risk", "Kelly Criterion", "position sizing", "Equity Curve Trading", "drawdown",
  "tail risk", "risk optimization", "sandbox", or "circuit breaker".
---

# CVaR Risk Optimizer Skill

## Purpose

This skill governs ALL risk management decisions across the trading system. No position
is taken without passing through the CVaR constraint check, Kelly sizing, and ECT
viability filter. This is the system's last line of defense against catastrophic loss.

## CVaR (Conditional Value-at-Risk)

### Definition

CVaR at confidence level α (e.g., α=0.95) is the expected loss given that the loss
exceeds the VaR threshold:

```
CVaR_α = E[L | L ≥ VaR_α] = (1/(1-α)) ∫_{α}^{1} VaR_u du

where:
  L = portfolio loss (positive values = losses)
  VaR_α = inf{l : P(L ≤ l) ≥ α}  (the α-quantile of the loss distribution)
  CVaR_α ≥ VaR_α always (CVaR is a more conservative measure)
```

### Computation Methods

**Method 1: Historical Simulation (primary)**
```python
def compute_cvar_historical(returns: np.ndarray, alpha: float = 0.95) -> float:
    """
    CVaR from empirical return distribution.
    Uses the worst (1-α)% of returns.
    """
    losses = -returns  # Convert returns to losses
    var_threshold = np.percentile(losses, alpha * 100)
    tail_losses = losses[losses >= var_threshold]
    cvar = tail_losses.mean()
    return cvar
```

**Method 2: Parametric (GARCH-informed, for regime-dependent CVaR)**
```python
def compute_cvar_parametric(mu: float, sigma: float, alpha: float = 0.95) -> float:
    """
    Gaussian parametric CVaR. Use sigma from GARCH conditional variance.

    CVaR_α = μ + σ · φ(Φ⁻¹(α)) / (1-α)

    where φ = standard normal PDF, Φ⁻¹ = standard normal quantile function
    """
    from scipy.stats import norm
    z_alpha = norm.ppf(alpha)
    cvar = mu + sigma * norm.pdf(z_alpha) / (1 - alpha)
    return cvar
```

**Method 3: Cornish-Fisher Expansion (for fat tails)**
```python
def compute_cvar_cornish_fisher(returns: np.ndarray, alpha: float = 0.95) -> float:
    """
    CVaR adjusted for skewness and kurtosis via Cornish-Fisher expansion.
    Better for fat-tailed return distributions (which CME futures exhibit).
    """
    mu = np.mean(returns)
    sigma = np.std(returns)
    skew = scipy.stats.skew(returns)
    kurt = scipy.stats.kurtosis(returns)  # excess kurtosis

    z = norm.ppf(alpha)
    z_cf = (z + (z**2 - 1)*skew/6 + (z**3 - 3*z)*(kurt)/24
            - (2*z**3 - 5*z)*(skew**2)/36)

    var_cf = -(mu + z_cf * sigma)
    # CVaR approximation: integrate the Cornish-Fisher adjusted tail
    tail_returns = returns[returns <= -(mu + z_cf * sigma)]
    cvar = -tail_returns.mean() if len(tail_returns) > 0 else var_cf * 1.2
    return cvar
```

### CVaR Portfolio Optimization

The portfolio allocation problem:

```
minimize  CVaR_α(w'R)
subject to:
  w'μ ≥ target_return          (minimum return constraint)
  Σᵢ wᵢ = 1                   (fully invested)
  wᵢ ≥ 0  ∀i                  (long-only, or relax for L/S)
  wᵢ ≤ w_max  ∀i              (concentration limit, e.g., 0.25)
  CVaR_α(w'R) ≤ cvar_budget   (CVaR budget per strategy)
```

**CVXPY Implementation:**
```python
import cvxpy as cp

def optimize_portfolio_cvar(
    returns: np.ndarray,      # (T, N) matrix of strategy returns
    alpha: float = 0.95,
    target_return: float = 0.0,
    max_weight: float = 0.25,
    cvar_budget: float = 0.05  # 5% CVaR budget
) -> np.ndarray:
    """
    CVaR-constrained portfolio optimization using CVXPY.
    Reformulated as a linear program per Rockafellar-Uryasev (2000).
    """
    T, N = returns.shape

    # Decision variables
    w = cp.Variable(N)          # portfolio weights
    zeta = cp.Variable()        # VaR threshold
    u = cp.Variable(T)          # auxiliary variables for CVaR linearization

    # CVaR as linear program
    # CVaR_α = zeta + (1/(T(1-α))) Σ_t max(-w'r_t - zeta, 0)
    portfolio_losses = -returns @ w  # (T,) vector of portfolio losses

    constraints = [
        u >= 0,
        u >= portfolio_losses - zeta,
        cp.sum(w) == 1,
        w >= 0,
        w <= max_weight,
        returns.mean(axis=0) @ w >= target_return,
        zeta + (1 / (T * (1 - alpha))) * cp.sum(u) <= cvar_budget  # CVaR constraint
    ]

    # Objective: minimize CVaR
    objective = cp.Minimize(zeta + (1 / (T * (1 - alpha))) * cp.sum(u))

    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.ECOS)

    return w.value
```

## Kelly Criterion Position Sizing

### Full Kelly

```
f* = (p · b - q) / b = (p(b+1) - 1) / b

where:
  p = probability of winning trade
  b = ratio of average win to average loss (win/loss ratio)
  q = 1 - p = probability of losing trade
  f* = fraction of capital to risk
```

### Continuous Kelly (for return distributions)

```
f* = μ / σ²

where:
  μ = expected return of the strategy
  σ² = variance of returns
```

### Fractional Kelly (production implementation)

Full Kelly is too aggressive for real trading. Use half-Kelly or regime-adjusted:

```python
def compute_kelly_fraction(
    returns: np.ndarray,
    regime: str,
    max_fraction: float = 0.15  # Hard cap at 15% of capital per trade
) -> float:
    """
    Regime-adjusted fractional Kelly position sizing.
    """
    mu = np.mean(returns)
    var = np.var(returns)

    if var == 0 or mu <= 0:
        return 0.0

    full_kelly = mu / var

    # Regime adjustment
    regime_multiplier = {
        'trending': 0.5,        # Half-Kelly in trending (moderate confidence)
        'mean_reverting': 0.4,  # 40% Kelly in mean-reverting
        'crisis': 0.1           # 10% Kelly in crisis (extreme caution)
    }

    adjusted = full_kelly * regime_multiplier.get(regime, 0.3)

    # Hard cap
    return min(adjusted, max_fraction)
```

## Equity Curve Trading (ECT)

ECT monitors the cumulative PnL of each strategy. When a strategy's equity curve
deteriorates, it is sandboxed (paper-traded) until recovery.

### ECT Protocol

```
For each strategy S with equity curve E(t):

1. Compute MA(E, window=50):  50-bar moving average of equity curve
2. Compute dE/dt:             first derivative (PnL rate of change)
3. Compute MA(dE/dt, 20):     moving average of PnL derivative

Sandboxing trigger:
  IF E(t) < MA(E, 50) AND dE/dt < MA(dE/dt, 20)
  THEN: Move strategy S to virtual execution (paper trading)
        Log: "Strategy {S} sandboxed at t={t}, E={E(t)}, MA={MA}"
        Continue monitoring with paper trades

Recovery trigger:
  IF E_virtual(t) > MA(E_virtual, 50) AND dE_virtual/dt > 0
  FOR 10 consecutive bars
  THEN: Restore strategy S to live execution
        Size: Start at 50% of normal Kelly allocation, scale to 100% over 20 bars
        Log: "Strategy {S} restored at t={t}, paper_E={E_virtual(t)}"
```

### ECT Implementation

```python
class EquityCurveTrader:
    def __init__(self, ma_window: int = 50, deriv_window: int = 20,
                 recovery_bars: int = 10):
        self.ma_window = ma_window
        self.deriv_window = deriv_window
        self.recovery_bars = recovery_bars
        self.sandboxed = {}  # {strategy_name: sandbox_state}

    def evaluate(self, strategy_name: str, equity_curve: np.ndarray) -> dict:
        """Evaluate whether a strategy should be sandboxed or restored."""
        ma = pd.Series(equity_curve).rolling(self.ma_window).mean().values
        deriv = np.diff(equity_curve, prepend=equity_curve[0])
        deriv_ma = pd.Series(deriv).rolling(self.deriv_window).mean().values

        current_equity = equity_curve[-1]
        current_ma = ma[-1]
        current_deriv = deriv[-1]
        current_deriv_ma = deriv_ma[-1]

        is_sandboxed = strategy_name in self.sandboxed

        if not is_sandboxed:
            # Check sandbox trigger
            if current_equity < current_ma and current_deriv < current_deriv_ma:
                self.sandboxed[strategy_name] = {
                    'entry_time': len(equity_curve),
                    'entry_equity': current_equity,
                    'recovery_count': 0
                }
                return {'action': 'SANDBOX', 'reason': 'Equity below MA + negative PnL derivative'}
        else:
            # Check recovery trigger
            state = self.sandboxed[strategy_name]
            if current_equity > current_ma and current_deriv > 0:
                state['recovery_count'] += 1
                if state['recovery_count'] >= self.recovery_bars:
                    del self.sandboxed[strategy_name]
                    return {'action': 'RESTORE', 'scale': 0.5}  # 50% initial allocation
            else:
                state['recovery_count'] = 0

        return {'action': 'HOLD', 'status': 'sandboxed' if is_sandboxed else 'active'}
```

## Portfolio-Level Risk Aggregation

```
Total portfolio CVaR:
  CVaR_portfolio ≤ Σᵢ wᵢ · CVaR_i  (sub-additive, but not tight)

Better: compute CVaR on the aggregate portfolio return directly:
  R_portfolio(t) = Σᵢ wᵢ · Rᵢ(t)
  CVaR_portfolio = compute_cvar_historical(R_portfolio, α=0.95)

Risk budget allocation:
  Cointegration engine: 30% of total CVaR budget
  Carry engine:         25% of total CVaR budget
  ML Momentum engine:   35% of total CVaR budget
  Reserve:              10% (unallocated buffer for regime transitions)
```

## Circuit Breakers

```
Level 1 (WARNING):  Daily drawdown > 2% → Reduce all positions to 50% Kelly
Level 2 (HALT):     Daily drawdown > 5% → Flatten all positions, pause for 1 hour
Level 3 (SHUTDOWN): Daily drawdown > 10% → Flatten all, disable all strategies,
                    require manual restart with 2FA confirmation from Nairobi dashboard
```

## Implementation Structure

```
./risk-engine/
  __init__.py
  cvar/
    historical.py       (historical simulation CVaR)
    parametric.py       (GARCH-informed parametric CVaR)
    cornish_fisher.py   (fat-tail adjusted CVaR)
    portfolio_opt.py    (CVXPY portfolio optimization)
  kelly/
    criterion.py        (full + fractional Kelly)
    regime_adjusted.py  (regime-dependent sizing)
  ect/
    equity_curve.py     (ECT sandbox/restore logic)
    virtual_executor.py (paper trading sandbox environment)
  circuit_breakers/
    drawdown_monitor.py (real-time drawdown tracking)
    kill_switch.py      (Level 1/2/3 circuit breaker implementation)
  tests/
    test_cvar.py
    test_kelly.py
    test_ect.py
    test_circuit_breakers.py
```

Read `prompts/` for tool-specific implementation prompts.
