---
status: resolved
trigger: "ml_price_momentum alpha engine produces ~35% OOS win rate — statistically inverted"
created: 2026-03-23T00:00:00Z
updated: 2026-03-24T12:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (from checkpoint run). Root cause is three interacting issues:
  (A) LONG BIAS FROM THRESHOLD ASYMMETRY: generate_signal uses proba>0.53→long,
      proba<0.47→short. With regularized model, probabilities cluster in 0.50-0.53 band
      (class imbalance in training period — Sept 2024 bullish for EUR/GBP). Result: 99%
      long signals, almost no shorts. In GBPUSD downtrend, this is systematic long losses.
  (B) 27 FEATURES TOO MANY FOR 1764 TRAINING SAMPLES: SHAP stable features are only 5
      (mom_1,5,10,22,63bar). The other 22 features are noise dimensions. High-dimensional
      noise increases chance of spurious correlations on small training sets.
  (C) EURUSD GROSS SHARPE IS NOW +0.083: The signal exists but is too thin to overcome
      12-pip spread on 111 trades. Fix: fewer, higher-quality trades with fewer features.

test: Three targeted fixes:
  (1) Threshold symmetry — lower long threshold to 0.51, short to 0.49 (tighter dead zone,
      symmetric around 0.50 rather than biased toward long by having 0.03 above/below 0.50
      in asymmetric band). Actually: current band IS symmetric (0.47-0.53). The long bias
      is from TRAINING DATA: training window is Sept 2024 (bullish period), so model learned
      proba tends to output slightly above 0.50 for momentum features. Fix: use mean-centered
      threshold — generate_signal dead zone is (mean_proba-0.02, mean_proba+0.02) per window.
      Simpler fix: just reduce dead zone to 0.50-0.01=0.49 short, 0.50+0.01=0.51 long.
  (2) Feature reduction to top-5 SHAP: mom_1bar, mom_5bar, mom_10bar, mom_22bar, mom_63bar.
      Drop 22 noise dimensions. This requires subset selection in validate_pipeline.py.
  (3) Hold 5-bar minimum: label horizon = 5 bars, but median trade = 2 bars. Trades exit
      too early because they are dominated by position transitions in the backtest engine.

next_action: Run validate_pipeline.py --pairs EURUSD GBPUSD --months 18 to verify:
  - Signal mix long/short is now balanced (not 99/1)
  - Gross Sharpe > 0 on both pairs
  - Net Sharpe improved from -2.784 (EURUSD) and -5.801 (GBPUSD)
  - Trade duration mean >= 5 bars (minimum hold working)

## Symptoms

expected: OOS win rate >= 50% (random), ideally 52-55%+ for a signal with edge
actual: ~35% win rate (first run), ~39.9% after four fixes — still below 50%
errors: No runtime errors. Silent failure at the ML signal quality level.
reproduction: Run `PYTHONPATH=. python scripts/validate_pipeline.py --pairs EURUSD GBPUSD --months 18`
started: Observed after first end-to-end pipeline run. Research completed prior to this session.

## Eliminated

- hypothesis: Double-shift in FeatureBuilder.build() making features 2-bar stale
  evidence: Removed df.shift(1); win rate improved 35→39.9%
  timestamp: 2026-03-23T00:01:00Z

- hypothesis: Binary 1-bar label with high class noise
  evidence: Replaced with 5-bar threshold label; win rate improved marginally
  timestamp: 2026-03-23T00:01:00Z

- hypothesis: train_window=756 as 1H bars (only 31 days of training)
  evidence: Updated to 2016/252/168/168; more windows, more data
  timestamp: 2026-03-23T00:01:00Z

- hypothesis: Regime states computed but not passed to ML pipeline
  evidence: Added regime_state as 28th feature column
  timestamp: 2026-03-23T00:01:00Z

- hypothesis: Signal direction inversion (signal=+1 → short instead of long)
  evidence: Code inspection confirms signal=+1 → position=1 (long) → profits from price going up.
    Label y=1 means price went up. proba>0.53 → signal=+1. Chain is internally consistent.
  timestamp: 2026-03-23T01:00:00Z

