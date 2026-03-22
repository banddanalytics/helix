"""Dynamic rolling hedge ratio using Johansen cointegration."""

from __future__ import annotations

import numpy as np

from src.alpha.cointegration.johansen import test_cointegration


class RollingHedgeRatio:
    """504-bar rolling hedge ratio computed via Johansen eigenvector.

    Parameters
    ----------
    window:
        Look-back window in bars. Default is 504 (2 years of daily bars).
    step:
        Recompute every ``step`` bars, carrying forward the previous value
        between recomputes. Default is 21 (monthly cadence for daily bars).
    """

    def __init__(self, window: int = 504, step: int = 21) -> None:
        self.window = window
        self.step = step

    def compute(self, y1: np.ndarray, y2: np.ndarray) -> np.ndarray:
        """Compute a PiT-compliant rolling hedge ratio.

        For each bar t >= window, the ratio is derived from the Johansen
        trace test on ``y1[t-window:t]`` and ``y2[t-window:t]``.
        Python's exclusive-end slice guarantees that bar t itself is
        never included in the estimation window (PiT compliant).

        Parameters
        ----------
        y1:
            First price series (n,) array.
        y2:
            Second price series (n,) array.

        Returns
        -------
        np.ndarray
            Array of shape ``(n,)`` containing hedge ratios. The first
            ``window`` elements are ``np.nan`` (insufficient data).
        """
        n = len(y1)
        ratios = np.full(n, np.nan)
        last_ratio: float | None = None

        for t in range(self.window, n):
            if (t - self.window) % self.step == 0 or last_ratio is None:
                # PiT slice: y1[t-window:t] excludes bar t
                y1_slice = y1[t - self.window : t]
                y2_slice = y2[t - self.window : t]
                last_ratio = test_cointegration(y1_slice, y2_slice).hedge_ratio
            ratios[t] = last_ratio  # type: ignore[assignment]

        return ratios
