"""Cost-adjusted performance metrics for ML price momentum strategy.

Computes gross vs. net Sharpe ratios after accounting for spread costs.
Annualization factor: sqrt(bars_per_year) — configurable per bar timeframe.
"""

from __future__ import annotations

import numpy as np

_TIMEFRAME_BARS_PER_YEAR: dict[str, int] = {
    "1m": 362_880,
    "5m": 72_576,
    "15m": 24_192,
    "30m": 12_096,
    "1h": 6_048,
    "60m": 6_048,
    "4h": 1_512,
    "1d": 252,
    "daily": 252,
    "1w": 52,
    "weekly": 52,
}

SUPPORTED_TIMEFRAMES: frozenset[str] = frozenset(_TIMEFRAME_BARS_PER_YEAR)


def timeframe_to_bars_per_year(timeframe: str) -> int:
    """Convert a bar timeframe string to the number of bars per trading year.

    Assumes Forex-style 24h sessions, 5 days/week, 252 trading days/year.

    Parameters
    ----------
    timeframe : str
        Bar timeframe (e.g. ``"1h"``, ``"4h"``, ``"1d"``).
        Case-insensitive; leading/trailing whitespace stripped.

    Returns
    -------
    int
        Bars per year for the given timeframe.

    Raises
    ------
    ValueError
        If *timeframe* is not in :data:`SUPPORTED_TIMEFRAMES`.
    """
    key = timeframe.strip().lower()
    if key not in _TIMEFRAME_BARS_PER_YEAR:
        msg = (
            f"Unknown timeframe {timeframe!r}. "
            f"Supported: {sorted(SUPPORTED_TIMEFRAMES)}"
        )
        raise ValueError(msg)
    return _TIMEFRAME_BARS_PER_YEAR[key]


def gross_sharpe(returns: np.ndarray, *, bars_per_year: int = 252) -> float:
    """Annualised Sharpe ratio before spread/commission costs.

    Parameters
    ----------
    returns : np.ndarray
        Per-bar (or per-period) gross returns.
    bars_per_year : int
        Number of bars in a trading year.  Default ``252`` (daily bars).
        Use :func:`timeframe_to_bars_per_year` to derive from a timeframe
        string.

    Returns
    -------
    float
        Annualised Sharpe ratio.
    """
    std = max(float(np.std(returns)), 1e-10)
    return float(np.mean(returns)) / std * np.sqrt(bars_per_year)


def cost_adjusted_sharpe(
    returns: np.ndarray,
    spread_costs: np.ndarray,
    *,
    bars_per_year: int = 252,
) -> float:
    """Annualised Sharpe ratio after deducting spread/commission costs.

    Parameters
    ----------
    returns : np.ndarray
        Per-bar gross returns.
    spread_costs : np.ndarray
        Per-bar spread/commission costs (positive values).
    bars_per_year : int
        Number of bars in a trading year.  Default ``252`` (daily bars).
        Use :func:`timeframe_to_bars_per_year` to derive from a timeframe
        string.

    Returns
    -------
    float
        Annualised Sharpe ratio on net returns.  Will be strictly less than
        gross_sharpe() when spread_costs are non-zero.
    """
    net_returns = returns - spread_costs
    std = max(float(np.std(net_returns)), 1e-10)
    return float(np.mean(net_returns)) / std * np.sqrt(bars_per_year)
