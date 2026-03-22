"""Forward-only real-time regime filter for HMM-GARCH regime detector."""

from __future__ import annotations

import math

import numpy as np

from src.alpha.regime.emissions import garch_emission_prob
from src.alpha.signal_types import RegimeState


class OnlineRegimeFilter:
    """Forward-algorithm regime filter for real-time (causal) prediction.

    Maintains a running forward variable α_t (normalized state probabilities)
    and per-state GARCH conditional variances.  On each bar, a single
    `update()` call advances the filter one step without any backward pass.

    This is suitable for live trading where future data is unavailable.

    Parameters
    ----------
    detector:
        A fitted HMMGARCHRegimeDetector providing GARCH parameters,
        transition matrix, and start probabilities.
    """

    def __init__(self, detector: "HMMGARCHRegimeDetector") -> None:  # type: ignore[name-defined]
        from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

        if not isinstance(detector, HMMGARCHRegimeDetector):
            raise TypeError("detector must be a HMMGARCHRegimeDetector instance")
        if not detector.is_fitted:
            raise RuntimeError("detector must be fitted before creating OnlineRegimeFilter")

        self._detector = detector
        self._n_states = detector.n_states

        # Initialise forward variable and per-state conditional variances
        self._alpha: np.ndarray = detector.startprob_.copy()
        self._sigma2: np.ndarray = np.array(
            [p.unconditional_variance for p in detector.garch_params],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, return_value: float) -> tuple[RegimeState, float]:
        """Advance filter by one observation.

        Implements the forward algorithm step:
          1. Compute emission probabilities using per-state GARCH(1,1) variance
          2. Propagate forward variable: α̂_j = Σ_i α_{t-1,i} · A_{ij} · b_j(r_t)
          3. Normalize to prevent underflow
          4. Update per-state conditional variance: σ²_j ← ω_j + α_j·ε²_j + β_j·σ²_j

        Parameters
        ----------
        return_value:
            The current bar's log-return.

        Returns
        -------
        (regime, confidence)
            regime: Most probable current regime state (RegimeState enum).
            confidence: Probability of most probable state after normalization.
        """
        params_list = self._detector.garch_params
        transmat = self._detector.transmat_  # (n_states, n_states)

        # Step 1: compute emission probs under current sigma2
        emission_probs = np.empty(self._n_states, dtype=np.float64)
        log_2pi = math.log(2.0 * math.pi)
        for j, params in enumerate(params_list):
            eps = return_value - params.mu
            eps2 = eps * eps
            sigma2_j = self._sigma2[j]
            log_b = -0.5 * (log_2pi + math.log(sigma2_j) + eps2 / sigma2_j)
            emission_probs[j] = math.exp(log_b)

        # Step 2: forward step — α_new[j] = b_j(r) * Σ_i α[i] * A[i,j]
        alpha_new = emission_probs * (self._alpha @ transmat)  # type: ignore[operator]

        # Step 3: normalize (guard against underflow by working in log-space fallback)
        total = alpha_new.sum()
        if total > 0.0:
            alpha_new /= total
        else:
            # Numerical underflow fallback: use log-space forward step
            alpha_new = self._log_space_forward(return_value)

        self._alpha = alpha_new

        # Step 4: update per-state conditional variances
        for j, params in enumerate(params_list):
            eps = return_value - params.mu
            eps2 = eps * eps
            self._sigma2[j] = params.omega + params.alpha * eps2 + params.beta * self._sigma2[j]

        best_state = int(np.argmax(self._alpha))
        confidence = float(self._alpha[best_state])

        return RegimeState(best_state), confidence

    def reset(self) -> None:
        """Re-initialize filter to start conditions."""
        self._alpha = self._detector.startprob_.copy()
        self._sigma2 = np.array(
            [p.unconditional_variance for p in self._detector.garch_params],
            dtype=np.float64,
        )

    @property
    def state_probs(self) -> np.ndarray:
        """Current normalized forward variable (state probabilities), shape (n_states,)."""
        return self._alpha.copy()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_space_forward(self, return_value: float) -> np.ndarray:
        """Log-space forward step for numerical underflow fallback."""
        params_list = self._detector.garch_params
        transmat = self._detector.transmat_  # type: ignore[union-attr]

        log_2pi = math.log(2.0 * math.pi)
        log_alpha_prev = np.log(np.clip(self._alpha, 1e-300, None))

        log_alpha_new = np.empty(self._n_states, dtype=np.float64)
        for j, params in enumerate(params_list):
            eps = return_value - params.mu
            eps2 = eps * eps
            sigma2_j = self._sigma2[j]
            log_b_j = -0.5 * (log_2pi + math.log(sigma2_j) + eps2 / sigma2_j)
            # log Σ_i exp(log_alpha_prev[i] + log(transmat[i, j]))
            log_trans_j = np.log(np.clip(transmat[:, j], 1e-300, None))
            log_sum = np.logaddexp.reduce(log_alpha_prev + log_trans_j)
            log_alpha_new[j] = log_b_j + log_sum

        # Normalize in log-space (subtract max for stability, then softmax)
        log_alpha_new -= log_alpha_new.max()
        alpha_new = np.exp(log_alpha_new)
        alpha_new /= alpha_new.sum()
        return alpha_new


__all__ = ["OnlineRegimeFilter"]
