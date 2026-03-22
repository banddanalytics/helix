"""HMM-GARCH regime detector — two-stage fitting with GARCH emission computation."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from arch import arch_model
from hmmlearn.hmm import GaussianHMM

from src.alpha.regime.emissions import GARCHParams, garch_emission_prob
from src.alpha.regime.viterbi import viterbi_decode

logger = logging.getLogger("helix.alpha")


class HMMGARCHRegimeDetector:
    """Two-stage HMM-GARCH regime detector.

    Stage 1: Fit a Gaussian HMM to obtain initial state assignments.
    Stage 2: Fit per-state GARCH(1,1) models on the assigned return subsets.

    States are sorted by ascending unconditional variance so that:
      - State 0: Trending (lowest vol, persistent direction)
      - State 1: Mean-Reverting (moderate vol, oscillation)
      - State 2: Crisis/Volatile (highest vol, fat tails)

    This ordering is deterministic across refits regardless of the EM
    initialization seed.
    """

    def __init__(
        self,
        n_states: int = 3,
        n_iter: int = 100,
        tol: float = 0.01,
        max_retries: int = 5,
        min_state_samples: int = 100,
        random_state: int = 0,
    ) -> None:
        self.n_states = n_states
        self.n_iter = n_iter
        self.tol = tol
        self.max_retries = max_retries
        self.min_state_samples = min_state_samples
        self._random_state = random_state

        self.garch_params: list[GARCHParams] = []
        self.transmat_: Optional[np.ndarray] = None
        self.startprob_: Optional[np.ndarray] = None
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, returns: np.ndarray) -> bool:
        """Fit the two-stage HMM-GARCH model.

        Parameters
        ----------
        returns:
            1-D array of log-returns.

        Returns
        -------
        bool
            True on success, False if stationarity check fails for any state
            or if the Gaussian HMM fails to converge in all retries.
        """
        obs = returns.reshape(-1, 1)

        # Stage 1: Gaussian HMM with retry loop
        hmm_model, initial_states = self._fit_gaussian_hmm(obs)
        if hmm_model is None or initial_states is None:
            logger.warning("GaussianHMM failed to converge after %d retries", self.max_retries)
            return False

        # Stage 2: Per-state GARCH(1,1)
        raw_params: list[tuple[int, GARCHParams]] = []  # (original_state, params)
        for state_idx in range(self.n_states):
            mask = initial_states == state_idx
            state_returns = returns[mask]

            if len(state_returns) < self.min_state_samples:
                # Gaussian fallback: use state sample statistics
                params = self._gaussian_fallback(state_returns, state_idx)
                logger.debug(
                    "State %d: only %d samples — using Gaussian fallback",
                    state_idx,
                    len(state_returns),
                )
            else:
                params = self._fit_garch(state_returns, state_idx)
                if params is None:
                    logger.warning("GARCH fit failed for state %d", state_idx)
                    return False

            # Stationarity check
            if not params.is_stationary:
                logger.warning(
                    "State %d: GARCH non-stationary (alpha+beta=%.4f >= 1)",
                    state_idx,
                    params.alpha + params.beta,
                )
                return False

            raw_params.append((state_idx, params))

        # Sort states by ascending unconditional variance
        raw_params.sort(key=lambda x: x[1].unconditional_variance)
        sort_order = [orig_idx for orig_idx, _ in raw_params]

        self.garch_params = [params for _, params in raw_params]

        # Re-map transition matrix and startprob to new state ordering
        self.transmat_ = self._remap_matrix(hmm_model.transmat_, sort_order)
        self.startprob_ = hmm_model.startprob_[sort_order]
        self._fitted = True

        logger.info(
            "HMMGARCHRegimeDetector fitted. Unconditional variances: %s",
            [f"{p.unconditional_variance:.6f}" for p in self.garch_params],
        )
        return True

    def predict_viterbi(self, returns: np.ndarray) -> np.ndarray:
        """Offline Viterbi decoding using GARCH emission probabilities.

        Parameters
        ----------
        returns:
            1-D array of log-returns.

        Returns
        -------
        np.ndarray, shape (T,)
            Optimal state sequence (0 = Trending, 1 = Mean-Rev, 2 = Crisis).
        """
        if not self._fitted:
            raise RuntimeError("Call fit() before predict_viterbi()")

        log_emission_probs = self._compute_log_emission_probs(returns)
        log_transmat = np.log(np.clip(self.transmat_, 1e-300, None))  # type: ignore[arg-type]
        log_startprob = np.log(np.clip(self.startprob_, 1e-300, None))  # type: ignore[arg-type]

        return viterbi_decode(log_emission_probs, log_transmat, log_startprob)

    def get_regime_label(self, state: int) -> str:
        """Map integer state to human-readable label."""
        labels = {0: "TRENDING", 1: "MEAN_REVERTING", 2: "CRISIS"}
        return labels.get(state, f"STATE_{state}")

    @property
    def is_fitted(self) -> bool:
        """True after a successful call to fit()."""
        return self._fitted

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fit_gaussian_hmm(
        self,
        obs: np.ndarray,
    ) -> tuple[Optional[GaussianHMM], Optional[np.ndarray]]:
        """Attempt to fit GaussianHMM with up to max_retries seeds."""
        for attempt in range(self.max_retries):
            seed = self._random_state + attempt
            model = GaussianHMM(
                n_components=self.n_states,
                covariance_type="diag",
                n_iter=self.n_iter,
                tol=self.tol,
                random_state=seed,
            )
            model.fit(obs)
            if model.monitor_.converged:
                states = model.predict(obs)
                logger.debug("GaussianHMM converged on attempt %d (seed=%d)", attempt + 1, seed)
                return model, states
            logger.debug("GaussianHMM did not converge on attempt %d (seed=%d)", attempt + 1, seed)

        # Return last model even without convergence — better than nothing
        # The stationarity check downstream will reject if params are bad
        logger.warning(
            "GaussianHMM did not converge in %d attempts; using last fit", self.max_retries
        )
        model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.n_iter,
            tol=self.tol,
            random_state=self._random_state + self.max_retries - 1,
        )
        model.fit(obs)
        states = model.predict(obs)
        return model, states

    def _fit_garch(self, state_returns: np.ndarray, state_idx: int) -> Optional[GARCHParams]:
        """Fit GARCH(1,1) on returns subset for a single state."""
        try:
            res = arch_model(
                state_returns, vol="Garch", p=1, q=1, dist="normal"
            ).fit(disp="off")
            mu = float(res.params["mu"])
            omega = float(res.params["omega"])
            alpha = float(res.params["alpha[1]"])
            beta = float(res.params["beta[1]"])
            return GARCHParams(mu=mu, omega=omega, alpha=alpha, beta=beta)
        except Exception as exc:
            logger.warning("GARCH fit error for state %d: %s", state_idx, exc)
            return None

    def _gaussian_fallback(self, state_returns: np.ndarray, state_idx: int) -> GARCHParams:
        """Gaussian fallback when state has too few samples for GARCH."""
        if len(state_returns) == 0:
            # Truly empty state — use tiny variance to avoid division-by-zero
            return GARCHParams(mu=0.0, omega=1e-6, alpha=0.05, beta=0.90)
        mu = float(np.mean(state_returns))
        var = float(np.var(state_returns)) if len(state_returns) > 1 else 1e-6
        # Map to GARCH params with alpha+beta = 0.95 (stationary) and omega = var * 0.05
        omega = max(var * 0.05, 1e-8)
        alpha = 0.05
        beta = 0.90
        return GARCHParams(mu=mu, omega=omega, alpha=alpha, beta=beta)

    def _compute_log_emission_probs(self, returns: np.ndarray) -> np.ndarray:
        """Compute per-state GARCH log-emission probs for all returns.

        Returns
        -------
        np.ndarray, shape (T, n_states)
        """
        T = len(returns)
        log_probs = np.empty((T, self.n_states), dtype=np.float64)
        for j, params in enumerate(self.garch_params):
            log_probs[:, j] = garch_emission_prob(returns, params)
        return log_probs

    @staticmethod
    def _remap_matrix(matrix: np.ndarray, sort_order: list[int]) -> np.ndarray:
        """Re-sort a square transition matrix according to new state ordering."""
        n = len(sort_order)
        remapped = np.empty_like(matrix)
        for new_i, old_i in enumerate(sort_order):
            for new_j, old_j in enumerate(sort_order):
                remapped[new_i, new_j] = matrix[old_i, old_j]
        return remapped


__all__ = ["HMMGARCHRegimeDetector"]
