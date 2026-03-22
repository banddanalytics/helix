"""Z-score entry/exit/hard-stop signal generator for cointegrated spread."""

from __future__ import annotations

import numpy as np


class SpreadSignalGenerator:
    """Generate trading signals from spread z-scores.

    Parameters
    ----------
    entry_z:
        Z-score threshold for entering a position. Default 2.0.
    exit_z:
        Z-score threshold for exiting a position. Default 0.5.
    hard_stop_z:
        Z-score threshold for hard stop (spread divergence). Default 4.0.
    lookback:
        Rolling window for z-score computation. Default 252.
    """

    def __init__(
        self,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        hard_stop_z: float = 4.0,
        lookback: int = 252,
    ) -> None:
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.hard_stop_z = hard_stop_z
        self.lookback = lookback

    def compute_spread(
        self,
        y1: np.ndarray,
        y2: np.ndarray,
        hedge_ratio: np.ndarray,
    ) -> np.ndarray:
        """Compute the spread: y1 - hedge_ratio * y2.

        Parameters
        ----------
        y1:
            First price series (n,).
        y2:
            Second price series (n,).
        hedge_ratio:
            Rolling hedge ratio array (n,).

        Returns
        -------
        np.ndarray
            Spread series (n,).
        """
        return y1 - hedge_ratio * y2

    def compute_zscore(self, spread: np.ndarray) -> np.ndarray:
        """Compute PiT rolling z-score of the spread.

        For each bar i, z-score uses ``spread[i-lookback:i]`` — the
        current bar is not included in the mean/std estimation.

        Parameters
        ----------
        spread:
            Spread series (n,).

        Returns
        -------
        np.ndarray
            Z-score series (n,). First ``lookback`` elements are NaN.
        """
        n = len(spread)
        z = np.full(n, np.nan)
        for i in range(self.lookback, n):
            window = spread[i - self.lookback : i]
            mean = np.mean(window)
            std = np.std(window, ddof=1)
            if std > 0:
                z[i] = (spread[i] - mean) / std
            # If std == 0 leave as NaN
        return z

    def generate_signals(self, z_scores: np.ndarray) -> list[tuple[int, float]]:
        """Generate (direction, strength) signal tuples per bar.

        Signal logic:
        - Hard stop:   |z| > hard_stop_z  -> (0, 1.0)   [urgency flag]
        - Entry long:  z < -entry_z       -> (+1, strength)
        - Entry short: z > +entry_z       -> (-1, strength)
        - Flat:        |z| <= exit_z      -> (0, 0.0)
        - Otherwise:   maintain no opinion -> (0, 0.0)

        Parameters
        ----------
        z_scores:
            Z-score array (n,).

        Returns
        -------
        list[tuple[int, float]]
            List of (direction, strength) tuples, one per bar.
        """
        signals: list[tuple[int, float]] = []
        for z in z_scores:
            if np.isnan(z):
                signals.append((0, 0.0))
                continue

            abs_z = abs(z)

            if abs_z > self.hard_stop_z:
                # Hard stop — spread diverged too far
                signals.append((0, 1.0))
            elif z < -self.entry_z:
                # Entry long — spread is too low relative to history
                strength = float(min(abs_z / self.entry_z, 1.0))
                signals.append((1, strength))
            elif z > self.entry_z:
                # Entry short — spread is too high relative to history
                strength = float(min(abs_z / self.entry_z, 1.0))
                signals.append((-1, strength))
            else:
                # In flat zone or between entry_z and exit_z
                signals.append((0, 0.0))

        return signals
