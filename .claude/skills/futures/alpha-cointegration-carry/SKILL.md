---
name: alpha-cointegration-carry
description: >
  Implement the cointegration-based pairs trading and convexity carry alpha generation
  subsystems. Covers Vector Error Correction Model (VECM) specification, Johansen trace
  tests for cointegration rank, dynamic hedge ratio estimation, policy divergence modeling
  (RBNZ vs Fed for AUD/NZD), interest rate parity models for sovereign bond carry,
  pricing kernel covariance for yield pickup maximization, and currency duration risk
  hedging. Use this skill whenever working on: pairs trading strategies, cointegration
  analysis, VECM models, carry trade implementation, interest rate parity, sovereign
  bond pricing, hedge ratio computation, or any task involving the cointegration or
  carry alpha engines. Also trigger when the user mentions "cointegration", "VECM",
  "pairs trading", "trace test", "carry trade", "interest rate parity", "convexity",
  "hedge ratio", "policy divergence", or "pricing kernel".
---

# Alpha Cointegration & Carry Skill

## Purpose

This skill defines two distinct but complementary alpha generation engines:
1. **Cointegration Engine**: Dynamic pairs trading via VECM on CME currency futures
2. **Convexity Carry Engine**: Interest rate parity exploitation on sovereign bonds

Both engines operate under the regime detector's governance — the cointegration engine
activates primarily in mean-reverting regimes (S₂), while carry activates in trending
regimes (S₁) with low-volatility filters.

---

## Part 1: Cointegration Engine (VECM)

### Mathematical Foundation

Given a vector of K cointegrated CME futures prices Yₜ = [y₁ₜ, y₂ₜ, ..., yₖₜ]',
the VECM representation is:

```
ΔYₜ = αβ'Yₜ₋₁ + Σᵢ₌₁ᵖ⁻¹ Γᵢ ΔYₜ₋ᵢ + μ + εₜ

where:
  β  = cointegrating vectors (K × r matrix, r = cointegration rank)
  α  = adjustment/loading coefficients (K × r matrix)
  Γᵢ = short-run dynamics matrices
  β'Yₜ₋₁ = error correction terms (deviations from long-run equilibrium)
  εₜ ~ N(0, Σ) white noise innovation
```

### Johansen Trace Test for Cointegration Rank

The trace test determines the number of cointegrating relationships r:

```
H₀: rank(Π) ≤ r   vs   H₁: rank(Π) > r

Trace statistic: λ_trace(r) = -T Σᵢ₌ᵣ₊₁ᴷ ln(1 - λ̂ᵢ)

where λ̂ᵢ are eigenvalues of the concentrated product moment matrix.

Decision rule (5% significance, using Osterwald-Lenum critical values):
  If λ_trace(0) > cv(0) → reject r=0, test r=1
  If λ_trace(1) > cv(1) → reject r=1, test r=2
  Continue until fail to reject
```

### Target Pairs and Policy Divergence

Primary pair: **6A (AUD) vs 6N (NZD)** — structurally cointegrated due to:
- Geographic proximity and trade linkages
- Similar commodity-export economic structures
- Policy divergence creates exploitable spreads when RBNZ and RBA diverge

Secondary pairs: 6E/6B (EUR/GBP), 6J/6C (JPY/CAD — risk-on/off proxy)

### Dynamic Hedge Ratio

The hedge ratio β is NOT static — it's re-estimated on a rolling window:

```python
# Rolling Johansen estimation
WINDOW = 252 * 2  # 2 years of daily data (or equivalent in bars)
STEP = 21          # Re-estimate monthly

def compute_dynamic_hedge_ratio(y1: np.ndarray, y2: np.ndarray, window: int) -> np.ndarray:
    """
    Rolling Johansen cointegration with dynamic hedge ratio.
    PiT: hedge ratio at time T uses data [T-window, T-1] (shifted).
    """
    T = len(y1)
    hedge_ratios = np.full(T, np.nan)
    
    for t in range(window, T):
        # PiT: use data up to t-1 only
        y_window = np.column_stack([y1[t-window:t], y2[t-window:t]])
        
        result = coint_johansen(y_window, det_order=0, k_ar_diff=1)
        
        if result.trace_stat[0] > result.trace_stat_crit_vals[0, 1]:  # 5% level
            # Cointegration exists — extract hedge ratio from first eigenvector
            beta = result.evec[:, 0]
            hedge_ratios[t] = -beta[1] / beta[0]  # Normalized hedge ratio
    
    return hedge_ratios
```

### Spread Construction and Z-Score Trading

