"""Direct unit tests for OnlineRegimeFilter.update() — Plan 03-10."""

from __future__ import annotations

import numpy as np
import pytest

from src.alpha.regime.online_filter import OnlineRegimeFilter
from src.alpha.signal_types import RegimeState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fitted_filter(synthetic_returns: np.ndarray) -> OnlineRegimeFilter:
    """Return a ready OnlineRegimeFilter backed by a real fitted HMMGARCHRegimeDetector."""
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    return OnlineRegimeFilter(detector)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_update_returns_regime_and_confidence(
    fitted_filter: OnlineRegimeFilter,
) -> None:
    """update() must return a (RegimeState, float) tuple with confidence in [0, 1]."""
    result = fitted_filter.update(0.001)

    assert isinstance(result, tuple), "update() must return a tuple"
    assert len(result) == 2, "tuple must have exactly 2 elements"

    regime, confidence = result
    assert isinstance(regime, RegimeState), f"first element must be RegimeState, got {type(regime)}"
    assert isinstance(confidence, float), f"second element must be float, got {type(confidence)}"
    assert 0.0 <= confidence <= 1.0, f"confidence {confidence} not in [0, 1]"


def test_update_multiple_bars_state_probs_sum_to_one(
    synthetic_returns: np.ndarray,
) -> None:
    """state_probs must sum to 1.0 after every update() call (within 1e-10)."""
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    filt = OnlineRegimeFilter(detector)

    for r in synthetic_returns[:50]:
        filt.update(float(r))
        prob_sum = filt.state_probs.sum()
        assert abs(prob_sum - 1.0) < 1e-10, (
            f"state_probs sum {prob_sum} deviates from 1.0 by {abs(prob_sum - 1.0)}"
        )


def test_reset_restores_initial_state(
    synthetic_returns: np.ndarray,
) -> None:
    """reset() must restore state_probs to the detector's startprob_."""
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    filt = OnlineRegimeFilter(detector)

    # Advance the filter 10 steps to change internal state
    for r in synthetic_returns[:10]:
        filt.update(float(r))

    # After 10 updates, state_probs should differ from startprob_
    assert not np.allclose(filt.state_probs, detector.startprob_, atol=1e-10), (
        "Expected state_probs to differ from startprob_ after 10 updates"
    )

    # Reset must restore to startprob_
    filt.reset()
    np.testing.assert_allclose(
        filt.state_probs,
        detector.startprob_,
        atol=1e-10,
        err_msg="reset() did not restore state_probs to detector.startprob_",
    )


def test_log_space_fallback_does_not_crash(
    synthetic_returns: np.ndarray,
) -> None:
    """Extreme return value triggering emission underflow must not raise.

    A return of 100.0 makes exp(log_b) ≈ 0 for all states (sigma2 is small),
    causing alpha_new.sum() == 0 and triggering _log_space_forward fallback.
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    filt = OnlineRegimeFilter(detector)

    # Feed extreme return — should not raise any exception
    try:
        regime, confidence = filt.update(100.0)
    except Exception as exc:
        pytest.fail(f"update(100.0) raised unexpectedly: {exc}")

    # Result must still be valid
    assert isinstance(regime, RegimeState)
    assert 0.0 <= confidence <= 1.0
    assert abs(filt.state_probs.sum() - 1.0) < 1e-10


def test_update_advances_garch_variance(
    synthetic_returns: np.ndarray,
) -> None:
    """After update(), _sigma2 must differ from the initial unconditional variances.

    The GARCH recursion σ²_j ← ω + α·ε² + β·σ²_j must be applied every bar.
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    detector = HMMGARCHRegimeDetector(n_states=3, random_state=0)
    detector.fit(synthetic_returns)
    filt = OnlineRegimeFilter(detector)

    initial_sigma2 = np.array(
        [p.unconditional_variance for p in detector.garch_params],
        dtype=np.float64,
    )

    filt.update(0.01)

    # At least one state's variance should have moved
    assert not np.allclose(filt._sigma2, initial_sigma2, rtol=1e-10), (
        "GARCH variance did not advance after update()"
    )
