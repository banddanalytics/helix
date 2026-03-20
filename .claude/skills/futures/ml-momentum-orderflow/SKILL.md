---
name: ml-momentum-orderflow
description: >
  Implement the machine learning momentum alpha engine using homogeneous ensemble models
  (XGBoost and Random Forests) to detect MBO liquidity imbalances and institutional iceberg
  order footprints. Covers feature engineering from Market-by-Order tick data, order flow
  imbalance metrics (VPIN, OFI, trade flow toxicity), iceberg order detection heuristics,
  XGBoost/RF hyperparameter tuning with walk-forward optimization, ensemble stacking,
  and feature importance analysis via SHAP. Use this skill whenever working on: ML-based
  trading signals, order flow analysis, XGBoost/RF for financial prediction, MBO feature
  engineering, iceberg order detection, liquidity imbalance modeling, ensemble methods for
  alpha generation, or any task involving the ML momentum layer. Also trigger when the user
  mentions "XGBoost", "Random Forest", "order flow", "liquidity imbalance", "iceberg orders",
  "VPIN", "MBO features", "ensemble model", "ML momentum", or "trade flow toxicity".
---

# ML Momentum & Orderflow Skill

## Purpose

This skill defines the machine learning pipeline that reads raw MBO tick data to detect
institutional order flow patterns (iceberg orders, liquidity sweeps, dark pool prints)
and generates momentum signals from ensemble predictions. This engine activates primarily
during trending regimes (S₁) as identified by the HMM-GARCH regime detector.

## Feature Engineering from MBO Data

### Tier 1: Raw Order Flow Features

These features are computed directly from MBO tick data with strict PiT compliance:

```python
@njit(cache=True)
def compute_ofi(prices: np.ndarray, bid_qty: np.ndarray, ask_qty: np.ndarray,
                bid_price: np.ndarray, ask_price: np.ndarray) -> np.ndarray:
    """
    Order Flow Imbalance (OFI) — measures net buying/selling pressure.
    
    OFI_t = ΔBid_t - ΔAsk_t
    where ΔBid_t = bid_qty_t·I(bid_price_t ≥ bid_price_{t-1}) - bid_qty_{t-1}·I(bid_price_t ≤ bid_price_{t-1})
    
    PiT: Uses data at t and t-1, signal applied at t+1 via external .shift(1)
    """
    n = len(prices)
    ofi = np.zeros(n)
    
    for t in range(1, n):
        # Bid side contribution
        if bid_price[t] >= bid_price[t-1]:
            delta_bid = bid_qty[t]
        elif bid_price[t] < bid_price[t-1]:
            delta_bid = -bid_qty[t-1]
        else:
            delta_bid = bid_qty[t] - bid_qty[t-1]
        
        # Ask side contribution
        if ask_price[t] <= ask_price[t-1]:
            delta_ask = ask_qty[t]
        elif ask_price[t] > ask_price[t-1]:
            delta_ask = -ask_qty[t-1]
        else:
            delta_ask = ask_qty[t] - ask_qty[t-1]
        
        ofi[t] = delta_bid - delta_ask
    
    return ofi
```

### Tier 2: Derived Microstructure Features

```python
FEATURE_DEFINITIONS = {
    # Volume-synchronized probability of informed trading
    'vpin': {
        'formula': 'VPIN = |V_buy - V_sell| / (V_buy + V_sell) over volume buckets',
        'window': '50 volume bars',
        'pit_shift': True
    },
    
    # Trade flow toxicity (Kyle's lambda proxy)
    'kyle_lambda': {
        'formula': 'λ = ΔP / ΔOF  (price impact per unit of order flow)',
        'window': 'rolling 100 ticks',
        'pit_shift': True
    },
    
    # Book depth imbalance at N levels
    'depth_imbalance_L5': {
        'formula': 'DI = (Σbid_qty[1:5] - Σask_qty[1:5]) / (Σbid_qty[1:5] + Σask_qty[1:5])',
        'window': 'instantaneous (snapshot)',
        'pit_shift': True
    },
    
    # Weighted mid-price pressure
    'microprice': {
        'formula': 'MP = (ask_price · bid_qty + bid_price · ask_qty) / (bid_qty + ask_qty)',
        'window': 'instantaneous',
        'pit_shift': True
    },
    
    # Order arrival rate asymmetry
    'arrival_imbalance': {
        'formula': 'AI = (N_buy_orders - N_sell_orders) / (N_buy + N_sell) per time bucket',
        'window': '1-second buckets, rolling 60s',
        'pit_shift': True
    },
    
    # Large order clustering (institutional footprint)
    'large_order_ratio': {
        'formula': 'LOR = Σ(qty > Q90) / Σ(all qty)  where Q90 = 90th percentile qty',
        'window': 'rolling 500 ticks',
        'pit_shift': True
    },
    
    # Spread dynamics
    'spread_volatility': {
        'formula': 'σ(ask-bid) over rolling window',
        'window': 'rolling 200 ticks',
        'pit_shift': True
    },
    
    # Price momentum features
    'returns_1m': {'formula': 'log(P_t / P_{t-60s})', 'pit_shift': True},
    'returns_5m': {'formula': 'log(P_t / P_{t-300s})', 'pit_shift': True},
    'returns_15m': {'formula': 'log(P_t / P_{t-900s})', 'pit_shift': True},
    
    # Volatility features
    'realized_vol_5m': {'formula': 'sqrt(Σ r²_1s) over 5min', 'pit_shift': True},
    'vol_of_vol': {'formula': 'rolling std of realized_vol_5m', 'pit_shift': True},
}
```