```
Spread: zₜ = y₁ₜ - βₜ · y₂ₜ

Z-score: Zₜ = (zₜ - μ_z(lookback)) / σ_z(lookback)

where μ_z and σ_z are rolling mean/std of the spread (PiT: computed on .shift(1) data)

Entry signals:
  Long spread:  Zₜ < -2.0  (spread is 2σ below mean)
  Short spread: Zₜ > +2.0  (spread is 2σ above mean)

Exit signals:
  Close long:   Zₜ > -0.5  (mean reversion toward zero)
  Close short:  Zₜ < +0.5

Stop loss:
  Hard stop if |Zₜ| > 4.0 (breakdown of cointegration relationship)
```

### Cointegration Health Monitoring

The cointegration relationship can break down. Monitor via:

```
Half-life of mean reversion: HL = -ln(2) / ln(δ)
  where δ is the AR(1) coefficient of the spread: zₜ = δ · zₜ₋₁ + εₜ

If HL > 60 days → relationship weakening, reduce position size by 50%
If HL > 120 days → relationship broken, close all positions, re-test Johansen
If trace statistic drops below 10% critical value → suspend pair entirely
```

---

## Part 2: Convexity Carry Engine

### Interest Rate Parity Framework

The carry trade exploits violations of Uncovered Interest Rate Parity (UIP):

```
UIP (theoretical): E[ΔSₜ₊₁] = iₜ - iₜ*

where:
  ΔSₜ₊₁ = expected change in exchange rate (domestic per foreign)
  iₜ     = domestic interest rate
  iₜ*    = foreign interest rate

UIP violation (empirical): High-yield currencies appreciate (forward premium puzzle)
  → Carry return = (iₜ* - iₜ) + ΔSₜ₊₁ > 0 on average
```

### Targeting Low-Cash-Price Sovereign Bonds

The strategy targets bonds trading at significant discounts to par (low cash price),
which exhibit enhanced convexity:

```
Bond convexity: C = (1/P) · d²P/dy² = (1/P) · Σₜ t(t+1)·CFₜ / (1+y)^(t+2)

Convexity advantage: For a given duration D, low-cash-price bonds have higher C
  → Positive carry + convexity gain on rate moves in either direction

Strategy:
  Long: Low-cash-price bonds in high-yield currency (e.g., AUD 10Y at 85 cash price)
  Hedge: Duration-neutral via short higher-cash-price bonds or futures
  Currency: Partially hedged via CME currency futures (6A for AUD exposure)
```

### Pricing Kernel Covariance

The yield pickup is maximized by selecting bonds whose pricing kernel covariance is
most favorable:

```
Pricing kernel: mₜ₊₁ = exp(-rₜ - ½λₜ'λₜ - λₜ'εₜ₊₁)

Excess return on bond j: E[rxⱼₜ₊₁] ≈ -Cov(rxⱼₜ₊₁, mₜ₊₁)

Select bonds that maximize:
  max_j { yield_pickup(j) - duration_risk(j) }
  
  yield_pickup(j) = yield(j) - funding_rate
  duration_risk(j) = modified_duration(j) · σ(Δy) · correlation_to_portfolio
```

### Currency Duration Risk Minimization

```
Total carry portfolio risk:
  σ²_portfolio = σ²_bond + σ²_fx + 2·ρ·σ_bond·σ_fx

Currency hedge ratio:
  h* = ρ · (σ_bond / σ_fx)  (minimum variance hedge ratio)

Implementation:
  - Compute rolling 60-day correlation between bond returns and FX returns
  - Adjust CME futures hedge notional daily based on h*
  - Cap hedge ratio at [0, 1] — never over-hedge or reverse-hedge
```

## Position Sizing Integration

Both engines feed into the Kelly Criterion (from cvar-risk-optimizer skill):

```
Kelly fraction for cointegration: f* = E[R_spread] / σ²(R_spread)
Kelly fraction for carry: f* = E[R_carry] / σ²(R_carry)

Apply half-Kelly for conservative sizing: f_actual = 0.5 · f*
Subject to CVaR constraint from risk optimizer
```

## Implementation Structure

```
./alpha-engine/
  cointegration/
    __init__.py
    johansen.py          (trace test, eigenvalue decomposition)
    vecm.py              (VECM estimation and forecasting)
    hedge_ratio.py       (dynamic rolling hedge ratio)
    spread_signals.py    (z-score computation, entry/exit logic)
    health_monitor.py    (half-life, cointegration breakdown detection)
  carry/
    __init__.py
    uip_model.py         (interest rate parity calculations)
    convexity.py         (bond convexity computation)
    pricing_kernel.py    (kernel covariance optimization)
    currency_hedge.py    (minimum variance hedge ratio)
  tests/
    test_johansen.py
    test_vecm.py
    test_carry.py
    test_pit_compliance.py
```

Read `prompts/` for tool-specific implementation prompts.