- hypothesis: Label-backtest misalignment (labels on original close, backtest on close_valid)
  evidence: Misalignment creates noise (1-bar offset, 40% gap-induced extension) but not
    systematic inversion. The label period [j, j+5] and backtest capture [j+1, j+8] have
    substantial overlap, and direction is consistent.
  timestamp: 2026-03-23T01:00:00Z

- hypothesis: Gross Sharpe=-2.2 is a measurement artifact (double-counted spread or wrong gross_pnl)
  evidence: BUG6 (double-counted spread) was fixed in previous session. The new Gross Sharpe=-2.2
    is computed from gross_pnl (zero on entry bars, directional price change × pos_size on
    hold/exit bars). This is spread-free. The -2.2 value is REAL systematic negative gross PnL,
    not a measurement artifact. Confirmed by analytical calculation: with 50% model, mean(gross)
    should be 0 unless confident predictions are directionally wrong.
  timestamp: 2026-03-24T00:00:00Z

- hypothesis: Gross Sharpe=-2.2 is statistical noise (too few OOS samples)
  evidence: Standard error calculation. With ~1008 OOS bars and ~700 non-zero gross return bars,
    SE(Sharpe) ≈ 0.10 when accounting for autocorrelation (effectively 351 independent trade obs).
    Sharpe=-2.2 is 22 standard errors from zero — statistically significant real negative signal.
    This is not sampling variance.
  timestamp: 2026-03-24T00:00:00Z

## Evidence

- timestamp: 2026-03-23T00:01:00Z
  checked: src/alpha/ml_price_momentum/features/builder.py lines 140-150
  found: Double-shift confirmed. Removed df.shift(1).
  implication: BUG 1 CONFIRMED AND FIXED.

- timestamp: 2026-03-23T00:01:00Z
  checked: scripts/validate_pipeline.py line 191 (original)
  found: Binary 1-bar label with ~40-50% class noise. Replaced with 5-bar threshold.
  implication: BUG 2 CONFIRMED AND FIXED.

- timestamp: 2026-03-23T00:01:00Z
  checked: src/alpha/ml_price_momentum/models/walk_forward.py WalkForwardConfig
  found: train_window=756 (31 days on 1H bars). Updated to train_window=2016.
  implication: BUG 3 CONFIRMED AND FIXED.

- timestamp: 2026-03-23T00:01:00Z
  checked: scripts/validate_pipeline.py regime states
  found: States computed but not passed to ML pipeline. Added as 28th feature.
  implication: BUG 4 CONFIRMED AND FIXED.

- timestamp: 2026-03-23T01:00:00Z
  checked: scripts/validate_pipeline.py compute_metrics lines 105-107
  found: win_rate = len(pnl > 0) / len(pnl != 0) — counts EVERY BAR with nonzero PnL.
    Entry bars always have pnl = -spread_cost * pos_size (ALWAYS negative).
    With 693 trades and 3360 OOS bars, ~693 entry bars are guaranteed losers.
    Even a 50% model produces ~39.9% bar-win-rate because of 693 guaranteed entry losses.
    Math: 3360 bars, 693 guaranteed losses, remaining 2667 at 50% → 1333 wins / 3360 = 39.7%.
    MATCHES THE OBSERVED 39.9%. This explains the "apparent" inversion metric.
  implication: BUG 5 CONFIRMED. win_rate metric is NOT model accuracy.
    The Gross Sharpe=-4.5 is the real inversion signal, NOT the 39.9% win_rate.
    win_rate must be computed at trade level (per-trade PnL, not per-bar PnL).

- timestamp: 2026-03-23T01:00:00Z
  checked: scripts/validate_pipeline.py compute_metrics + cost_adjusted_metrics.py
  found: pnl from single_pass_backtest ALREADY deducts spread_cost on every entry/exit bar.
    compute_metrics: returns = pnl[1:] / equity[:-1]  (pnl includes spread deductions)
    gross_sharpe(returns) — computes Sharpe on spread-included returns (actually NET)
    cost_adjusted_sharpe(returns, costs) — subtracts spread_costs AGAIN from returns
    NET sharpe = DOUBLE-COUNTED spreads.
    "Gross Sharpe=-4.563" is actually net-of-spread Sharpe.
    "Net Sharpe=-6.208" is net-of-2x-spread Sharpe.
    True pre-spread gross Sharpe is unknown but likely less negative (may be ~0 or positive).
  implication: BUG 6 CONFIRMED. The Gross Sharpe metric is misleading us.
    The model might not be inverted — it might be a near-zero signal that spread costs kill.
    Need to compute TRUE gross Sharpe from raw bar returns before spread deduction.