### Tier 3: Iceberg Order Detection Features

Iceberg orders are large institutional orders that display only a small visible portion.
Detection heuristics:

```python
@njit(cache=True)
def detect_iceberg_signatures(
    order_ids: np.ndarray,
    qtys: np.ndarray,
    actions: np.ndarray,  # 0=new, 1=modify, 2=delete, 3=trade
    prices: np.ndarray,
    timestamps: np.ndarray
) -> np.ndarray:
    """
    Detect iceberg order footprints from MBO data.
    
    Iceberg signature: same price level shows repeated new orders of similar size
    immediately after a trade depletes the visible quantity.
    
    Pattern: [Order at P, qty=Q] → [Trade, qty=Q fills] → [New order at P, qty≈Q] → repeat
    """
    n = len(order_ids)
    iceberg_score = np.zeros(n)
    
    # Track replenishment patterns at each price level
    # Simplified: look for sequences of fill-then-replace at same price
    for t in range(2, n):
        if actions[t] == 0:  # New order
            # Check if previous action at this price was a trade (fill)
            if (actions[t-1] == 3 and 
                abs(prices[t] - prices[t-1]) < 1e-10 and
                abs(qtys[t] - qtys[t-1]) / max(qtys[t], 1) < 0.2):  # Similar qty
                # Time gap must be small (< 100ms = automated replenishment)
                if timestamps[t] - timestamps[t-1] < 100_000_000:  # 100ms in ns
                    iceberg_score[t] = 1.0
    
    return iceberg_score
```

## Model Architecture

### Ensemble Design

Two homogeneous base models, combined via simple averaging (not stacking — avoids
overfitting on small alpha signals):

```
Model 1: XGBoost (gradient boosted trees)
  - Objective: binary:logistic (predict P(up move in next N bars))
  - n_estimators: 500
  - max_depth: 6
  - learning_rate: 0.01
  - subsample: 0.8
  - colsample_bytree: 0.8
  - min_child_weight: 100 (prevent overfitting to noise)
  - reg_alpha: 0.1 (L1 regularization)
  - reg_lambda: 1.0 (L2 regularization)
  
Model 2: Random Forest
  - n_estimators: 1000
  - max_depth: 8
  - min_samples_leaf: 50
  - max_features: 'sqrt'
  - class_weight: 'balanced' (handle imbalanced up/down classes)

Ensemble:
  P_ensemble = 0.5 · P_xgboost + 0.5 · P_rf
  Signal: Long if P_ensemble > 0.55, Short if P_ensemble < 0.45, Flat otherwise
```

### Walk-Forward Optimization

NEVER use standard train/test split for financial time series. Use expanding window
walk-forward:

```
Window structure (daily retraining):
  Train: [T-504, T-1]    (2 years of history, PiT compliant)
  Validate: [T-63, T-1]   (last 3 months of train, for early stopping)
  Test: [T, T+21]         (next month, out-of-sample)
  
  Advance T by 21 days, retrain, repeat.

Purge gap: Remove 5 bars between train and test to prevent label leakage
Embargo: Do not use test-period features as training features in subsequent windows
```

### Feature Importance and Selection

```python
import shap

def compute_feature_importance(model, X_test, feature_names):
    """SHAP-based feature importance for model interpretability."""
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)
    
    importance = np.abs(shap_values).mean(axis=0)
    ranked = sorted(zip(feature_names, importance), key=lambda x: -x[1])
    
    # Drop features with near-zero SHAP values (noise)
    significant = [(name, imp) for name, imp in ranked if imp > 0.001]
    
    return significant
```

### Overfitting Safeguards

1. **Minimum leaf samples**: XGB min_child_weight=100, RF min_samples_leaf=50
2. **Feature count cap**: Maximum 20 features in production model
3. **Regularization**: L1+L2 on XGBoost, max_features='sqrt' on RF
4. **Walk-forward only**: No in-sample optimization, no future data leakage
5. **Purge + embargo**: Temporal gap between train/test windows
6. **Ensemble averaging**: Reduces variance of any single model's overfit
7. **Regime gating**: Model only trades in trending regime (prevents noise trading)

## Implementation Structure

```
./alpha-engine/ml_momentum/
  __init__.py
  features/
    __init__.py
    ofi.py              (Order Flow Imbalance)
    vpin.py             (Volume-sync informed trading prob)
    depth.py            (Book depth features)
    iceberg.py          (Iceberg order detection)
    momentum.py         (Price momentum features)
    builder.py          (Feature matrix assembly with PiT)
  models/
    __init__.py
    xgboost_model.py    (XGBoost wrapper with walk-forward)
    rf_model.py         (Random Forest wrapper)
    ensemble.py         (Averaging ensemble)
    walk_forward.py     (Walk-forward train/test splitter)
  evaluation/
    __init__.py
    shap_analysis.py    (Feature importance)
    performance.py      (Sharpe, IC, hit rate metrics)
  tests/
    test_features.py
    test_walk_forward.py
    test_iceberg.py
    test_pit.py
```

Read `prompts/` for tool-specific implementation prompts.
