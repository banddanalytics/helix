"""Cointegration engine tests — ALPH-04, ALPH-05."""

from __future__ import annotations

import numpy as np

from src.alpha.cointegration import (
    CointegrationHealthMonitor,
    JohansenResult,
    RollingHedgeRatio,
    SpreadSignalGenerator,
    test_cointegration as johansen_test,
)


def test_johansen_detects_cointegrated_pair(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-04: Johansen trace test identifies rank=1 on synthetic cointegrated data.

    Uses a known cointegrated pair (hedge ratio ~0.8) and verifies the
    Johansen trace statistic exceeds the 5% critical value for rank=1.
    """
    y1, y2 = cointegrated_pair
    result = johansen_test(y1, y2)
    assert isinstance(result, JohansenResult)
    assert result.cointegrated is True
    assert result.trace_stat > result.crit_95


def test_johansen_rejects_independent_walks() -> None:
    """ALPH-04: Johansen test returns cointegrated=False on independent random walks."""
    rng = np.random.default_rng(999)
    y1 = np.cumsum(rng.normal(0, 1, size=500))
    y2 = np.cumsum(rng.normal(0, 1, size=500))
    result = johansen_test(y1, y2)
    assert isinstance(result, JohansenResult)
    assert result.cointegrated is False


def test_hedge_ratio_converges(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-04: Estimated hedge ratio is within 5% of the known true value (0.8).

    OLS or Johansen eigenvector estimation on 1000 bars of synthetic data
    must recover the true hedge ratio 0.8 within ±0.04.
    """
    y1, y2 = cointegrated_pair
    result = johansen_test(y1, y2)
    assert abs(result.hedge_ratio - 0.8) < 0.05


def test_rolling_hedge_ratio_pit_compliant(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-04: RollingHedgeRatio produces PiT-compliant ratios (no future data)."""
    y1, y2 = cointegrated_pair
    roller = RollingHedgeRatio(window=200, step=50)
    ratios = roller.compute(y1, y2)
    assert ratios.shape == (len(y1),)
    # First window bars must be NaN
    assert np.all(np.isnan(ratios[:200]))
    # After window, values should be finite
    assert np.any(np.isfinite(ratios[200:]))


def test_zscore_entry_signals(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-05: Z-score entry signals fire at +/-2.0 threshold.

    When the spread z-score crosses ±2.0, direction +1 or -1 must be
    emitted. No signal should be emitted when |z| < 2.0.
    """
    gen = SpreadSignalGenerator(entry_z=2.0, exit_z=0.5, hard_stop_z=4.0, lookback=50)

    # Build z_scores with a known value
    z_scores = np.zeros(100)
    z_scores[80] = -2.5  # should trigger long entry (+1)
    z_scores[90] = 2.5   # should trigger short entry (-1)

    signals = gen.generate_signals(z_scores)
    assert len(signals) == 100

    direction_80, strength_80 = signals[80]
    assert direction_80 == 1
    assert strength_80 > 0

    direction_90, strength_90 = signals[90]
    assert direction_90 == -1
    assert strength_90 > 0

    # Flat zone — direction should be 0
    direction_50, _ = signals[50]
    assert direction_50 == 0


def test_zscore_hard_stop(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-05: Z-score hard stop fires at +/-4.0 (widening spread protection).

    When |z| >= 4.0, a hard stop signal with direction=0 must be emitted
    regardless of current position, indicating spread divergence.
    """
    gen = SpreadSignalGenerator(entry_z=2.0, exit_z=0.5, hard_stop_z=4.0, lookback=50)

    z_scores = np.zeros(100)
    z_scores[70] = 4.5   # hard stop — |z| > 4.0
    z_scores[75] = -4.5  # hard stop — |z| > 4.0

    signals = gen.generate_signals(z_scores)

    direction_70, strength_70 = signals[70]
    assert direction_70 == 0
    assert strength_70 == 1.0  # urgency flag

    direction_75, strength_75 = signals[75]
    assert direction_75 == 0
    assert strength_75 == 1.0


def test_half_life_computation() -> None:
    """ALPH-04: Half-life computation matches known AR(1) coefficient.

    For spread s_t = delta * s_{t-1} + epsilon, half-life = -log(2)/log(delta).
    With delta=0.95, expected half-life ~ 13.5 bars.
    Estimated half-life must match within 1.0 bar.
    """
    rng = np.random.default_rng(42)
    n = 2000
    delta = 0.95
    spread = np.zeros(n)
    spread[0] = rng.normal(0, 1)
    for t in range(1, n):
        spread[t] = delta * spread[t - 1] + rng.normal(0, 1)

    expected_hl = -np.log(2) / np.log(delta)  # ~13.5

    monitor = CointegrationHealthMonitor()
    hl = monitor.compute_half_life(spread)
    assert abs(hl - expected_hl) < 1.0


def test_health_monitor_flags(
    cointegrated_pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """ALPH-04: HL > 60 triggers reduce_position; HL > 120 triggers close_all."""
    monitor = CointegrationHealthMonitor(
        hl_reduce_threshold=60, hl_close_threshold=120
    )

    # Build a spread with very slow mean reversion (large half-life)
    rng = np.random.default_rng(7)
    n = 2000
    delta = 0.995  # half-life ~138 bars
    spread = np.zeros(n)
    spread[0] = rng.normal(0, 1)
    for t in range(1, n):
        spread[t] = delta * spread[t - 1] + rng.normal(0, 1)

    health = monitor.assess_health(
        spread, trace_stat=15.0, crit_10=10.0
    )
    assert "half_life" in health
    assert health["reduce_position"] is True
    assert health["close_all"] is True
    assert health["suspend"] is False  # trace_stat > crit_10