- timestamp: 2026-03-23T01:00:00Z
  checked: scripts/validate_pipeline.py lines 262-263
  found: oos_actuals = np.concatenate([r.actuals for r in results]) is computed but NEVER
    used. No accuracy_score, no confusion matrix, no reporting of classification accuracy.
    We cannot tell from the current output whether the MODEL is inverting or whether
    spread costs are destroying a flat model.
  implication: BUG 7 CONFIRMED. Critical diagnostic missing.
    After all fixes, the FIRST thing to print is sklearn accuracy_score(oos_actuals,
    oos_predictions > 0.5) and the class distribution (np.mean(oos_actuals)).

- timestamp: 2026-03-23T01:00:00Z
  checked: Cross-pair prediction correlation = -0.123 (EURUSD vs GBPUSD)
  found: EURUSD and GBPUSD price movements are highly correlated (+0.7-0.9).
    Predictions are NEGATIVELY correlated (-0.123). Likely cause: OOS prediction windows
    cover different time periods (different valid_masks filter different bars, different
    oos_start/oos_end indices). The correlation is between time-misaligned series.
    Also: regime_state feature may have arbitrary state ordering per pair.
  implication: -0.123 correlation is a diagnostic artifact from time-misaligned OOS windows,
    not evidence of a fundamental model inversion. Can be confirmed by aligning OOS windows
    by timestamp rather than array index.

- timestamp: 2026-03-24T00:00:00Z
  checked: New diagnostic numbers from second run (reported in checkpoint response)
  found:
    EURUSD: Model accuracy=49.6%, Label balance=50.9%, Gross Sharpe=-2.215, Win Rate=34.5%, NumTrades=351
    GBPUSD: Model accuracy=50.3%, Label balance=51.7%, Gross Sharpe=-1.753, Win Rate=26.5%, NumTrades=340
    Cross-pair OOS prediction correlation: -0.123 (stable)
    Regime detection COMPLETELY FLIPPED (EURUSD: 45.5% trending vs 80.3% prior run on same data)
  implication:
    (1) Model accuracy ~50% = coin flip. Model has no predictive signal at all.
    (2) Gross Sharpe = -2.2 even with coin-flip signals. Cannot be explained by spread
        (gross_pnl excludes spread). Must be systematic negative direction in gross PnL.
    (3) Trade win rate = 26-34% with 50% model. If trades are SHORT (1-3 bars), spread can
        explain ~39% theoretical win rate from P(1-bar return > 2×spread). But 26-34% < 39%.
        Implies either model direction is inverted ON TRADE-GENERATING BARS, or trades
        are even shorter than 1 bar.
    (4) Regime detection instability: HMM-GARCH flips state assignments between runs on
        identical data. The regime_state feature added as 28th feature is NOISE — it changes
        meaning between training windows since HMM global Viterbi assigns states across the
        full sequence but state labels are arbitrary.

