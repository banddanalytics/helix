"""GARCH emission PDF computation for HMM-GARCH regime detector."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GARCHParams:
    """GARCH(1,1) parameters for a single HMM state.

    Fields follow the arch library naming convention:
      - mu:    conditional mean
      - omega: long-run variance constant (ω > 0)
      - alpha: ARCH term coefficient (α >= 0)
      - beta:  GARCH term coefficient (β >= 0)

    Stationarity requires alpha + beta < 1.
    """

    mu: float
    omega: float
    alpha: float
    beta: float

    @property
    def unconditional_variance(self) -> float:
        """Long-run (unconditional) variance = omega / (1 - alpha - beta).

        Only valid when is_stationary is True.
        """
        return self.omega / (1.0 - self.alpha - self.beta)

    @property
    def is_stationary(self) -> bool:
        """True iff alpha + beta < 1 (finite unconditional variance)."""
        return self.alpha + self.beta < 1.0


def garch_emission_prob(
    returns: np.ndarray,
    params: GARCHParams,
) -> np.ndarray:
    """Compute GARCH(1,1) conditional log-emission probabilities.

    For each time step t, the conditional variance σ²_t follows the recursion:

        σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1},   ε_t = r_t - μ

    Initialized at the unconditional variance: σ²_0 = ω / (1 - α - β).

    Returns log-emission log-probabilities:

        log b(r_t) = -0.5 * (log(2π) + log(σ²_t) + ε²_t / σ²_t)

    Parameters
    ----------
    returns:
        1-D array of log-returns (shape T).
    params:
        Fitted GARCH(1,1) parameters for this state.

    Returns
    -------
    log_probs : np.ndarray, shape (T,)
        Log-emission probabilities under the GARCH(1,1) model.
    """
    T = len(returns)
    log_probs = np.empty(T, dtype=np.float64)

    mu = params.mu
    omega = params.omega
    alpha = params.alpha
    beta = params.beta

    # Initialise conditional variance at unconditional variance
    sigma2 = params.unconditional_variance

    log_2pi = math.log(2.0 * math.pi)

    for t in range(T):
        eps = returns[t] - mu
        eps2 = eps * eps

        # Emission log-prob at current sigma2
        log_probs[t] = -0.5 * (log_2pi + math.log(sigma2) + eps2 / sigma2)

        # Update variance for next step
        sigma2 = omega + alpha * eps2 + beta * sigma2

    return log_probs


__all__ = ["GARCHParams", "garch_emission_prob"]
