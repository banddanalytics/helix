---
name: cvar-risk-optimizer
description: >
  Implement risk management using CVaR for tail-event optimization, Kelly Criterion for
  dynamic position sizing, and Equity Curve Trading for strategy viability governance.
  Stage-agnostic core math with stage-specific extensions: Stage A adds variable spread
  as a stochastic cost in CVaR and uses Forex lot sizing; Stage B uses deterministic
  exchange fees and CME contract sizing. Covers CVaR computation (historical, parametric,
  Cornish-Fisher), CVXPY portfolio optimization, fractional Kelly with regime adjustment,
  ECT sandbox/restore protocol, and drawdown circuit breakers. Use this skill for: risk
  management, position sizing, CVaR, Kelly Criterion, drawdown, strategy sandboxing,
  tail risk, circuit breakers, or portfolio optimization.
---

# CVaR Risk Optimizer Skill

## Purpose

Governs ALL risk decisions across both stages. No position is taken without CVaR
constraint check, Kelly sizing, and ECT viability filter.

## CVaR Computation (Stage-Agnostic Math)

### Method 1: Historical Simulation

```python
def compute_cvar_historical(returns: np.ndarray, alpha: float = 0.95) -> tuple:
    losses = -returns
    var = np.percentile(losses, alpha * 100)
    cvar = losses[losses >= var].mean()
    return var, cvar
```

### Method 2: Parametric (GARCH-informed)

```python
from scipy.stats import norm

def compute_cvar_parametric(mu: float, sigma: float, alpha: float = 0.95) -> tuple:
    z = norm.ppf(alpha)
    var = -(mu - z * sigma)
    cvar = -(mu - sigma * norm.pdf(z) / (1 - alpha))
    return var, cvar
```

### Method 3: Cornish-Fisher (fat tails)

```python
def compute_cvar_cornish_fisher(returns: np.ndarray, alpha: float = 0.95) -> tuple:
    mu, sigma = np.mean(returns), np.std(returns)
    skew = scipy.stats.skew(returns)
    kurt = scipy.stats.kurtosis(returns)
    z = norm.ppf(alpha)
    z_cf = z + (z**2-1)*skew/6 + (z**3-3*z)*kurt/24 - (2*z**3-5*z)*skew**2/36
    var = -(mu + z_cf * sigma)
    tail = returns[returns <= -(mu + z_cf * sigma)]
    cvar = -tail.mean() if len(tail) > 0 else var * 1.2
    return var, cvar
```

## Forex-Specific CVaR Extension (Stage A)

In Stage A, variable broker spreads introduce stochastic execution costs.
The CVaR must account for spread widening during stress periods:

```python
def compute_cvar_with_spread(returns: np.ndarray, spread_history: np.ndarray,
                              alpha: float = 0.95) -> tuple:
    """
    CVaR adjusted for variable spread costs.

    During crisis periods (regime S₃), spreads widen dramatically.
    This correlates with the worst return periods, making the tail fatter.
    """
    # Deduct estimated round-trip spread from each return
    # Use p95 spread during stress, median spread otherwise
    spread_cost = np.where(
        returns < np.percentile(returns, 10),  # Worst 10% of returns
        np.percentile(spread_history, 95) * 2,  # p95 spread, round-trip
        np.median(spread_history) * 2            # Median spread, round-trip
    )
    adjusted_returns = returns - spread_cost
    return compute_cvar_historical(adjusted_returns, alpha)
```

## CVXPY Portfolio Optimization

```python
import cvxpy as cp

def optimize_portfolio_cvar(returns, alpha=0.95, max_weight=0.25, cvar_budget=0.05):
    T, N = returns.shape
    w = cp.Variable(N)
    zeta = cp.Variable()
    u = cp.Variable(T)

    losses = -returns @ w
    constraints = [
        u >= 0, u >= losses - zeta,
        cp.sum(w) == 1, w >= 0, w <= max_weight,
        zeta + (1/(T*(1-alpha))) * cp.sum(u) <= cvar_budget
    ]

    prob = cp.Problem(cp.Minimize(zeta + (1/(T*(1-alpha))) * cp.sum(u)), constraints)
    prob.solve(solver=cp.ECOS)
    return w.value
```