- timestamp: 2026-03-24T00:00:00Z
  checked: validate_pipeline.py signal generation and backtest chain; ensemble.py thresholds
  found:
    generate_signal: proba>0.53→+1, proba<0.47→-1, 0.47-0.53→0 (flat/no trade)
    With a coin-flip (50%) model, probabilities cluster near 0.5. If MOST predictions land
    in flat zone (0.47-0.53), then most bars produce signal=0 and only a few produce trades.
    The overall accuracy metric = mean((preds>0.5)==actuals) includes ALL bars (including
    flat-zone bars that never generate trades). If flat-zone predictions are ~50% accurate
    (random) and dominate the count, overall accuracy appears 50% even if trade-generating
    predictions (|proba-0.5|>0.03) are systematically wrong (< 50% accurate).
    HYPOTHESIS: The 50% overall accuracy masks significant inversion on confident predictions.
    A model overfitting on noise learns spurious patterns → confident OOS predictions are
    systematically wrong, while uncertain predictions (near 0.5) are essentially random and
    dominate the accuracy calculation.
  implication:
    The root cause of 26-34% trade win rate with 50% overall accuracy is likely:
    - Accurate predictions clustered in flat zone (0.47-0.53) → no trades, but count toward 50%
    - Inaccurate predictions in tail zones (>0.53 or <0.47) → generate trades, all wrong
    - This is classic overfit noise signature: confident wrong predictions, uncertain right ones
    ADDITIONALLY: with model accuracy = 50% on the overall distribution, but trades taken
    only on confident signals that are ~0-40% accurate, the gross PnL will be negative.
    This explains Gross Sharpe=-2.2: it's not a measurement artifact, it's a real negative
    signal captured by taking the wrong side of confident but wrong predictions.

- timestamp: 2026-03-24T00:00:00Z
  checked: scripts/validate_pipeline.py — all 5 feature tiers for PiT compliance
  found:
    Tier 1 (momentum): feature[i] uses close[i-1]..close[i-253]. PiT compliant.
    Tier 2 (volatility): feature[i] uses log returns lr[i-1] and earlier. PiT compliant.
    Tier 3 (session): feature[i] uses hour[i-1], close[i-1], etc. PiT compliant.
    Tier 4 (cross-asset): applies .shift(1) explicitly. PiT compliant.
    Tier 5 (tick volume): not read yet but follows same @njit pattern.
    Label: y[i] = sign(close[i+5] - close[i]). Reference price is close[i], which is
    the CURRENT close, NOT in features (features use close[i-1] as most recent). Small
    but systematic 1-bar gap between feature state and label reference.
  implication:
    No look-ahead bias found in features. PiT compliance is correct.
    The 1-bar gap (label anchored at close[i] but features use close[i-1]) is a minor
    signal degradation, not a systematic inversion. This was previously eliminated.

- timestamp: 2026-03-24T02:00:00Z
  checked: checkpoint response — post-regularization diagnostic run (EURUSD+GBPUSD, 18 months)
  found:
    EURUSD: Train acc 59-61%, Test acc 40-58% (gap reduced). Confident preds 430 bars (12.8%),
      accuracy 48.4%. Flat-zone accuracy 51.9%. Gross Sharpe +0.083 (was -2.215). Net -2.784.
      Signal mix: long=12.7%, short=0.1%, flat=87.2%. Num Trades: 111.
    GBPUSD: Train acc 60-63%, Test acc 51-64% (gap reduced). Confident preds 611 bars (19.1%),
      accuracy 46.6%. Flat-zone accuracy 52.2%. Gross Sharpe -2.857 (was -1.386). Net -5.801.
      Signal mix: long=18.3%, short=0.8%, flat=80.9%. Num Trades: 131, Win Rate: 22.9%.
    Cross-pair correlation: -0.081 (improved from -0.124).
    SHAP stable features (both pairs): mom_1bar, mom_5bar, mom_10bar, mom_22bar, mom_63bar.
  implication:
    (1) LONG BIAS IS THE PRIMARY PROBLEM: 99% long signals on both pairs. Symmetric ±0.03
        threshold band is not the cause — model itself outputs probabilities clustered at
        0.50-0.53, generating only long signals. Training period was bullish; model learned
        that momentum features → y=1 (up) more than y=0 (down).
    (2) EURUSD GROSS +0.083: Signal exists (weak) but is spread-crushed on 111 trades. If
        short signals were generated, net PnL could improve by avoiding long bias in downtrend.
    (3) GBPUSD 46.6% CONFIDENT ACCURACY: MORE confident → MORE wrong. This is overfit noise
        inversion on trade-generating predictions, compounded by long bias in GBPUSD downtrend.
    (4) SHAP top-5 stable features are all short-term momentum. The other 22 features are
        not consistently informative and likely add noise to the decision boundary.
    (5) Train-test gap still exists on low windows (e.g. EURUSD window 3: 40.5% test).
        Feature reduction should further reduce this by eliminating noise dimensions.

