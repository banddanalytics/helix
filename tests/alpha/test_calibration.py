"""Regime calibration tests — ALPH-03."""

from __future__ import annotations

import logging

import numpy as np
import pytest

from src.alpha.regime.calibration import RecalibrationService
from src.alpha.regime.emissions import GARCHParams
from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector


@pytest.fixture
def fitted_detector(synthetic_returns: np.ndarray) -> HMMGARCHRegimeDetector:
    """Pre-fitted HMMGARCHRegimeDetector on synthetic_returns."""
    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    ok = detector.fit(synthetic_returns)
    assert ok, "HMMGARCHRegimeDetector.fit failed during test setup"
    return detector


def test_weekly_recalibration_produces_valid_model(
    synthetic_returns: np.ndarray,
    fitted_detector: HMMGARCHRegimeDetector,
) -> None:
    """ALPH-03: Weekly Baum-Welch recalibration produces a stationarity-valid model.

    Fits the HMM-GARCH on the most recent rolling window and verifies
    the resulting model passes all stationarity gates.
    """
    service = RecalibrationService(fitted_detector)

    result = service.recalibrate(synthetic_returns)
    assert result is True, "recalibrate() should return True on valid data"
    assert service.has_pending is True

    applied = service.apply_pending()
    assert applied is True
    assert service.detector.is_fitted is True
    assert service.has_pending is False


def test_dirichlet_smoothing_no_zero_transitions(
    synthetic_returns: np.ndarray,
    fitted_detector: HMMGARCHRegimeDetector,
) -> None:
    """ALPH-03: Dirichlet smoothing ensures no transition probability is exactly 0.

    After applying concentration parameter alpha=0.01, all entries in the
    3x3 transition matrix must be > 0 to avoid absorbing states.
    """
    service = RecalibrationService(fitted_detector)
    service.recalibrate(synthetic_returns)
    service.apply_pending()

    transmat = service.detector.transmat_
    assert transmat is not None
    assert np.all(transmat > 0), (
        "Dirichlet smoothing must ensure no zero transition probability; "
        f"found zeros in:\n{transmat}"
    )


def test_parameter_drift_warning(
    synthetic_returns: np.ndarray,
    fitted_detector: HMMGARCHRegimeDetector,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALPH-03: >50% parameter drift triggers a WARNING log entry.

    When recalibrated parameters differ from previous fit by more than 50%,
    a WARNING-level message must be emitted.
    """
    service = RecalibrationService(fitted_detector)

    # First recalibration to populate _last_params
    service.recalibrate(synthetic_returns)
    service.apply_pending()

    # Patch fit to return params with extreme omega drift (100x)
    original_fit = HMMGARCHRegimeDetector.fit

    def patched_fit_drift(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> bool:
        result = original_fit(self, returns)
        if result and self.garch_params:
            old = self.garch_params[0]
            drifted = GARCHParams(
                mu=old.mu,
                omega=old.omega * 100.0,
                alpha=old.alpha,
                beta=old.beta,
            )
            if drifted.is_stationary:
                self.garch_params = [drifted] + list(self.garch_params[1:])
        return result

    with caplog.at_level(logging.WARNING, logger="helix.alpha"):
        monkeypatch.setattr(HMMGARCHRegimeDetector, "fit", patched_fit_drift)
        service.recalibrate(synthetic_returns)

    assert "drift" in caplog.text.lower(), (
        f"Expected 'drift' in WARNING log; got: {caplog.text!r}"
    )


def test_stationarity_gate_rejects_invalid(
    synthetic_returns: np.ndarray,
    fitted_detector: HMMGARCHRegimeDetector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALPH-03: Stationarity gate rejects model where alpha + beta >= 1.

    A model with at least one state violating alpha_i + beta_i < 1
    must be rejected (recalibrate returns False).
    """
    service = RecalibrationService(fitted_detector)

    original_fit = HMMGARCHRegimeDetector.fit

    def patched_fit_nonstationery(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> bool:
        result = original_fit(self, returns)
        if result and self.garch_params:
            bad = GARCHParams(mu=0.0, omega=1e-5, alpha=0.6, beta=0.5)  # alpha+beta=1.1
            self.garch_params = [bad] + list(self.garch_params[1:])
        return result

    monkeypatch.setattr(HMMGARCHRegimeDetector, "fit", patched_fit_nonstationery)

    result = service.recalibrate(synthetic_returns)
    assert result is False, "Gate 1 (stationarity) should reject alpha+beta >= 1"
    assert service.has_pending is False


def test_state_agreement_gate(
    synthetic_returns: np.ndarray,
    fitted_detector: HMMGARCHRegimeDetector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALPH-03: State agreement gate rejects recalibration with <90% agreement.

    If online predictions agree with the new model's Viterbi path on fewer
    than 90% of the validation window bars, recalibration is rejected.
    """
    service = RecalibrationService(fitted_detector)

    # First recalibrate to ensure detector is fitted (so Gate 2 can be checked)
    service.recalibrate(synthetic_returns)
    service.apply_pending()

    call_count = {"n": 0}
    original_predict = HMMGARCHRegimeDetector.predict_viterbi

    def patched_predict(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> np.ndarray:
        call_count["n"] += 1
        result = original_predict(self, returns)
        # On even calls (new detector's predict), return flipped states
        if call_count["n"] % 2 == 0:
            return (result + 1) % 3
        return result

    monkeypatch.setattr(HMMGARCHRegimeDetector, "predict_viterbi", patched_predict)

    result = service.recalibrate(synthetic_returns)
    assert result is False, "Gate 2 (state agreement) should reject <90% agreement"
    assert service.has_pending is False