## Kelly Criterion Position Sizing

### Continuous Kelly with Regime Adjustment

```python
def compute_kelly_fraction(returns: np.ndarray, regime: str,
                            max_fraction: float = 0.15) -> float:
    mu = np.mean(returns)
    var = np.var(returns)
    if var == 0 or mu <= 0:
        return 0.0

    full_kelly = mu / var
    multiplier = {'trending': 0.5, 'mean_reverting': 0.4, 'crisis': 0.1}
    adjusted = full_kelly * multiplier.get(regime, 0.3)
    return min(adjusted, max_fraction)
```

### Stage-Specific Sizing

```python
# Stage A: Kelly → Forex lots
from src.execution.lot_sizing import kelly_to_lots
lots = kelly_to_lots(equity, kelly_fraction, stop_loss_pips, symbol)

# Stage B: Kelly → CME contracts
contracts = int(equity * kelly_fraction / margin_per_contract)
```

## Equity Curve Trading (ECT)

```python
class EquityCurveTrader:
    def __init__(self, ma_window=50, deriv_window=20, recovery_bars=10):
        self.ma_window = ma_window
        self.deriv_window = deriv_window
        self.recovery_bars = recovery_bars
        self.sandboxed = {}

    def evaluate(self, strategy_name: str, equity_curve: np.ndarray) -> dict:
        ma = pd.Series(equity_curve).rolling(self.ma_window).mean().values
        deriv = np.diff(equity_curve, prepend=equity_curve[0])
        deriv_ma = pd.Series(deriv).rolling(self.deriv_window).mean().values

        current_eq = equity_curve[-1]
        is_sandboxed = strategy_name in self.sandboxed

        if not is_sandboxed:
            if current_eq < ma[-1] and deriv[-1] < deriv_ma[-1]:
                self.sandboxed[strategy_name] = {'recovery_count': 0}
                return {'action': 'SANDBOX'}
        else:
            if current_eq > ma[-1] and deriv[-1] > 0:
                self.sandboxed[strategy_name]['recovery_count'] += 1
                if self.sandboxed[strategy_name]['recovery_count'] >= self.recovery_bars:
                    del self.sandboxed[strategy_name]
                    return {'action': 'RESTORE', 'scale': 0.5}
            else:
                self.sandboxed[strategy_name]['recovery_count'] = 0

        return {'action': 'HOLD'}
```

## Circuit Breakers (Identical Both Stages)

```
Level 1 (WARNING):  Daily DD > 2% → All positions to 50% Kelly
Level 2 (HALT):     Daily DD > 5% → Flatten all, pause 1 hour
Level 3 (SHUTDOWN): Daily DD > 10% → Flatten all, require manual restart
```

## Risk Budget Allocation

```
                          Stage A (Forex)    Stage B (Futures)
Cointegration engine:     35%                30%
Carry engine:             25%                25%
ML Momentum:              30%                35%
Reserve:                  10%                10%
```

## Implementation Structure

```
./src/risk/
  cvar/
    historical.py, parametric.py, cornish_fisher.py
    spread_adjusted.py    (Stage A: spread-aware CVaR)
    portfolio_opt.py      (CVXPY optimization)
  kelly/
    criterion.py          (Full + fractional Kelly)
    regime_adjusted.py    (Regime-dependent multipliers)
  ect/
    equity_curve.py       (Sandbox/restore logic)
    virtual_executor.py   (Paper trading sandbox)
  circuit_breakers/
    drawdown_monitor.py, kill_switch.py
  tests/
    test_cvar.py, test_kelly.py, test_ect.py, test_circuit_breakers.py
```