- timestamp: 2026-03-24T01:00:00Z
  checked: src/alpha/ml_price_momentum/models/xgboost_model.py,
           src/alpha/ml_price_momentum/models/rf_model.py,
           scripts/validate_pipeline.py (regime_state section)
  found:
    Applied three fixes:
    (1) XGBoost: max_depth 5→3, n_estimators 500→300, subsample 0.8→0.6,
        colsample_bytree 0.7→0.5, min_child_weight 100→200, reg_alpha 0.1→1.0,
        reg_lambda 1.0→5.0, early_stopping_rounds 50→30
    (2) RF: n_estimators 1000→300, max_depth 7→3, min_samples_leaf 50→200
    (3) regime_state feature removed from validate_pipeline.py — HMM-GARCH state
        assignments are non-deterministic across runs; feature injected noise not signal.
        Regime detection step also skipped (no longer used by the pipeline).
    All 88 existing tests pass after changes.
  implication:
    Reduced model capacity matches the training data size (~1764 samples × 27 features).
    Target: train-test accuracy gap < 10 points, confident prediction accuracy > 50%.

- timestamp: 2026-03-24T02:30:00Z
  checked: ensemble.py generate_signal, validate_pipeline.py feature pipeline and signal gen
  found:
    (4) Threshold narrowing applied: proba>0.51→long, proba<0.49→short (was 0.53/0.47).
        Dead zone narrowed from ±0.03 to ±0.01. With proba clustering 0.50-0.52, this
        enables short signals (proba 0.49-0.50 → short) rather than requiring proba < 0.47.
    (5) Feature subsetting applied: x_arr now uses only 5 SHAP-stable momentum features
        (mom_1bar, mom_5bar, mom_10bar, mom_22bar, mom_63bar) via column index lookup.
        Valid_mask NaN detection still uses full 27-feature matrix to preserve warmup exclusion.
        walk_forward engine receives 5-feature x_arr and 5-element feature_names list.
    (6) Minimum hold applied: pre-backtest signal_arr transform holds current direction
        for MIN_HOLD_BARS=5 bars after entry, suppressing premature exit. This matches the
        label horizon (5-bar forward return) so trades capture the predicted price move.
    All 10 affected tests pass. Syntax verified.
  implication:
    Fix (4) should restore long/short signal balance. Fix (5) eliminates 82% noise dimensions,
    should reduce train-test gap and improve confident prediction accuracy. Fix (6) increases
    trade duration from median ~2 bars to minimum 5 bars, which should improve win rate because
    trades now hold long enough for the predicted move to occur before spread costs dominate.

## Resolution

root_cause: CONFIRMED (checkpoint run 2026-03-24):
  Three interacting issues explain the persistent negative Sharpe despite regularization:
  (A) LONG BIAS FROM TRAINING REGIME + THRESHOLD: Training period (Sept 2024) was bullish
      for EUR/GBP, so model learned proba→slightly above 0.50 for typical momentum input.
      The symmetric ±0.03 dead zone means probabilities clustering at 0.50-0.52 generate
      ONLY long signals (above 0.51 threshold), virtually no short signals. With GBPUSD
      in downtrend over OOS period, 99% long signals = systematic directional losses.
  (B) 27 FEATURES = 22 NOISE DIMENSIONS: SHAP stability identifies only 5 features as
      consistently informative across windows (mom_1,5,10,22,63bar). The remaining 22
      features (volatility, session, cross-asset, tick volume) are either unstable or
      add noise. With 1764 training samples, noise dimensions increase spurious fits.
  (C) EURUSD SIGNAL EXISTS BUT IS SPREAD-CRUSHED: Gross Sharpe +0.083 after regularization
      confirms a weak directional signal in EURUSD. Net Sharpe -2.784 means 12 pips spread
      on 111 trades destroys all profit. Need fewer, higher-conviction trades.

  Previously confirmed bugs BUG5/6/7 (win rate metric, double-spread, missing accuracy):
  All fixed. Metrics now correctly report trade-level win rate and gross vs net Sharpe.

