"""End-to-end Helix pipeline validation — Yahoo Finance -> metrics.

No ArcticDB dependency. Uses vbt.YFData.pull() for data sourcing.
Exercises: regime detection, feature building, walk-forward ML,
backtesting, cost sensitivity, and cross-pair correlation.

Run:
    python scripts/validate_pipeline.py
    python scripts/validate_pipeline.py --pairs EURUSD GBPUSD --months 18
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("helix.validate")

PAIR_TO_YF = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
}

BASE_SPREAD_PIPS = {
    "EURUSD": 0.00012,
    "GBPUSD": 0.00015,
    "AUDUSD": 0.00016,
    "NZDUSD": 0.00020,
    "USDJPY": 0.012,
    "USDCHF": 0.00015,
}

COST_MULTIPLIERS = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]


def pull_data(pairs: list[str], months: int) -> dict[str, pd.DataFrame]:
    """Pull hourly OHLCV data from Yahoo Finance via VectorBT Pro."""
    import vectorbtpro as vbt

    end = datetime.now(tz=UTC)
    start = end - timedelta(days=months * 30)

    yf_symbols = [PAIR_TO_YF[p] for p in pairs]
    print(f"\n{'=' * 60}")
    print(f"  Pulling {months} months of 1H data for {pairs}")
    print(f"  Range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    print(f"{'=' * 60}\n")

    data = vbt.YFData.pull(
        symbols=yf_symbols,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        timeframe="1h",
        tz="UTC",
    )

    result = {}
    for pair, yf_sym in zip(pairs, yf_symbols, strict=True):
        ohlc = data.select_symbols(yf_sym).get()
        ohlc = ohlc.dropna(subset=["Close"])
        result[pair] = ohlc
        print(f"  {pair}: {len(ohlc)} bars loaded")

    return result


def compute_metrics(
    equity: np.ndarray,
    position: np.ndarray,
    pnl: np.ndarray,
    gross_pnl: np.ndarray,
    spread_cost: np.ndarray,
    bars_per_year: int,
) -> dict[str, float]:
    """Compute performance metrics from backtest output.

    Uses gross_pnl (no spread deductions) for gross Sharpe and net pnl
    (spread deducted once in the backtest) for net Sharpe.  Previously both
    metrics used pnl, which already had spread deducted — cost_adjusted_sharpe
    was then subtracting spread a second time (double-counting).

    win_rate is computed at trade level (sum of bar PnLs per trade), not bar
    level.  Bar-level win_rate was inflated with num_trades guaranteed losing
    entry bars (spread-only bars), producing ~40% win rate for a flat model.
    """
    from src.alpha.ml_price_momentum.evaluation.cost_adjusted_metrics import (
        cost_adjusted_sharpe,
        gross_sharpe,
    )

    # Gross returns: directional PnL only, no spread costs
    gross_returns = gross_pnl[1:] / np.maximum(equity[:-1], 1.0)

    g_sharpe = gross_sharpe(gross_returns, bars_per_year=bars_per_year)
    # cost_adjusted_sharpe expects gross returns + separate cost array.
    # Pass gross_returns and spread_cost[1:] so spread is deducted exactly once.
    n_sharpe = cost_adjusted_sharpe(
        gross_returns, spread_cost[1:], bars_per_year=bars_per_year
    )

    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / np.maximum(peak, 1.0)
    max_dd = float(np.min(drawdown))

    # num_trades: count entries (position goes from 0 to nonzero)
    # Entry: position was 0, now nonzero — detect by position[i-1]==0 and position[i]!=0
    entry_mask = (position[:-1] == 0) & (position[1:] != 0)
    num_trades = int(np.sum(entry_mask))

    # Trade-level win rate: aggregate bar PnLs per trade, count profitable trades.
    # Each trade runs from entry bar to the last bar before the next entry or end.
    trade_pnls: list[float] = []
    current_trade_pnl = 0.0
    in_trade = False
    for i in range(len(position)):
        if position[i] != 0:
            current_trade_pnl += pnl[i]
            in_trade = True
        elif in_trade:
            trade_pnls.append(current_trade_pnl)
            current_trade_pnl = 0.0
            in_trade = False
    if in_trade:
        trade_pnls.append(current_trade_pnl)

    trade_pnls_arr = np.array(trade_pnls) if trade_pnls else np.array([0.0])
    winning_trades = trade_pnls_arr[trade_pnls_arr > 0]
    losing_trades = trade_pnls_arr[trade_pnls_arr < 0]
    win_rate = float(len(winning_trades) / max(len(trade_pnls_arr), 1))
    profit_factor = float(
        np.sum(winning_trades) / max(abs(np.sum(losing_trades)), 1e-10)
    )

    return {
        "gross_sharpe": g_sharpe,
        "net_sharpe": n_sharpe,
        "max_drawdown": max_dd,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "final_equity": float(equity[-1]),
        "total_return": float((equity[-1] / equity[0]) - 1.0),
    }


def run_regime_detection(
    close: np.ndarray,
) -> np.ndarray:
    """Fit HMM-GARCH and return Viterbi regime states.

    Rescales returns to basis points (x10000) before GARCH fitting
    because the arch library optimizer requires values between 1 and
    1000 — raw hourly FX returns (~1e-7) cause convergence failure.
    """
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    log_returns = np.diff(np.log(close))
    scaled_returns = log_returns * 10_000  # basis points for GARCH convergence
    detector = HMMGARCHRegimeDetector()
    success = detector.fit(scaled_returns)

    if not success:
        logger.warning("Regime detection failed — using uniform state 0")
        return np.zeros(len(log_returns), dtype=int)

    states = detector.predict_viterbi(scaled_returns)
    return states


def run_single_pair(
    pair: str,
    ohlc: pd.DataFrame,
    cross_asset_data: dict[str, pd.DataFrame] | None,
    bars_per_year: int,
) -> dict:
    """Run the full pipeline for one currency pair."""
    from src.alpha.ml_price_momentum.evaluation.shap_analysis import SHAPAnalyzer
    from src.alpha.ml_price_momentum.features.builder import FeatureBuilder
    from src.alpha.ml_price_momentum.models.ensemble import EnsembleModel
    from src.alpha.ml_price_momentum.models.walk_forward import (
        WalkForwardConfig,
        WalkForwardEngine,
    )
    from src.backtest.accumulators import single_pass_backtest
    from src.backtest.numba_kernels import rolling_atr

    open_arr = ohlc["Open"].values.astype(np.float64)
    high = ohlc["High"].values.astype(np.float64)
    low = ohlc["Low"].values.astype(np.float64)
    close = ohlc["Close"].values.astype(np.float64)
    volume = ohlc["Volume"].values.astype(np.float64)
    hour = pd.DatetimeIndex(ohlc.index).hour.values.astype(np.float64)
    dow = pd.DatetimeIndex(ohlc.index).dayofweek.values.astype(np.float64)

    print(f"\n--- {pair} ---")

    # 1. Regime detection — SKIPPED.
    # HMM-GARCH regime_state was removed as a feature (2026-03-24) because state
    # assignments are non-deterministic across runs. Step retained as a placeholder
    # for future use once a stable, deterministic regime indicator is developed.
    print("  [1/6] Regime detection... SKIPPED (feature removed — see debug session)")

    # 2. Feature building
    print("  [2/6] Building 27 features...")
    builder = FeatureBuilder(cross_asset_data)
    features_df = builder.build(pair, open_arr, high, low, close, volume, hour, dow)

    # 3. Labels — 5-bar threshold to eliminate near-zero return noise.
    #    Binary next-bar labels on 1H FX have ~40-50% class noise because moves
    #    smaller than spread (1.2 pips) are rounded to +1/-1 arbitrarily.
    #    Fix: use sign of 5-bar forward return, dropping ambiguous rows where
    #    |5-bar return| < 0.08% (roughly 1 pip on EURUSD at 1.10).
    label_horizon = 5
    label_threshold = 0.0008  # 0.08% — approximately 1 pip threshold
    close_series = pd.Series(close)
    fwd_return = (close_series.shift(-label_horizon) - close_series) / close_series
    y_direction = np.sign(fwd_return.values)  # -1, 0, +1
    # Map to binary: +1 -> 1 (long), -1 -> 0 (short), 0 -> masked out
    y_full = np.where(y_direction > 0, 1, 0)
    # Mark ambiguous (near-zero) and future-unavailable rows invalid
    ambiguous_mask = np.abs(fwd_return.values) < label_threshold
    # Last label_horizon rows have no valid label (shift(-5) runs out)
    ambiguous_mask[-label_horizon:] = True

    # Feature subset: SHAP stability analysis (2026-03-24) identified 5 consistently
    # informative features across all walk-forward windows for both EURUSD and GBPUSD.
    # The other 22 features (volatility, session, cross-asset, tick volume) are either
    # unstable across windows or add noise dimensions to the decision boundary.
    # With ~1764 training samples, 22 noise dimensions increase spurious fit
    # probability. Using only the 5 SHAP-stable momentum features reduces the
    # feature space by 82%, lowers train-test gap, and forces the model to use
    # the signal it actually has.
    #
    # Previously: 27-feature set used directly after regime_state removal.
    # Now: subset to top-5 SHAP-stable features.
    shap_stable_features = [
        "mom_1bar",
        "mom_5bar",
        "mom_10bar",
        "mom_22bar",
        "mom_63bar",
    ]
    feature_names_with_regime = shap_stable_features  # 5 features, SHAP-stable only

    # 4. Drop warmup NaN rows, ambiguous label rows, and last label_horizon rows.
    # NaN detection uses the full 27-feature matrix so that any warmup row missing
    # ANY feature is excluded.  Then we subset columns to the 5 SHAP-stable features.
    valid_mask = ~np.isnan(features_df.values).any(axis=1)
    valid_mask &= ~ambiguous_mask
    feature_col_indices = [
        FeatureBuilder.FEATURE_NAMES.index(f) for f in feature_names_with_regime
    ]
    x_arr = features_df.values[valid_mask][:, feature_col_indices].astype(np.float32)
    y_arr = y_full[valid_mask]
    close_valid = close[valid_mask]
    high_valid = high[valid_mask]
    low_valid = low[valid_mask]

    warmup_dropped = int(np.sum(~valid_mask))
    print(
        f"    Warmup/ambiguous rows dropped: {warmup_dropped}, valid bars: {len(x_arr)}"
    )
    feat_names_str = ", ".join(feature_names_with_regime)
    print(f"    Feature set ({len(feature_names_with_regime)}): {feat_names_str}")

    # 5. Walk-forward validation
    print("  [3/6] Walk-forward validation...")
    config = WalkForwardConfig()
    engine = WalkForwardEngine(config)
    n_wins = engine.n_windows(len(x_arr))
    print(
        f"    Config: train={config.train_window}, test={config.test_window}, "
        f"step={config.step}, purge={config.purge_gap}"
    )
    print(f"    Expected windows: {n_wins}")

    results = engine.run(x_arr, y_arr, feature_names=feature_names_with_regime)
    print(f"    Completed windows: {len(results)}")

    if len(results) == 0:
        print(f"    SKIP: Not enough data for walk-forward ({len(x_arr)} bars)")
        return {"pair": pair, "skipped": True}

    # 6. SHAP stability
    print("  [4/6] SHAP stability analysis...")
    shap_results = [
        {
            "top_5": sorted(
                r.feature_importance,
                key=lambda k: r.feature_importance[k],
                reverse=True,
            )[:5]
        }
        for r in results
        if r.feature_importance is not None
    ]
    if shap_results:
        analyzer = SHAPAnalyzer(feature_names_with_regime)
        stability = analyzer.track_stability(shap_results)
        print(f"    Stable features (>50% windows): {stability['stable_features']}")

    # 7. Generate signals from OOS predictions
    oos_predictions = np.concatenate([r.predictions for r in results])
    oos_actuals = np.concatenate([r.actuals for r in results])

    # Model accuracy diagnostic — tells us if the MODEL is inverted or if the
    # backtest execution converts a correct model into negative PnL.
    model_accuracy = float(np.mean((oos_predictions > 0.5) == oos_actuals))
    class_balance = float(np.mean(oos_actuals))
    print(f"    Model accuracy (proba>0.5 vs y_test): {model_accuracy:.1%}")
    print(f"    Label class balance (fraction y=1):    {class_balance:.1%}")

    # Diagnostic: accuracy split by confident vs flat-zone predictions.
    # Threshold updated to match new generate_signal dead-zone [0.49, 0.51].
    # The overall 50% accuracy may be dominated by flat-zone bars (0.49-0.51)
    # that never generate trades.  Trades execute only on confident predictions
    # (proba > 0.51 → long, proba < 0.49 → short).  If confident predictions are
    # systematically inverted while flat-zone predictions are ~50/50, the overall
    # 50% accuracy masks a real inversion on trade-generating bars.
    conf_threshold = 0.01  # matches generate_signal dead-zone [0.49, 0.51]
    confident_mask = np.abs(oos_predictions - 0.5) > conf_threshold
    n_confident = int(np.sum(confident_mask))
    n_flat = int(np.sum(~confident_mask))
    if n_confident > 0:
        acc_confident = float(
            np.mean(
                (oos_predictions[confident_mask] > 0.5) == oos_actuals[confident_mask]
            )
        )
    else:
        acc_confident = float("nan")
    if n_flat > 0:
        acc_flat = float(
            np.mean(
                (oos_predictions[~confident_mask] > 0.5) == oos_actuals[~confident_mask]
            )
        )
    else:
        acc_flat = float("nan")
    print(
        f"    Confident predictions (|p-0.5|>0.01): {n_confident:5d} bars "
        f"({n_confident / max(len(oos_predictions), 1):.1%} of OOS)"
    )
    print(
        f"    Flat-zone predictions (|p-0.5|<=0.01): {n_flat:5d} bars "
        f"({n_flat / max(len(oos_predictions), 1):.1%} of OOS)"
    )
    print(f"    Accuracy on confident predictions:     {acc_confident:.1%}")
    print(f"    Accuracy on flat-zone predictions:     {acc_flat:.1%}")

    # Per-window train vs test accuracy (detects overfitting)
    print("    Per-window train-vs-test accuracy:")
    from sklearn.metrics import accuracy_score

    from src.alpha.ml_price_momentum.models.ensemble import (
        EnsembleModel as _Ens,
    )

    for w_idx, res in enumerate(results[: min(5, len(results))]):  # first 5 windows
        cfg = WalkForwardConfig()
        train_end = cfg.train_window + w_idx * cfg.step
        val_start = train_end - cfg.val_size
        x_tr = x_arr[train_end - cfg.train_window : val_start]
        y_tr = y_arr[train_end - cfg.train_window : val_start]
        x_ts = x_arr[res.test_start : res.test_end]
        y_ts = res.actuals
        # Refit model to get train accuracy (expensive but diagnostic only)
        _ens = _Ens()
        _ens.fit(x_tr, y_tr, x_arr[val_start:train_end], y_arr[val_start:train_end])
        train_proba = _ens.predict_proba(x_tr)
        test_proba = _ens.predict_proba(x_ts)
        tr_acc = accuracy_score(y_tr, train_proba > 0.5)
        ts_acc = accuracy_score(y_ts, test_proba > 0.5)
        print(f"      Window {w_idx}: train_acc={tr_acc:.1%}  test_acc={ts_acc:.1%}")
    oos_start = results[0].test_start
    oos_end = results[-1].test_end

    ensemble = EnsembleModel()
    raw_signal_arr = np.array(
        [ensemble.generate_signal(float(p)) for p in oos_predictions],
        dtype=np.int8,
    )

    # Minimum hold: enforce 5-bar hold period matching the label horizon.
    # The 5-bar threshold label means the model predicts a directional move
    # over the NEXT 5 bars.  If the backtest exits after 1-2 bars (before the
    # predicted move completes), the signal cannot overcome 2x spread costs.
    # Fix: once a trade is entered, suppress the signal for min_hold_bars-1
    # additional bars so the position is held for at least min_hold_bars.
    # This is a pre-backtest transform — it does not change the entry signal,
    # only prevents premature exits driven by flat/opposite signals in bars 1-4.
    min_hold_bars = 5
    signal_arr = raw_signal_arr.copy()
    hold_remaining = 0
    current_direction: int = 0
    for _i in range(len(signal_arr)):
        if hold_remaining > 0:
            # Still within minimum hold — keep current direction, suppress exit
            signal_arr[_i] = current_direction
            hold_remaining -= 1
        elif signal_arr[_i] != 0:
            # New entry signal — start hold counter
            current_direction = int(signal_arr[_i])
            hold_remaining = min_hold_bars - 1
        else:
            # Flat signal outside hold window — allow exit
            current_direction = 0

    oos_close = close_valid[oos_start:oos_end]
    oos_high = high_valid[oos_start:oos_end]
    oos_low = low_valid[oos_start:oos_end]

    min_len = min(len(signal_arr), len(oos_close))
    signal_arr = signal_arr[:min_len]
    oos_close = oos_close[:min_len]
    oos_high = oos_high[:min_len]
    oos_low = oos_low[:min_len]

    # 8. ATR for position sizing
    atr = rolling_atr(oos_high, oos_low, oos_close, 14)
    first_valid_atr = atr[~np.isnan(atr)]
    fill_val = float(first_valid_atr[0]) if len(first_valid_atr) > 0 else 0.001
    atr = np.where(np.isnan(atr), fill_val, atr)

    # 9. Backtest at base spread
    print("  [5/6] Backtesting...")
    base_spread = BASE_SPREAD_PIPS.get(pair, 0.00015)
    spread_cost = np.full(min_len, base_spread)

    equity, position, pnl, gross_pnl = single_pass_backtest(
        oos_close,
        signal_arr,
        0.01,
        atr,
        spread_cost,
    )
    metrics = compute_metrics(
        equity, position, pnl, gross_pnl, spread_cost, bars_per_year
    )

    print(f"    Gross Sharpe:    {metrics['gross_sharpe']:>8.3f}")
    print(f"    Net Sharpe:      {metrics['net_sharpe']:>8.3f}")
    print(f"    Max Drawdown:    {metrics['max_drawdown']:>8.1%}")
    print(f"    Win Rate:        {metrics['win_rate']:>8.1%}")
    print(f"    Profit Factor:   {metrics['profit_factor']:>8.3f}")
    print(f"    Num Trades:      {metrics['num_trades']:>8d}")
    print(f"    Total Return:    {metrics['total_return']:>8.1%}")

    # Diagnostic: trade duration distribution.
    # A momentum model should hold for several bars (capturing the predicted move).
    # Very short trades (1-3 bars) cannot recover 2x spread costs and lose.
    # Compute per-trade duration from the position array.
    trade_durations: list[int] = []
    dur = 0
    for _pos in position:
        if _pos != 0:
            dur += 1
        elif dur > 0:
            trade_durations.append(dur)
            dur = 0
    if dur > 0:
        trade_durations.append(dur)  # trade open at end of series
    if trade_durations:
        td = np.array(trade_durations)
        print(
            f"    Trade duration:  mean={np.mean(td):.1f}  median={np.median(td):.0f}  "
            f"max={np.max(td):.0f}  pct<5bars={np.mean(td < 5):.1%}"
        )
    # Signal composition (how many long/flat/short signals were generated)
    n_long = int(np.sum(signal_arr == 1))
    n_short = int(np.sum(signal_arr == -1))
    n_flat_sig = int(np.sum(signal_arr == 0))
    n_sig = len(signal_arr)
    print(
        f"    Signal mix:      long={n_long / n_sig:.1%}  short={n_short / n_sig:.1%}  "
        f"flat={n_flat_sig / n_sig:.1%}"
    )

    # 10. Cost sensitivity sweep
    print("  [6/6] Cost sensitivity sweep...")
    print(f"    {'Mult':>6} | {'Sharpe':>8} | {'MaxDD':>8} | {'PF':>8}")
    print(f"    {'─' * 6}─┼─{'─' * 8}─┼─{'─' * 8}─┼─{'─' * 8}")

    cost_sharpes = []
    for mult in COST_MULTIPLIERS:
        sc = np.full(min_len, base_spread * mult)
        eq, pos, pl, gpl = single_pass_backtest(
            oos_close,
            signal_arr,
            0.01,
            atr,
            sc,
        )
        m = compute_metrics(eq, pos, pl, gpl, sc, bars_per_year)
        cost_sharpes.append(m["net_sharpe"])
        print(
            f"    {mult:>5.1f}x | {m['net_sharpe']:>8.3f} | "
            f"{m['max_drawdown']:>7.1%} | {m['profit_factor']:>8.3f}"
        )

    return {
        "pair": pair,
        "skipped": False,
        "metrics": metrics,
        "oos_predictions": oos_predictions,
        "cost_sharpes": cost_sharpes,
        "shap_stability": stability if shap_results else None,
    }


def print_correlation_matrix(
    all_results: list[dict],
) -> None:
    """Print pairwise OOS prediction correlation between pairs."""
    active = [r for r in all_results if not r.get("skipped", True)]
    if len(active) < 2:
        print("\n  (Need >= 2 pairs for correlation matrix)")
        return

    print(f"\n{'=' * 60}")
    print("  Cross-Pair OOS Prediction Correlation")
    print(f"{'=' * 60}")

    pairs = [r["pair"] for r in active]
    preds = {r["pair"]: r["oos_predictions"] for r in active}

    header = f"{'':>10}" + "".join(f"{p:>10}" for p in pairs)
    print(header)

    for p1 in pairs:
        row = f"{p1:>10}"
        for p2 in pairs:
            min_len = min(len(preds[p1]), len(preds[p2]))
            if p1 == p2:
                corr = 1.0
            else:
                corr = float(
                    np.corrcoef(preds[p1][:min_len], preds[p2][:min_len])[0, 1]
                )
            row += f"{corr:>10.3f}"
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Helix end-to-end pipeline validation")
    parser.add_argument(
        "--pairs",
        nargs="+",
        default=["EURUSD", "GBPUSD"],
        choices=list(PAIR_TO_YF.keys()),
        help="Currency pairs to validate (default: EURUSD GBPUSD)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=18,
        help="Months of hourly data to pull (default: 18, max ~24)",
    )
    args = parser.parse_args()

    bars_per_year = 6048  # 1h bars: 252 * 24

    # Pull data
    try:
        all_ohlc = pull_data(args.pairs, args.months)
    except Exception as e:
        print(f"\nERROR: Failed to pull data from Yahoo Finance: {e}")
        print("Check your network connection and try again.")
        sys.exit(1)

    # Build cross-asset data dict for FeatureBuilder Tier 4
    cross_asset_data = {}
    for pair, ohlc in all_ohlc.items():
        cross_asset_data[pair] = pd.DataFrame(
            {"close": ohlc["Close"].values}, index=ohlc.index
        )

    # Run per-pair validation
    all_results = []
    for pair in args.pairs:
        result = run_single_pair(pair, all_ohlc[pair], cross_asset_data, bars_per_year)
        all_results.append(result)

    # Cross-pair correlation
    print_correlation_matrix(all_results)

    # Summary
    print(f"\n{'=' * 60}")
    print("  VALIDATION SUMMARY")
    print(f"{'=' * 60}")
    for r in all_results:
        if r.get("skipped"):
            print(f"  {r['pair']}: SKIPPED (insufficient data)")
        else:
            m = r["metrics"]
            verdict = "PASS" if m["net_sharpe"] > 0 else "FAIL"
            print(
                f"  {r['pair']}: Net Sharpe={m['net_sharpe']:.3f} "
                f"MaxDD={m['max_drawdown']:.1%} "
                f"PF={m['profit_factor']:.2f} "
                f"[{verdict}]"
            )

    print()


if __name__ == "__main__":
    main()
