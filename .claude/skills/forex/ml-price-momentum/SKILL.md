---
name: ml-price-momentum
description: >
  Implement ML momentum alpha using features available WITHOUT genuine Market-by-Order
  data. Active in Stage A (Forex) and retained in Stage B (Futures) as a feature subset.
  Covers multi-horizon return momentum, Parkinson volatility, session structure features
  (Asian/London/NY), cross-asset correlation, tick volume proxies, XGBoost/RF ensemble with
  walk-forward validation, spread-cost-adjusted performance metrics, and SHAP feature
  selection. Use this skill when: ML signals from price data, tick volume features, session
  trading, multi-timeframe momentum, Forex ML, or any ML alpha without order book data.
---

# ML Price Momentum Skill (Non-MBO Environments)

## Purpose

ML momentum engine generating alpha from price and volume data available from ANY source.
Replaces MBO-dependent features (OFI, VPIN, iceberg) during Stage A with genuinely
available features. ALL features from this skill are RETAINED in Stage B — they supplement
(not get replaced by) the MBO features from `ml-momentum-orderflow`.

## Feature Tiers

### Tier 1: Multi-Horizon Return Momentum (8 features)

```python
@njit(cache=True)
def compute_momentum_features(close: np.ndarray, high: np.ndarray,
                                low: np.ndarray) -> np.ndarray:
    n = len(close)
    features = np.empty((n, 8))
    features[:] = np.nan

    for i in range(253, n):
        features[i, 0] = close[i-1] / close[i-2] - 1        # 1-bar return
        features[i, 1] = close[i-1] / close[i-6] - 1        # 5-bar return
        features[i, 2] = close[i-1] / close[i-11] - 1       # 10-bar return
        features[i, 3] = close[i-1] / close[i-22] - 1       # 1-month return
        features[i, 4] = close[i-1] / close[i-64] - 1       # 3-month return
        features[i, 5] = close[i-1] / close[i-253] - 1      # 12-month return

        # Momentum acceleration
        mom5 = close[i-1] / close[i-6] - 1
        mom5_prev = close[i-6] / close[i-11] - 1
        features[i, 6] = mom5 - mom5_prev

        # Range expansion (trend strength)
        recent_range = np.max(high[i-11:i]) - np.min(low[i-11:i])
        older_range = np.max(high[i-22:i-11]) - np.min(low[i-22:i-11])
        features[i, 7] = recent_range / max(older_range, 1e-10)

    return features
```

### Tier 2: Volatility Features (6 features)

```python
@njit(cache=True)
def compute_volatility_features(close: np.ndarray, high: np.ndarray,
                                  low: np.ndarray) -> np.ndarray:
    n = len(close)
    features = np.empty((n, 6))
    features[:] = np.nan
    log_ret = np.empty(n)
    log_ret[0] = 0.0
    for i in range(1, n):
        log_ret[i] = np.log(close[i] / close[i-1])

    for i in range(64, n):
        features[i, 0] = np.std(log_ret[i-5:i])      # 5-bar vol
        features[i, 1] = np.std(log_ret[i-22:i])     # 22-bar vol
        features[i, 2] = np.std(log_ret[i-63:i])     # 63-bar vol
        features[i, 3] = features[i, 0] / max(features[i, 2], 1e-10)  # Vol ratio

        # Parkinson volatility (high-low based, more efficient)
        hl_sum = 0.0
        for j in range(i-22, i):
            hl = np.log(high[j] / max(low[j], 1e-10))
            hl_sum += hl * hl
        features[i, 4] = np.sqrt(hl_sum / (22 * 4 * np.log(2.0)))

        # Volatility of volatility
        vol_5_series = np.empty(10)
        for k in range(10):
            idx = i - k
            vol_5_series[k] = np.std(log_ret[idx-5:idx])
        features[i, 5] = np.std(vol_5_series)

    return features
```

### Tier 3: Session Structure Features (5 features)

```python
@njit(cache=True)
def compute_session_features(hours: np.ndarray, close: np.ndarray,
                               high: np.ndarray, low: np.ndarray,
                               day_of_week: np.ndarray) -> np.ndarray:
    n = len(close)
    features = np.empty((n, 5))
    features[:] = np.nan

    for i in range(1, n):
        h = hours[i-1]
        # Session ID: 0=Asian(00-08), 1=London(08-13), 2=Overlap(13-16), 3=NY(16-21)
        if 0 <= h < 8:
            features[i, 0] = 0
        elif 8 <= h < 13:
            features[i, 0] = 1
        elif 13 <= h < 16:
            features[i, 0] = 2
        elif 16 <= h < 21:
            features[i, 0] = 3
        else:
            features[i, 0] = 0

        # Bar position within its range
        bar_range = high[i-1] - low[i-1]
        features[i, 1] = (close[i-1] - low[i-1]) / max(bar_range, 1e-10)

        # Relative bar size (current range vs 20-bar avg range)
        if i >= 21:
            avg_range = np.mean(high[i-21:i-1] - low[i-21:i-1])
            features[i, 2] = bar_range / max(avg_range, 1e-10)

        features[i, 3] = day_of_week[i-1]  # 0=Mon, 4=Fri
        features[i, 4] = 0.0  # Placeholder for distance from daily open

    return features
```

