"""Tier 4: 4 cross-asset correlation features in pure pandas.

IMPORTANT: This module intentionally does NOT use @njit — pandas rolling
corr/std are not Numba-compatible (per RESEARCH Pitfall 4).

All features apply .shift(1) internally for PiT compliance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Pairs whose return is already expressed as USD appreciation:
#   USD appreciates when USDJPY/USDCHF rises (direct USD pair)
#   USD depreciates when EURUSD/GBPUSD/AUDUSD/NZDUSD rises (inverted)
_USD_DIRECT = {"USDJPY", "USDCHF"}
_USD_INVERTED = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}


def compute_cross_asset_features(
    cross_asset_data: dict[str, pd.DataFrame],
    target_symbol: str,  # noqa: ARG001  (kept for API symmetry — unused here)
) -> pd.DataFrame:
    """Compute 4 cross-asset features for the target symbol's bars.

    Parameters
    ----------
    cross_asset_data : dict[str, pd.DataFrame]
        Mapping of symbol -> DataFrame with a ``close`` column.
        Expected symbols: EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCHF.
    target_symbol : str
        The symbol being modelled (used for API symmetry; all 4 features are
        market-wide, not pair-specific).

    Returns
    -------
    pd.DataFrame
        Same index as the longest series in cross_asset_data, with columns:
        - ``usd_strength``       : 5-bar MA of mean USD-appreciation return
        - ``risk_appetite``      : 10-bar MA of (AUD return + inverted JPY return)
        - ``eur_gbp_corr``       : 20-bar rolling correlation of EURUSD/GBPUSD returns
        - ``momentum_dispersion``: std of 20-bar momentum across all 6 pairs

        All columns are .shift(1) applied (PiT compliant).
    """
    # Build returns DataFrame — one column per available symbol
    returns: dict[str, pd.Series] = {}
    for sym, df in cross_asset_data.items():
        if "close" not in df.columns:
            continue
        r = df["close"].pct_change()
        if sym in _USD_INVERTED:
            r = -r  # flip so positive = USD appreciation
        returns[sym] = r

    ret_df = pd.DataFrame(returns)

    # -----------------------------------------------------------------------
    # 1. USD strength: mean of all available USD-centric returns, 5-bar MA
    # -----------------------------------------------------------------------
    # Use all available symbols as a proxy for USD strength
    usd_raw = ret_df.mean(axis=1)
    usd_strength = usd_raw.rolling(5, min_periods=1).mean().shift(1)

    # -----------------------------------------------------------------------
    # 2. Risk appetite: AUD return + inverted JPY return, 10-bar MA
    # -----------------------------------------------------------------------
    aud_ret = returns.get("AUDUSD", pd.Series(0.0, index=ret_df.index))
    # JPY: USDJPY return is already inverted above, so positive = JPY weakness
    # Risk appetite = AUD + JPY weakness = both pro-risk
    jpy_ret = returns.get("USDJPY", pd.Series(0.0, index=ret_df.index))
    risk_raw = aud_ret + jpy_ret
    risk_appetite = risk_raw.rolling(10, min_periods=1).mean().shift(1)

    # -----------------------------------------------------------------------
    # 3. EUR/GBP correlation: 20-bar rolling corr of EURUSD vs GBPUSD returns
    # -----------------------------------------------------------------------
    eur_ret_raw = (
        cross_asset_data["EURUSD"]["close"].pct_change()
        if "EURUSD" in cross_asset_data
        else pd.Series(np.nan, index=ret_df.index)
    )
    gbp_ret_raw = (
        cross_asset_data["GBPUSD"]["close"].pct_change()
        if "GBPUSD" in cross_asset_data
        else pd.Series(np.nan, index=ret_df.index)
    )
    eur_gbp_corr = eur_ret_raw.rolling(20, min_periods=10).corr(gbp_ret_raw).shift(1)

    # -----------------------------------------------------------------------
    # 4. Momentum dispersion: std of 20-bar cumulative return across all pairs
    # -----------------------------------------------------------------------
    mom_20 = pd.DataFrame(
        {
            sym: cross_asset_data[sym]["close"].pct_change(20)
            for sym in cross_asset_data
            if "close" in cross_asset_data[sym].columns
        }
    )
    momentum_dispersion = mom_20.std(axis=1).shift(1)

    result = pd.DataFrame(
        {
            "usd_strength": usd_strength,
            "risk_appetite": risk_appetite,
            "eur_gbp_corr": eur_gbp_corr,
            "momentum_dispersion": momentum_dispersion,
        }
    )
    return result
