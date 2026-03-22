---
name: alpha-cointegration-carry
description: >
  Implement cointegration-based pairs trading and carry trade alpha engines. This skill
  supports BOTH stages: in Stage A (Forex), carry signals derive from broker swap rates
  and pairs trade synthetic spreads from two separate positions. In Stage B (Futures),
  carry derives from term structure and spreads trade as exchange-defined calendar spreads.
  Covers VECM specification, Johansen trace tests, dynamic hedge ratios, z-score trading,
  half-life monitoring, swap-based carry (Stage A), term structure carry (Stage B), and
  currency duration hedging. Use this skill whenever working on: pairs trading, cointegration,
  VECM, carry trade, interest rate parity, hedge ratios, z-scores, swap rates, term
  structure, or policy divergence.
---

# Alpha Cointegration & Carry Skill

## Purpose

Two complementary alpha engines:
1. **Cointegration**: Dynamic pairs trading via VECM — works on any correlated price series
2. **Carry**: Exploit yield differentials — source differs by stage

## Part 1: Cointegration Engine (Stage-Agnostic)

The VECM math is identical whether trading Forex pairs or CME futures pairs.

### VECM Representation

```
ΔYₜ = αβ'Yₜ₋₁ + Σᵢ Γᵢ ΔYₜ₋ᵢ + μ + εₜ

where:
  β  = cointegrating vectors (long-run equilibrium)
  α  = adjustment coefficients (speed of mean reversion)
  β'Yₜ₋₁ = error correction terms (deviations from equilibrium)
```

### Johansen Trace Test

```python
from statsmodels.tsa.vector_ar.vecm import coint_johansen, VECM, select_coint_rank

def test_cointegration(y1: np.ndarray, y2: np.ndarray) -> dict:
    """
    Test cointegration between two price series.
    Works for EURUSD/GBPUSD (Forex) or 6E/6B (futures).
    """
    data = np.column_stack([y1, y2])
    result = coint_johansen(data, det_order=0, k_ar_diff=1)

    trace_stat = result.trace_stat[0]
    crit_95 = result.trace_stat_crit_vals[0, 1]

    return {
        'cointegrated': trace_stat > crit_95,
        'trace_stat': trace_stat,
        'crit_95': crit_95,
        'hedge_ratio': -result.evec[1, 0] / result.evec[0, 0],
        'eigenvectors': result.evec
    }
```

### Dynamic Hedge Ratio (Rolling)

```python
def compute_dynamic_hedge_ratio(y1, y2, window=504, step=21):
    """
    Rolling Johansen with PiT compliance.
    Hedge ratio at T uses data [T-window, T-1] only.
    """
    T = len(y1)
    hedge_ratios = np.full(T, np.nan)

    for t in range(window, T):
        data = np.column_stack([y1[t-window:t], y2[t-window:t]])
        result = coint_johansen(data, det_order=0, k_ar_diff=1)
        if result.trace_stat[0] > result.trace_stat_crit_vals[0, 1]:
            hedge_ratios[t] = -result.evec[1, 0] / result.evec[0, 0]

    return hedge_ratios
```

### Spread Z-Score Trading

```
Spread: zₜ = y₁ₜ - βₜ · y₂ₜ
Z-score: Zₜ = (zₜ - μ_z) / σ_z  (rolling mean/std on .shift(1) data)

Entry: Long spread at Zₜ < -2.0, Short spread at Zₜ > +2.0
Exit:  Close long at Zₜ > -0.5, Close short at Zₜ < +0.5
Stop:  Hard stop if |Zₜ| > 4.0 (cointegration breakdown)
```

### Half-Life Monitoring

```
HL = -ln(2) / ln(δ)   where δ is AR(1) coeff: zₜ = δ·zₜ₋₁ + εₜ

If HL > 60 days → reduce size 50% (relationship weakening)
If HL > 120 days → close all, re-test Johansen
If trace stat < 10% critical value → suspend pair
```

### Target Pairs

**Stage A (Forex):** AUDUSD/NZDUSD, EURUSD/GBPUSD, USDJPY/USDCHF
- Trade as two separate positions (buy one, sell other)
- Account for two separate spread costs
- Hedge ratio expressed in lot ratio