### Tier 4: Cross-Asset Features (4 features)

```python
def compute_cross_asset_features(price_dict: dict[str, np.ndarray]) -> np.ndarray:
    """
    Cross-pair momentum and correlation features.
    Computed in pandas (not Numba) due to multi-symbol alignment.
    """
    df = pd.DataFrame(price_dict)
    returns = df.pct_change()
    features = pd.DataFrame(index=df.index)

    # USD strength: average return of USD-quoted pairs (inverted)
    usd_pairs = [c for c in df.columns if c.endswith('USD') and c != 'USDJPY']
    if usd_pairs:
        features['usd_strength'] = -returns[usd_pairs].mean(axis=1).rolling(5).mean().shift(1)

    # Risk appetite: AUD + JPY divergence
    if 'AUDUSD' in returns and 'USDJPY' in returns:
        features['risk_appetite'] = (returns['AUDUSD'].rolling(10).mean() +
                                     returns['USDJPY'].rolling(10).mean()).shift(1)

    # Correlation regime: rolling corr between EUR and GBP
    if 'EURUSD' in returns and 'GBPUSD' in returns:
        features['eur_gbp_corr'] = returns['EURUSD'].rolling(20).corr(
            returns['GBPUSD']).shift(1)

    # Momentum dispersion: std of momentum across pairs
    mom_20 = returns.rolling(20).mean()
    features['mom_dispersion'] = mom_20.std(axis=1).shift(1)

    return features.values
```

### Tier 5: Tick Volume Features (4 features)

```python
@njit(cache=True)
def compute_tick_volume_features(tick_vol: np.ndarray,
                                   close: np.ndarray) -> np.ndarray:
    """
    Tick volume = count of price changes per bar (NOT real volume).
    Use for relative comparisons only.
    """
    n = len(tick_vol)
    features = np.empty((n, 4))
    features[:] = np.nan

    for i in range(22, n):
        avg_vol = np.mean(tick_vol[i-21:i])
        features[i, 0] = tick_vol[i-1] / max(avg_vol, 1.0)  # Relative volume

        recent = np.mean(tick_vol[i-6:i])
        older = np.mean(tick_vol[i-11:i-5])
        features[i, 1] = recent / max(older, 1.0)  # Volume trend

        # Price-volume divergence
        pc = close[i-1] - close[i-6]
        vc = tick_vol[i-1] - np.mean(tick_vol[i-6:i-1])
        features[i, 2] = np.sign(pc) * np.sign(vc)

        features[i, 3] = 1.0 if tick_vol[i-1] > 2 * avg_vol else 0.0  # Spike

    return features
```

## Model Architecture

XGBoost/RF ensemble with walk-forward validation — identical framework to
`ml-momentum-orderflow` but with different input features and adjusted parameters:

```
Model 1: XGBoost
  n_estimators: 500, max_depth: 5, learning_rate: 0.01
  subsample: 0.8, colsample_bytree: 0.7
  min_child_weight: 100, reg_alpha: 0.1, reg_lambda: 1.0

Model 2: Random Forest
  n_estimators: 1000, max_depth: 7, min_samples_leaf: 50
  max_features: 'sqrt', class_weight: 'balanced'

Ensemble: P = 0.5 * P_xgb + 0.5 * P_rf

Signal (wider thresholds than futures due to weaker signal):
  Long if P > 0.53
  Short if P < 0.47
  Flat otherwise
```

### Walk-Forward (Adjusted for Forex)

```
Train: [T-756, T-1]     (3 years — longer than futures due to weaker signal)
Validate: [T-63, T-1]   (last 3 months for early stopping)
Test: [T, T+21]          (1 month out-of-sample)
Purge: 5 bars between train and test
Step: 21 bars (monthly retraining)
```

### Spread-Cost-Adjusted Metrics

```python
def cost_adjusted_sharpe(returns: np.ndarray, spread_costs: np.ndarray) -> float:
    """Sharpe ratio after deducting broker spread costs."""
    net_returns = returns - spread_costs
    return np.mean(net_returns) / max(np.std(net_returns), 1e-10) * np.sqrt(252)
```

## Transition to Stage B

When migrating to CME futures:
1. KEEP all 27 features from this skill (Tiers 1-5)
2. ADD ~15 MBO features from `ml-momentum-orderflow` (OFI, VPIN, depth, iceberg)
3. Re-run walk-forward with expanded ~42 feature set
4. SHAP analysis shows relative contribution of old vs new features
5. Expected: IC improves from ~0.01-0.02 (Forex) to ~0.02-0.04 (Futures)

## Implementation Structure

```
./src/alpha/ml_price_momentum/
  features/
    momentum.py, volatility.py, session.py, cross_asset.py, tick_volume.py
    builder.py            (Assembles all tiers with PiT .shift(1))
  models/
    xgboost_model.py, rf_model.py, ensemble.py, walk_forward.py
  evaluation/
    shap_analysis.py, cost_adjusted_metrics.py
  tests/
    test_features.py, test_walk_forward.py, test_pit.py
```
