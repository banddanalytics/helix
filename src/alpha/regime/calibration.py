"""Regime recalibration scheduler — weekly Baum-Welch + GARCH update with two-gate validation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

from src.alpha.regime.emissions import GARCHParams
from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

logger = logging.getLogger("helix.alpha")


class RecalibrationService:
    """Weekly HMM-GARCH recalibration with Dirichlet smoothing and two-gate validation.

    Gate 1 — Stationarity: Rejects refits where alpha + beta >= 1 for any state.
    Gate 2 — State Agreement: Rejects refits with <90% agreement on last 100 bars
              compared to the current active detector.

    Model swap is atomic — the pending model is only activated when apply_pending()
    is called, which should happen at the next bar boundary.
    """

    def __init__(
        self,
        detector: HMMGARCHRegimeDetector,
        config_path: str = "config/regime_calibration.yaml",
    ) -> None:
        self._detector = detector
        self._config = self._load_config(config_path)
        self._pending: Optional[HMMGARCHRegimeDetector] = None
        self._last_params: Optional[list[GARCHParams]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recalibrate(self, returns: np.ndarray) -> bool:
        """Fit a new HMM-GARCH model and validate before storing as pending.

        Parameters
        ----------
        returns:
            1-D array of log-returns (typically the last 1260 bars).

        Returns
        -------
        bool
            True if a valid pending model was stored; False if validation failed.
        """
        validation_cfg = self._config.get("recalibration", {}).get("validation", {})
        smoothing_cfg = self._config.get("recalibration", {}).get("smoothing", {})

        concentration: float = float(smoothing_cfg.get("dirichlet_concentration", 0.01))
        stationarity_threshold: float = float(validation_cfg.get("stationarity_threshold", 1.0))
        agreement_threshold: float = float(validation_cfg.get("state_agreement_threshold", 0.90))
        agreement_lookback: int = int(validation_cfg.get("agreement_lookback", 100))
        drift_threshold: float = float(validation_cfg.get("drift_warning_threshold", 0.50))

        # Create fresh detector with same hyperparameters
        new_detector = HMMGARCHRegimeDetector(
            n_states=self._detector.n_states,
            n_iter=self._detector.n_iter,
            tol=self._detector.tol,
            max_retries=self._detector.max_retries,
            min_state_samples=self._detector.min_state_samples,
        )

        # Fit the new model
        if not new_detector.fit(returns):
            logger.warning("RecalibrationService: new detector fit() returned False — rejecting")
            return False

        # Apply Dirichlet smoothing to transition matrix
        transmat = new_detector.transmat_.copy()  # type: ignore[union-attr]
        smoothed = transmat + concentration
        # Row-normalize
        row_sums = smoothed.sum(axis=1, keepdims=True)
        smoothed = smoothed / row_sums
        new_detector.transmat_ = smoothed

        # Gate 1 — Stationarity: all states must have alpha + beta < threshold
        for i, params in enumerate(new_detector.garch_params):
            ab = params.alpha + params.beta
            if ab >= stationarity_threshold:
                logger.warning(
                    "RecalibrationService: Gate 1 FAILED — state %d alpha+beta=%.4f >= %.4f",
                    i,
                    ab,
                    stationarity_threshold,
                )
                return False

        # Gate 2 — State agreement: compare old and new Viterbi on last N bars
        if self._detector.is_fitted:
            lookback = min(agreement_lookback, len(returns))
            recent_returns = returns[-lookback:]
            old_states = self._detector.predict_viterbi(recent_returns)
            new_states = new_detector.predict_viterbi(recent_returns)
            agreement = float(np.mean(old_states == new_states))
            if agreement < agreement_threshold:
                logger.warning(
                    "RecalibrationService: Gate 2 FAILED — state agreement=%.4f < %.4f",
                    agreement,
                    agreement_threshold,
                )
                return False

        # Drift warning — compare against last known parameters
        if self._last_params is not None and len(self._last_params) == len(new_detector.garch_params):
            self._check_param_drift(new_detector.garch_params, self._last_params, drift_threshold)

        # All gates passed — store pending model and update last params
        self._pending = new_detector
        self._last_params = list(new_detector.garch_params)
        logger.info("RecalibrationService: new model validated and stored as pending")
        return True

    def apply_pending(self) -> bool:
        """Atomically swap in the pending model at the next bar boundary.

        Returns
        -------
        bool
            True if a pending model was swapped in; False if nothing was pending.
        """
        if self._pending is not None:
            self._detector = self._pending
            self._pending = None
            logger.info("RecalibrationService: pending model applied")
            return True
        return False

    @property
    def has_pending(self) -> bool:
        """True if a validated model is waiting to be applied."""
        return self._pending is not None

    @property
    def detector(self) -> HMMGARCHRegimeDetector:
        """The currently active detector."""
        return self._detector

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_param_drift(
        self,
        new_params: list[GARCHParams],
        old_params: list[GARCHParams],
        threshold: float,
    ) -> None:
        """Log WARNING if any GARCH parameter drifted beyond threshold fraction."""
        fields = ("mu", "omega", "alpha", "beta")
        for state_idx, (old, new) in enumerate(zip(old_params, new_params)):
            for field in fields:
                old_val = float(getattr(old, field))
                new_val = float(getattr(new, field))
                denominator = max(abs(old_val), 1e-10)
                drift = abs(new_val - old_val) / denominator
                if drift > threshold:
                    logger.warning(
                        "RecalibrationService: Parameter drift >%.0f%% — "
                        "state=%d field=%s old=%.6f new=%.6f drift=%.4f",
                        threshold * 100,
                        state_idx,
                        field,
                        old_val,
                        new_val,
                        drift,
                    )
                    return  # Log once per recalibration call is sufficient

    @staticmethod
    def _load_config(config_path: str) -> dict:  # type: ignore[type-arg]
        """Load YAML config, returning empty dict on missing file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(
                "RecalibrationService: config file not found at %s — using defaults",
                config_path,
            )
            return {}
        with path.open() as fh:
            return yaml.safe_load(fh) or {}


__all__ = ["RecalibrationService"]