**Stage B (Futures):** 6A/6N, 6E/6B, 6J/6S
- Can trade as exchange-defined calendar/inter-commodity spreads
- Single spread commission
- Hedge ratio expressed in contract ratio

## Part 2: Carry Engine

### Stage A: Swap-Based Carry (Forex)

```python
def compute_forex_carry(symbols: list[str]) -> pd.DataFrame:
    """
    Carry signal from MT5 swap rates.

    Carry = annualized swap rate for holding a position overnight.
    Positive carry = you earn interest; Negative = you pay.

    The carry_signal is a normalized float that the alpha engine
    consumes identically regardless of source.
    """
    from src.execution.swap_rates import compute_annualized_carry

    carries = []
    for symbol in symbols:
        c = compute_annualized_carry(symbol)
        carries.append({
            'symbol': symbol,
            'carry_signal': c['net_carry_signal'],  # Normalized float
            'carry_long': c['annual_carry_long_pct'],
            'carry_short': c['annual_carry_short_pct'],
        })

    df = pd.DataFrame(carries)
    # Cross-sectional rank: long top quartile, short bottom quartile
    df['rank'] = df['carry_signal'].rank(pct=True)
    df['position'] = np.where(df['rank'] > 0.75, 1,
                     np.where(df['rank'] < 0.25, -1, 0))
    return df
```

### Stage B: Term Structure Carry (Futures)

```python
def compute_futures_carry(front_price, back_price,
                           front_expiry_days, back_expiry_days):
    """
    Carry from futures term structure (roll yield).

    Annualized carry = (F1/F2 - 1) × 365/(D2 - D1)

    Contango (F1 < F2): negative carry (short signal)
    Backwardation (F1 > F2): positive carry (long signal)
    """
    if back_expiry_days <= front_expiry_days:
        return 0.0

    raw_carry = (front_price / back_price - 1)
    annualized = raw_carry * 365.0 / (back_expiry_days - front_expiry_days)
    return annualized  # Same normalized float as forex carry
```

### Unified Carry Interface

```python
class CarrySignalProvider(ABC):
    """Alpha engines call this. They don't know the source."""
    @abstractmethod
    def get_carry_signals(self, symbols: list[str]) -> dict[str, float]:
        """Returns {symbol: carry_signal_float} for each symbol."""
        ...

class ForexCarryProvider(CarrySignalProvider):
    """Stage A: reads from MT5 swap rates."""
    def get_carry_signals(self, symbols):
        return {s: compute_annualized_carry(s)['net_carry_signal'] for s in symbols}

class FuturesCarryProvider(CarrySignalProvider):
    """Stage B: reads from CME term structure."""
    def get_carry_signals(self, symbols):
        # Read front/back month prices from ArcticDB
        # Compute term structure carry per symbol
        ...
```

## Stage-Specific Execution Differences

| Aspect             | Stage A (Forex)                        | Stage B (Futures)                    |
|--------------------|----------------------------------------|--------------------------------------|
| Spread execution   | Two separate orders (buy X, sell Y)    | Single spread order (if available)   |
| Spread cost        | 2× broker spread per round trip        | 1× exchange fee per spread leg       |
| Carry source       | Broker swap rates                      | Futures term structure               |
| Hedge ratio units  | Lot ratio (e.g., 1.0 lot vs 0.85 lot) | Contract ratio (e.g., 1 vs 1)        |
| Overnight cost     | Swap points (triple Wednesday)         | None (mark-to-market daily)          |
| Position limits    | Broker-dependent                       | CME position limits                  |

## Implementation Structure

```
./src/alpha/
  cointegration/
    __init__.py
    johansen.py            (Trace test, cointegration rank)
    vecm.py                (VECM estimation)
    hedge_ratio.py         (Dynamic rolling hedge ratio)
    spread_signals.py      (Z-score entry/exit logic)
    health_monitor.py      (Half-life, breakdown detection)
  carry/
    __init__.py
    carry_provider.py      (Abstract CarrySignalProvider)
    forex_carry.py         (Stage A: swap rate implementation)
    futures_carry.py       (Stage B: term structure — stub during Stage A)
  tests/
    test_johansen.py
    test_vecm.py
    test_carry.py
    test_pit_compliance.py
```
