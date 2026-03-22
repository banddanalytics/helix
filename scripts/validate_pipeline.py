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
import itertools
import logging
import sys
from datetime import datetime, timedelta

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


def pull_data(
    pairs: list[str], months: int
) -> dict[str, pd.DataFrame]:
    """Pull hourly OHLCV data from Yahoo Finance via VectorBT Pro."""
    import vectorbtpro as vbt

    end = datetime.now()
    start = end - timedelta(days=months * 30)

    yf_symbols = [PAIR_TO_YF[p] for p in pairs]
    print(f"\n{'='*60}")
    print(f"  Pulling {months} months of 1H data for {pairs}")
    print(f"  Range: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    data = vbt.YFData.pull(
        symbols=yf_symbols,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        timeframe="1h",
        tz="UTC",
    )

    result = {}
    for pair, yf_sym in zip(pairs, yf_symbols):
        ohlc = data.select_symbols(yf_sym).get()
        ohlc = ohlc.dropna(subset=["Close"])
        result[pair] = ohlc
        print(f"  {pair}: {len(ohlc)} bars loaded")

    return result


def compute_metrics(
    equity: np.ndarray,
    position: np.ndarray,
    pnl: np.ndarray,
    spread_cost: np.ndarray,
    bars_per_year: int,
) -> dict[str, float]:
    """Compute performance metrics from backtest output."""
    from src.alpha.ml_price_momentum.evaluation.cost_adjusted_metrics import (
        cost_adjusted_sharpe,
        gross_sharpe,
    )

    returns = pnl[1:] / np.maximum(equity[:-1], 1.0)
    costs = spread_cost[1:]

    g_sharpe = gross_sharpe(returns, bars_per_year=bars_per_year)
    n_sharpe = cost_adjusted_sharpe(returns, costs, bars_per_year=bars_per_year)

    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / np.maximum(peak, 1.0)
    max_dd = float(np.min(drawdown))

    trades_mask = np.diff(position.astype(np.int16)) != 0
    num_trades = int(np.sum(trades_mask))

    winning = pnl[pnl > 0]
    losing = pnl[pnl < 0]
    win_rate = float(len(winning) / max(len(winning) + len(losing), 1))
    profit_factor = float(
        np.sum(winning) / max(abs(np.sum(losing)), 1e-10)
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
    """Fit HMM-GARCH and return Viterbi regime states."""
    from src.alpha.regime.hmm_garch import HMMGARCHRegimeDetector

    log_returns = np.diff(np.log(close))
    detector = HMMGARCHRegimeDetector()
    success = detector.fit(log_returns)

    if not success:
        logger.warning("Regime detection failed — using uniform state 0")
        return np.zeros(len(log_returns), dtype=int)

    states = detector.predict_viterbi(log_returns)
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

    # 1. Regime detection
    print("  [1/6] Regime detection...")
    states = run_regime_detection(close)
    if len(states) > 0:
        counts = np.bincount(states, minlength=3)
        total = len(states)
        print(f"    States: Trending={counts[0]/total:.1%} "
              f"Mean-Rev={counts[1]/total:.1%} "
              f"Volatile={counts[2]/total:.1%}")

    # 2. Feature building
    print("  [2/6] Building 27 features...")
    builder = FeatureBuilder(cross_asset_data)
    features_df = builder.build(pair, open_arr, high, low, close, volume, hour, dow)

    # 3. Labels (binary: next bar up/down)
    y_full = (pd.Series(close).shift(-1) > close).astype(int).values

    # 4. Drop warmup NaN rows and last row (no label)
    valid_mask = ~np.isnan(features_df.values).any(axis=1)
    valid_mask[-1] = False  # last row has no label
    x_arr = features_df.values[valid_mask].astype(np.float32)
    y_arr = y_full[valid_mask]
    close_valid = close[valid_mask]
    high_valid = high[valid_mask]
    low_valid = low[valid_mask]

    warmup_dropped = int(np.sum(~valid_mask)) - 1
    print(f"    Warmup rows dropped: {warmup_dropped}, valid bars: {len(x_arr)}")

    # 5. Walk-forward validation
    print("  [3/6] Walk-forward validation...")
    config = WalkForwardConfig()
    engine = WalkForwardEngine(config)
    n_wins = engine.n_windows(len(x_arr))
    print(f"    Config: train={config.train_window}, test={config.test_window}, "
          f"step={config.step}, purge={config.purge_gap}")
    print(f"    Expected windows: {n_wins}")

    results = engine.run(x_arr, y_arr, feature_names=FeatureBuilder.FEATURE_NAMES)
    print(f"    Completed windows: {len(results)}")

    if len(results) == 0:
        print(f"    SKIP: Not enough data for walk-forward ({len(x_arr)} bars)")
        return {"pair": pair, "skipped": True}

    # 6. SHAP stability
    print("  [4/6] SHAP stability analysis...")
    shap_results = [
        {"top_5": sorted(r.feature_importance, key=lambda k: r.feature_importance[k], reverse=True)[:5]}
        for r in results if r.feature_importance is not None
    ]
    if shap_results:
        analyzer = SHAPAnalyzer(FeatureBuilder.FEATURE_NAMES)
        stability = analyzer.track_stability(shap_results)
        print(f"    Stable features (>50% windows): {stability['stable_features']}")

    # 7. Generate signals from OOS predictions
    oos_predictions = np.concatenate([r.predictions for r in results])
    oos_actuals = np.concatenate([r.actuals for r in results])
    oos_start = results[0].test_start
    oos_end = results[-1].test_end

    ensemble = EnsembleModel()
    signal_arr = np.array(
        [ensemble.generate_signal(float(p)) for p in oos_predictions],
        dtype=np.int8,
    )
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

    equity, position, pnl = single_pass_backtest(
        oos_close, signal_arr, 0.01, atr, spread_cost,
    )
    metrics = compute_metrics(equity, position, pnl, spread_cost, bars_per_year)

    print(f"    Gross Sharpe:    {metrics['gross_sharpe']:>8.3f}")
    print(f"    Net Sharpe:      {metrics['net_sharpe']:>8.3f}")
    print(f"    Max Drawdown:    {metrics['max_drawdown']:>8.1%}")
    print(f"    Win Rate:        {metrics['win_rate']:>8.1%}")
    print(f"    Profit Factor:   {metrics['profit_factor']:>8.3f}")
    print(f"    Num Trades:      {metrics['num_trades']:>8d}")
    print(f"    Total Return:    {metrics['total_return']:>8.1%}")

    # 10. Cost sensitivity sweep
    print("  [6/6] Cost sensitivity sweep...")
    print(f"    {'Mult':>6} | {'Sharpe':>8} | {'MaxDD':>8} | {'PF':>8}")
    print(f"    {'─'*6}─┼─{'─'*8}─┼─{'─'*8}─┼─{'─'*8}")

    cost_sharpes = []
    for mult in COST_MULTIPLIERS:
        sc = np.full(min_len, base_spread * mult)
        eq, pos, pl = single_pass_backtest(
            oos_close, signal_arr, 0.01, atr, sc,
        )
        m = compute_metrics(eq, pos, pl, sc, bars_per_year)
        cost_sharpes.append(m["net_sharpe"])
        print(f"    {mult:>5.1f}x | {m['net_sharpe']:>8.3f} | "
              f"{m['max_drawdown']:>7.1%} | {m['profit_factor']:>8.3f}")

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

    print(f"\n{'='*60}")
    print("  Cross-Pair OOS Prediction Correlation")
    print(f"{'='*60}")

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
    parser = argparse.ArgumentParser(
        description="Helix end-to-end pipeline validation"
    )
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
    print(f"\n{'='*60}")
    print("  VALIDATION SUMMARY")
    print(f"{'='*60}")
    for r in all_results:
        if r.get("skipped"):
            print(f"  {r['pair']}: SKIPPED (insufficient data)")
        else:
            m = r["metrics"]
            verdict = "PASS" if m["net_sharpe"] > 0 else "FAIL"
            print(f"  {r['pair']}: Net Sharpe={m['net_sharpe']:.3f} "
                  f"MaxDD={m['max_drawdown']:.1%} "
                  f"PF={m['profit_factor']:.2f} "
                  f"[{verdict}]")

    print()


if __name__ == "__main__":
    main()
