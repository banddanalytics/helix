---
name: ml-momentum-orderflow
description: >
  Stage B ONLY: Implement MBO-dependent ML momentum features that require genuine
  Market-by-Order data from CME. This skill SUPPLEMENTS ml-price-momentum — it adds
  OFI, VPIN, depth imbalance, microprice, iceberg detection, and Kyle's lambda features
  to the existing price/volume feature set. NOT active during Stage A (Forex) because
  retail brokers do not provide genuine order book data. Use this skill when transitioning
  to CME futures and need to add order flow features to the ML pipeline.
---

# ML Momentum & Orderflow Skill (Stage B Only)

## Purpose

This skill adds MBO-dependent features to the ML momentum engine when transitioning
to CME futures (Stage B). These features are NOT available from retail Forex brokers.

**Activation rule:** Only use this skill after CME MDP 3.0 data feed is operational
and ArcticDB `mbo_ticks` library contains genuine Market-by-Order data.

## Feature Engineering from MBO Data

### OFI (Order Flow Imbalance) — Cont, Kukanov, Stoikov (2014)

```python
@njit(cache=True)
def compute_ofi(bid_price: np.ndarray, ask_price: np.ndarray,
                bid_qty: np.ndarray, ask_qty: np.ndarray) -> np.ndarray:
    n = len(bid_price)
    ofi = np.zeros(n)
    for t in range(1, n):
        if bid_price[t] >= bid_price[t-1]:
            delta_bid = bid_qty[t]
        elif bid_price[t] < bid_price[t-1]:
            delta_bid = -bid_qty[t-1]
        else:
            delta_bid = bid_qty[t] - bid_qty[t-1]
        if ask_price[t] <= ask_price[t-1]:
            delta_ask = ask_qty[t]
        elif ask_price[t] > ask_price[t-1]:
            delta_ask = -ask_qty[t-1]
        else:
            delta_ask = ask_qty[t] - ask_qty[t-1]
        ofi[t] = delta_bid - delta_ask
    return ofi
```

### VPIN (Volume-Synchronized Probability of Informed Trading)

```python
@njit(cache=True)
def compute_vpin(prices: np.ndarray, volumes: np.ndarray,
                 bucket_size: float, n_buckets: int = 50) -> np.ndarray:
    """
    VPIN using Bulk Volume Classification.
    Requires REAL volume (not tick volume) — only available from CME.
    """
    n = len(prices)
    vpin = np.full(n, np.nan)
    # ... bucket-based computation using real trade volume
    return vpin
```

### Additional MBO Features

- **Depth Imbalance L1-L5**: (Σbid_qty - Σask_qty) / (Σbid_qty + Σask_qty) per level
- **Microprice**: (ask × bid_qty + bid × ask_qty) / (bid_qty + ask_qty)
- **Kyle's Lambda**: ΔP / ΔOF (price impact per unit of order flow)
- **Iceberg Detection**: fill-then-replenish patterns at same price within 100ms
- **Order Arrival Asymmetry**: (N_buy - N_sell) / (N_buy + N_sell) per time bucket
- **Large Order Ratio**: Σ(qty > Q90) / Σ(all qty) — institutional footprint

## Integration with ml-price-momentum

```python
# Stage B feature matrix = Stage A features + MBO features
stage_a_features = build_price_momentum_features(bars)  # 27 features from ml-price-momentum
stage_b_features = build_mbo_features(mbo_ticks)        # 15 features from this skill
full_feature_matrix = np.hstack([stage_a_features, stage_b_features])  # 42 features total
```

## Implementation Structure

```
./src/alpha/ml_mbo_orderflow/
  features/
    ofi.py, vpin.py, depth.py, microprice.py, iceberg.py, kyle_lambda.py
    builder.py      (Assembles MBO features, merges with price momentum features)
  tests/
    test_ofi.py, test_vpin.py, test_iceberg.py
```
