"""Johansen cointegration trace test for Forex pair detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from statsmodels.tsa.vector_ar.vecm import coint_johansen


@dataclass(frozen=True)
class JohansenResult:
    """Result of the Johansen cointegration trace test."""

    cointegrated: bool
    trace_stat: float
    crit_95: float
    hedge_ratio: float


def test_cointegration(y1: np.ndarray, y2: np.ndarray) -> JohansenResult:
    """Run Johansen trace test on a pair of price series.

    Parameters
    ----------
    y1:
        First price series (n,) array.
    y2:
        Second price series (n,) array.

    Returns
    -------
    JohansenResult
        Cointegration flag, trace statistic, 95% critical value, and
        the hedge ratio derived from the first eigenvector.
    """
    data = np.column_stack([y1, y2])
    result = coint_johansen(data, det_order=0, k_ar_diff=1)

    trace_stat = float(result.trace_stat[0])
    crit_95 = float(result.trace_stat_crit_vals[0, 1])  # col 1 = 95% critical value

    # Normalize first eigenvector so that cointegrating relation is y1 - beta*y2.
    # evec[:,0] is the first cointegrating vector in (y1, y2) ordering.
    # beta = -evec[0,0] / evec[1,0]  gives: evec[0]*y1 + evec[1]*y2 = 0
    #   => y1 = (-evec[1,0]/evec[0,0]) * y2  -- but we want y1 - beta*y2
    #   => beta = -evec[0,0] / evec[1,0]
    hedge_ratio = float(-result.evec[0, 0] / result.evec[1, 0])

    return JohansenResult(
        cointegrated=trace_stat > crit_95,
        trace_stat=trace_stat,
        crit_95=crit_95,
        hedge_ratio=hedge_ratio,
    )
