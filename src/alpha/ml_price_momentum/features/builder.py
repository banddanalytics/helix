"""FeatureBuilder — assembles all 27 features with PiT compliance.

Architecture:
- Tiers 1/2/3/5 are @njit compiled arrays (fast, ~1M bars < 5s)
- Tier 4 is pure pandas (rolling corr/std — not Numba-compatible)
- PiT compliance is enforced inside each Numba function: feature[i] uses
  data up to index i-1 only. No additional .shift() is applied in build()
  because that would make features 2-bar stale and invert the win rate.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd


class FeatureBuilder:
    """Assemble all 27 features from 5 tiers into a single PiT-compliant DataFrame.

    Parameters
    ----------
    cross_asset_data : dict[str, pd.DataFrame] | None
        Mapping of symbol -> DataFrame with a ``close`` column for the 6
        configured pairs.  If None, Tier 4 columns are filled with NaN.
    """

    FEATURE_NAMES: ClassVar[list[str]] = [
        # Tier 1 — Momentum (8)
        "mom_1bar",
        "mom_5bar",
        "mom_10bar",
        "mom_22bar",
        "mom_63bar",
        "mom_252bar",
        "mom_accel",
        "range_expansion",
        # Tier 2 — Volatility (6)
        "vol_5bar",
        "vol_22bar",
        "vol_zscore",
        "vol_ratio",
        "parkinson_vol",
        "vol_of_vol",
        # Tier 3 — Session (5)
        "session_id",
        "bar_position",
        "relative_bar_size",
        "day_of_week",
        "dist_from_open",
        # Tier 4 — Cross-asset (4)
        "usd_strength",
        "risk_appetite",
        "eur_gbp_corr",
        "momentum_dispersion",
        # Tier 5 — Tick volume (4)
        "rel_tick_volume",
        "volume_trend",
        "price_vol_div",
        "volume_spike",
    ]

    def __init__(
        self,
        cross_asset_data: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        self._cross_asset_data = cross_asset_data

    def build(
        self,
        symbol: str,
        open_arr: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        tick_volume: np.ndarray,
        hour: np.ndarray,
        dow: np.ndarray,
    ) -> pd.DataFrame:
        """Compute all 27 features and return a PiT-compliant DataFrame.

        Parameters
        ----------
        symbol : str
            Target symbol (e.g. "EURUSD") — passed to cross-asset tier.
        open_arr, high, low, close : np.ndarray
            OHLC price arrays of shape (n,).
        tick_volume : np.ndarray
            Tick volume array of shape (n,).
        hour : np.ndarray
            Hour-of-day integer array (0-23) of shape (n,).
        dow : np.ndarray
            Day-of-week integer array (0-4) of shape (n,).

        Returns
        -------
        pd.DataFrame
            Shape (n, 27) with columns ``FEATURE_NAMES``.  All values at row i
            are derived from data at rows <= i-1 (PiT compliant, enforced by
            the Numba kernels — no extra shift applied here).
        """
        from src.alpha.ml_price_momentum.features.cross_asset import (
            compute_cross_asset_features,
        )
        from src.alpha.ml_price_momentum.features.momentum import (
            compute_momentum_features,
        )
        from src.alpha.ml_price_momentum.features.session import (
            compute_session_features,
        )
        from src.alpha.ml_price_momentum.features.tick_volume import (
            compute_tick_volume_features,
        )
        from src.alpha.ml_price_momentum.features.volatility import (
            compute_volatility_features,
        )

        n = len(close)

        # --- Tiers 1, 2, 3, 5 (Numba @njit) ---
        mom = compute_momentum_features(close, high, low)  # (n, 8)
        vol = compute_volatility_features(close, high, low)  # (n, 6)
        sess = compute_session_features(open_arr, high, low, close, hour, dow)  # (n, 5)
        tkvol = compute_tick_volume_features(close, tick_volume)  # (n, 4)

        # --- Tier 4 (pandas) ---
        if self._cross_asset_data is not None:
            ca_df = compute_cross_asset_features(self._cross_asset_data, symbol)
            # Align to n rows (reindex to positional 0..n-1 if needed)
            if len(ca_df) >= n:
                ca_arr = ca_df.values[:n]
            else:
                # Pad with NaN if cross-asset data is shorter
                pad = np.full((n - len(ca_df), 4), np.nan)
                ca_arr = np.vstack([ca_df.values, pad])
        else:
            ca_arr = np.full((n, 4), np.nan)

        # --- Assemble into (n, 27) matrix ---
        raw = np.hstack([mom, vol, sess, ca_arr, tkvol])
        df = pd.DataFrame(raw, columns=self.FEATURE_NAMES)

        # PiT compliance is already enforced inside each Numba function:
        # every feature at index i uses data from indices <= i-1 (e.g. close[i-1]).
        # A second .shift(1) here would make features 2-bar stale — the features
        # at row i would describe market state at i-2, not i-1. That misalignment
        # inverts win rate because the model trains on a feature-label gap of 3 bars
        # rather than the intended 1 bar. Do NOT add .shift(1) here.

        # Forward-fill NaN for the warmup period so downstream models get finite input
        df = df.ffill()

        return df

    def check_correlation(
        self,
        df: pd.DataFrame,
        threshold: float = 0.95,
    ) -> list[tuple[str, str, float]]:
        """Find feature pairs with |Pearson correlation| > threshold.

        Parameters
        ----------
        df : pd.DataFrame
            Feature matrix from ``build()``.
        threshold : float
            Absolute correlation threshold (default 0.95).

        Returns
        -------
        list[tuple[str, str, float]]
            List of (col_a, col_b, corr_value) for each flagged pair.
            Empty list if no pairs exceed the threshold.
        """
        # Drop rows that are all NaN (warmup rows)
        clean = df.dropna(how="all")
        if len(clean) < 10:
            return []

        corr_matrix = clean.corr()
        flagged: list[tuple[str, str, float]] = []
        cols = list(corr_matrix.columns)
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1 :]:
                val = corr_matrix.loc[col_a, col_b]
                if abs(val) > threshold:
                    flagged.append((col_a, col_b, float(val)))
        return flagged