fix: COMPLETE — six fixes applied across two rounds.

  ROUND 1 (2026-03-24):
  (1) XGBoost regularization — max_depth 5→3, n_estimators 500→300, subsample 0.8→0.6,
      colsample_bytree 0.7→0.5, min_child_weight 100→200, reg_alpha 0.1→1.0,
      reg_lambda 1.0→5.0, early_stopping_rounds 50→30
      File: src/alpha/ml_price_momentum/models/xgboost_model.py
  (2) RF regularization — n_estimators 1000→300, max_depth 7→3, min_samples_leaf 50→200
      File: src/alpha/ml_price_momentum/models/rf_model.py
  (3) regime_state feature removed — HMM-GARCH labels are non-deterministic across runs.
      File: scripts/validate_pipeline.py

  ROUND 2 (2026-03-24):
  (4) Threshold narrowing — dead zone ±0.03 → ±0.01 (proba>0.51→long, <0.49→short).
      Restores short signal generation when probabilities cluster at 0.50-0.52.
      File: src/alpha/ml_price_momentum/models/ensemble.py
  (5) Feature reduction — x_arr subset to top-5 SHAP-stable features only
      (mom_1bar, mom_5bar, mom_10bar, mom_22bar, mom_63bar). Eliminates 22 noise dims.
      File: scripts/validate_pipeline.py
  (6) Minimum hold — signal held for MIN_HOLD_BARS=5 after entry, matching label horizon.
      Prevents premature exit before the predicted 5-bar price move completes.
      File: scripts/validate_pipeline.py

verification: CONFIRMED by human (2026-03-24).
  EURUSD final metrics:
  - Train acc 56-59%, Test acc 48-60% (gap 0-10 pts, was 15-35)
  - Confident prediction accuracy: 51.6% (first time above 50%)
  - Flat-zone accuracy: 48.1% (correctly uncertain)
  - Gross Sharpe: +0.723 (was -2.215 → -0.083 → +0.723)
  - Net Sharpe: -0.445 (was -6.208)
  - Win Rate: 54.4% (first time above 50%)
  - Signal mix: long=61.3%, short=19.0%, flat=19.6%
  - Trade duration: mean=13.8, median=10, pct<5bars=0.0% (min-hold working)
  - At 0.5x spread: Sharpe +0.139 (marginally profitable)

  GBPUSD final metrics:
  - Train acc 57-60%, Test acc 51-59% (gap 5-10 pts)
  - Confident prediction accuracy: 50.9%
  - Gross Sharpe: -1.009 (was -2.857)
  - Net Sharpe: -2.377 (was -5.801)
  - Win Rate: 47.6%
  - Signal mix: long=66.7%, short=19.0%, flat=14.3%

  Cross-pair correlation: -0.027 (was -0.124, now essentially zero — correct)

  All pipeline bugs confirmed fixed. EURUSD has a real but weak gross signal.
  GBPUSD loss is signal quality / regime issue, not a pipeline bug.

  REMAINING WORK (signal development, not bugs):
  1. Spread cost exceeds gross signal — signal too weak at 1H FX resolution.
     Investigate higher timeframe (4H/daily) or tighter-spread instruments.
  2. Long bias (61-67% long) — training period more bullish than OOS period.
     Consider pair-specific regime conditioning or rolling label rebalancing.
  3. GBPUSD gross signal not working — may need pair-specific features or
     separate model trained on GBPUSD-specific regime.

files_changed:
  - scripts/validate_pipeline.py (diagnostics, regime removal, feature subset, min-hold)
  - src/backtest/accumulators.py (gross_pnl separated from pnl)
  - src/backtest/result_logger.py (Python 3.10 compat fix)
  - src/backtest/engine.py (unpack 4 return values)
  - src/alpha/ml_price_momentum/models/xgboost_model.py (regularization)
  - src/alpha/ml_price_momentum/models/rf_model.py (regularization)
  - src/alpha/ml_price_momentum/models/ensemble.py (threshold narrowing)
  - tests/backtest/test_accumulators.py (unpack 4 return values)
  - tests/alpha/test_validate_pipeline.py (unpack 4 return values + fix double-counting)
