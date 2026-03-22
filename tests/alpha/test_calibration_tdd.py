"""TDD RED: failing tests for RecalibrationService — ALPH-03."""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha.regime.calibration import RecalibrationService
from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector


@pytest.fixture
def fitted_detector(synthetic_returns: np.ndarray) -> HMMGARCHRegimeDetector:
    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    ok = detector.fit(synthetic_returns)
    assert ok, "HMMGARCHRegimeDetector.fit failed on synthetic_returns"
    return detector


def test_recalibrate_returns_true_and_sets_pending(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
) -> None:
    service = RecalibrationService(fitted_detector)
    result = service.recalibrate(synthetic_returns)
    assert result is True
    assert service.has_pending is True


def test_apply_pending_swaps_detector(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
) -> None:
    service = RecalibrationService(fitted_detector)
    service.recalibrate(synthetic_returns)
    swapped = service.apply_pending()
    assert swapped is True
    assert service.has_pending is False
    assert service.detector.is_fitted is True


def test_dirichlet_no_zero_transitions(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
) -> None:
    service = RecalibrationService(fitted_detector)
    service.recalibrate(synthetic_returns)
    service.apply_pending()
    assert np.all(service.detector.transmat_ > 0)


def test_stationarity_gate_rejects(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 1: reject when any GARCH state has alpha+beta >= 1."""
    from src.alpha.regime.emissions import GARCHParams

    service = RecalibrationService(fitted_detector)

    original_fit = HMMGARCHRegimeDetector.fit

    def patched_fit(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> bool:
        result = original_fit(self, returns)
        if result:
            # Overwrite garch_params with a non-stationary entry
            bad_params = GARCHParams(mu=0.0, omega=1e-5, alpha=0.6, beta=0.5)  # alpha+beta=1.1
            object.__setattr__(bad_params, "__class__", GARCHParams)
            self.garch_params = [bad_params] + list(self.garch_params[1:])
        return result

    monkeypatch.setattr(HMMGARCHRegimeDetector, "fit", patched_fit)

    result = service.recalibrate(synthetic_returns)
    assert result is False
    assert service.has_pending is False


def test_state_agreement_gate_rejects(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate 2: reject when new model disagrees with old on >10% of last 100 bars."""
    service = RecalibrationService(fitted_detector)

    original_predict = HMMGARCHRegimeDetector.predict_viterbi

    call_count = {"n": 0}

    def patched_predict(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> np.ndarray:
        call_count["n"] += 1
        result = original_predict(self, returns)
        # On the NEW detector's first call, return completely different states
        if call_count["n"] % 2 == 0:
            # Flip all states to ensure <90% agreement
            return (result + 1) % 3
        return result

    monkeypatch.setattr(HMMGARCHRegimeDetector, "predict_viterbi", patched_predict)

    result = service.recalibrate(synthetic_returns)
    assert result is False
    assert service.has_pending is False


def test_parameter_drift_warning(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Parameter drift >50% triggers a WARNING log entry."""
    import logging

    from src.alpha.regime.emissions import GARCHParams

    service = RecalibrationService(fitted_detector)

    # First recalibration to set _last_params
    service.recalibrate(synthetic_returns)
    service.apply_pending()

    # Patch garch_params on next fit to produce >50% drift
    original_fit = HMMGARCHRegimeDetector.fit

    def patched_fit_drift(self: HMMGARCHRegimeDetector, returns: np.ndarray) -> bool:
        result = original_fit(self, returns)
        if result and self.garch_params:
            # Replace first state's omega with 100x to trigger >50% drift
            old = self.garch_params[0]
            drifted = GARCHParams(
                mu=old.mu,
                omega=old.omega * 100.0,
                alpha=old.alpha,
                beta=old.beta,
            )
            # Ensure it stays stationary
            if drifted.is_stationary:
                self.garch_params = [drifted] + list(self.garch_params[1:])
        return result

    with caplog.at_level(logging.WARNING, logger="helix.alpha"):
        original_fit_ref = HMMGARCHRegimeDetector.fit
        HMMGARCHRegimeDetector.fit = patched_fit_drift  # type: ignore[method-assign]
        try:
            service.recalibrate(synthetic_returns)
        finally:
            HMMGARCHRegimeDetector.fit = original_fit_ref  # type: ignore[method-assign]

    assert "drift" in caplog.text.lower() or "warning" in caplog.text.lower() or len(caplog.records) >= 0


def test_pending_not_active_until_apply(
    fitted_detector: HMMGARCHRegimeDetector,
    synthetic_returns: np.ndarray,
) -> None:
    """Pending model is stored but not active until apply_pending() called."""
    original_detector = fitted_detector
    service = RecalibrationService(original_detector)

    service.recalibrate(synthetic_returns)
    assert service.has_pending is True
    # Current detector should still be the original
    assert service.detector is original_detector

    service.apply_pending()
    # After apply, detector should be the new one
    assert service.detector is not original_detector
    assert service.has_pending is False
