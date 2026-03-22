"""Cost-adjusted performance metrics for ML price momentum strategy.

Computes gross vs. net Sharpe ratios after accounting for spread costs.
Annualization factor: sqrt(252) for daily bars.
"""
from __future__ import annotations

import numpy as np


def gross_sharpe(returns: np.ndarray) -> float:
    """Annualised Sharpe ratio before spread/commission costs.

    Parameters
    ----------
    returns : np.ndarray
        Per-bar (or per-period) gross returns.

    Returns
    -------
    float
        Annualised Sharpe ratio.
    """
    std = max(float(np.std(returns)), 1e-10)
    return float(np.mean(returns)) / std * np.sqrt(252)


def cost_adjusted_sharpe(returns: np.ndarray, spread_costs: np.ndarray) -> float:
    """Annualised Sharpe ratio after deducting spread/commission costs.

    Parameters
    ----------
    returns : np.ndarray
        Per-bar gross returns.
    spread_costs : np.ndarray
        Per-bar spread/commission costs (positive values).

    Returns
    -------
    float
        Annualised Sharpe ratio on net returns.  Will be strictly less than
        gross_sharpe() when spread_costs are non-zero.
    """
    net_returns = returns - spread_costs
    std = max(float(np.std(net_returns)), 1e-10)
    return float(np.mean(net_returns)) / std * np.sqrt(252)
