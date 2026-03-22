"""Half-life AR(1) and cointegration breakdown detection."""

from __future__ import annotations

import numpy as np


class CointegrationHealthMonitor:
    """Monitor cointegration health via half-life and trace statistics.

    Parameters
    ----------
    hl_reduce_threshold:
        Half-life (in bars) above which position reduction is recommended.
        Default 60 bars.
    hl_close_threshold:
        Half-life (in bars) above which closing all positions is recommended.
        Default 120 bars.
    """

    def __init__(
        self,
        hl_reduce_threshold: int = 60,
        hl_close_threshold: int = 120,
    ) -> None:
        self.hl_reduce_threshold = hl_reduce_threshold
        self.hl_close_threshold = hl_close_threshold

    def compute_half_life(self, spread: np.ndarray) -> float:
        """Compute half-life via AR(1) OLS regression on the spread.

        Fits ``spread[t] = delta * spread[t-1] + epsilon`` and computes
        ``half_life = -ln(2) / ln(|delta|)``.

        Parameters
        ----------
        spread:
            Spread series (n,).

        Returns
        -------
        float
            Half-life in bars.
        """
        y = spread[1:]
        x = spread[:-1]

        # OLS via closed-form: delta = cov(x, y) / var(x)
        x_dm = x - np.mean(x)
        y_dm = y - np.mean(y)
        delta = float(np.dot(x_dm, y_dm) / np.dot(x_dm, x_dm))

        abs_delta = abs(delta)
        # Guard against non-stationary or exactly unit-root processes
        if abs_delta >= 1.0:
            return float("inf")
        if abs_delta <= 0.0:
            return 0.0

        half_life = float(-np.log(2) / np.log(abs_delta))
        return half_life

    def check_breakdown(self, trace_stat: float, crit_10: float) -> bool:
        """Return True if the trace statistic falls below the 10% critical value.

        A trace_stat < crit_10 signals that cointegration is breaking down.

        Parameters
        ----------
        trace_stat:
            Johansen trace statistic.
        crit_10:
            10% critical value for the trace test.

        Returns
        -------
        bool
            True if cointegration is breaking down.
        """
        return trace_stat < crit_10

    def assess_health(
        self,
        spread: np.ndarray,
        trace_stat: float,
        crit_10: float,
    ) -> dict[str, object]:
        """Assess overall cointegration health.

        Parameters
        ----------
        spread:
            Spread series (n,).
        trace_stat:
            Current Johansen trace statistic.
        crit_10:
            10% critical value for the trace test.

        Returns
        -------
        dict
            Keys:
            - ``half_life``: float, estimated mean-reversion half-life in bars
            - ``reduce_position``: bool, True if HL > hl_reduce_threshold
            - ``close_all``: bool, True if HL > hl_close_threshold
            - ``suspend``: bool, True if trace_stat < crit_10 (breakdown)
        """
        hl = self.compute_half_life(spread)
        return {
            "half_life": hl,
            "reduce_position": hl > self.hl_reduce_threshold,
            "close_all": hl > self.hl_close_threshold,
            "suspend": self.check_breakdown(trace_stat, crit_10),
        }
