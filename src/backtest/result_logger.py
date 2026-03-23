"""
Backtest Result Logger

Utility for appending backtest results to the trading journal (backtest_log.csv).
Ensures consistent formatting, deduplication, and audit trail.

Usage:
    from src.backtest.result_logger import BacktestLogger

    logger = BacktestLogger()
    logger.log_result(
        pair="EURUSD",
        timeframe="1H",
        metrics=BacktestMetrics(...)
    )
"""

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar


@dataclass
class BacktestMetrics:
    """Container for all backtest performance metrics."""

    pair: str
    timeframe: str
    data_period_months: int
    bars_available: int
    bars_oos: int
    config_train_window: int
    config_test_window: int
    config_purge_gap: int
    config_step: int
    num_wf_windows: int
    num_trades: int
    trades_per_bar_pct: float
    gross_sharpe: float
    net_sharpe: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    base_spread_pips: float
    stable_features: str  # Comma-separated feature names
    regime_trending_pct: float
    regime_meanrev_pct: float
    regime_volatile_pct: float
    notes: str = ""


class BacktestLogger:
    """Logs backtest results to CSV trading journal with validation."""

    JOURNAL_PATH: ClassVar[Path] = (
        Path(__file__).parent.parent.parent / "Backtest_results" / "backtest_log.csv"
    )

    # Expected CSV columns (order matters for validation)
    EXPECTED_COLUMNS: ClassVar[list[str]] = [
        "Date",
        "Pair",
        "Timeframe",
        "Data_Period_Months",
        "Bars_Available",
        "Bars_OOS",
        "Config_Train_Window",
        "Config_Test_Window",
        "Config_Purge_Gap",
        "Config_Step",
        "Num_WF_Windows",
        "Num_Trades",
        "Trades_Per_Bar_Pct",
        "Gross_Sharpe",
        "Net_Sharpe",
        "Max_Drawdown_Pct",
        "Win_Rate_Pct",
        "Profit_Factor",
        "Total_Return_Pct",
        "Base_Spread_Pips",
        "Stable_Features",
        "Regime_Trending_Pct",
        "Regime_MeanRev_Pct",
        "Regime_Volatile_Pct",
        "Notes",
    ]

    def __init__(self, journal_path: Path | None = None) -> None:
        """
        Initialize logger.

        Args:
            journal_path: Path to backtest_log.csv (defaults to Backtest_results/)
        """
        self.journal_path = journal_path or self.JOURNAL_PATH
        self._ensure_journal_exists()

    def _ensure_journal_exists(self) -> None:
        """Create journal file with headers if it doesn't exist."""
        if not self.journal_path.exists():
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.EXPECTED_COLUMNS)
                writer.writeheader()

    def log_result(
        self, metrics: BacktestMetrics, date: datetime | None = None
    ) -> None:
        """
        Append a backtest result to the journal.

        Args:
            metrics: BacktestMetrics dataclass with all performance data
            date: Backtest date (defaults to today)

        Raises:
            ValueError: If metrics contain invalid data
        """
        date = date or datetime.now(tz=UTC)

        row: dict[str, str | int | float] = {
            "Date": date.strftime("%Y-%m-%d"),
            "Pair": metrics.pair,
            "Timeframe": metrics.timeframe,
            "Data_Period_Months": metrics.data_period_months,
            "Bars_Available": metrics.bars_available,
            "Bars_OOS": metrics.bars_oos,
            "Config_Train_Window": metrics.config_train_window,
            "Config_Test_Window": metrics.config_test_window,
            "Config_Purge_Gap": metrics.config_purge_gap,
            "Config_Step": metrics.config_step,
            "Num_WF_Windows": metrics.num_wf_windows,
            "Num_Trades": metrics.num_trades,
            "Trades_Per_Bar_Pct": f"{metrics.trades_per_bar_pct:.1f}",
            "Gross_Sharpe": f"{metrics.gross_sharpe:.3f}",
            "Net_Sharpe": f"{metrics.net_sharpe:.3f}",
            "Max_Drawdown_Pct": f"{metrics.max_drawdown_pct:.1f}",
            "Win_Rate_Pct": f"{metrics.win_rate_pct:.1f}",
            "Profit_Factor": f"{metrics.profit_factor:.3f}",
            "Total_Return_Pct": f"{metrics.total_return_pct:.1f}",
            "Base_Spread_Pips": f"{metrics.base_spread_pips:.5f}",
            "Stable_Features": metrics.stable_features,
            "Regime_Trending_Pct": f"{metrics.regime_trending_pct:.1f}",
            "Regime_MeanRev_Pct": f"{metrics.regime_meanrev_pct:.1f}",
            "Regime_Volatile_Pct": f"{metrics.regime_volatile_pct:.1f}",
            "Notes": metrics.notes,
        }

        # Validate row
        self._validate_row(row)

        # Append to CSV
        with open(self.journal_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.EXPECTED_COLUMNS)
            writer.writerow(row)

        print(f"Logged backtest: {metrics.pair} on {date.strftime('%Y-%m-%d')}")

    def _validate_row(self, row: dict[str, str | int | float]) -> None:
        """
        Validate row before writing.

        Args:
            row: Dictionary with backtest result

        Raises:
            ValueError: If row contains invalid data
        """
        # Check all required columns present
        if set(row.keys()) != set(self.EXPECTED_COLUMNS):
            raise ValueError(f"Row keys mismatch. Expected: {self.EXPECTED_COLUMNS}")

        # Check pair is valid
        valid_pairs = {
            "EURUSD",
            "GBPUSD",
            "AUDUSD",
            "NZDUSD",
            "USDJPY",
            "USDCAD",
            "USDCHF",
        }
        if row["Pair"] not in valid_pairs:
            raise ValueError(f"Unknown pair: {row['Pair']}. Valid: {valid_pairs}")

        # Check Sharpe is in reasonable range (-20 to +5)
        try:
            sharpe = float(str(row["Net_Sharpe"]))
            if sharpe < -20 or sharpe > 5:
                raise ValueError(f"Net_Sharpe out of bounds: {sharpe}")
        except ValueError as e:
            raise ValueError(f"Invalid Net_Sharpe: {row['Net_Sharpe']}") from e

    def read_journal(self) -> list[dict[str, str]]:
        """Read all rows from the journal."""
        rows: list[dict[str, str]] = []
        with open(self.journal_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
        return rows

    def get_latest_by_pair(self, pair: str) -> dict[str, str] | None:
        """Get the most recent backtest row for a given pair."""
        rows = self.read_journal()
        pair_rows = [r for r in rows if r["Pair"] == pair]
        return pair_rows[-1] if pair_rows else None

    def get_best_net_sharpe(self, pair: str | None = None) -> dict[str, str] | None:
        """Get the backtest with highest Net_Sharpe."""
        rows = self.read_journal()
        if pair:
            rows = [r for r in rows if r["Pair"] == pair]

        if not rows:
            return None

        return max(rows, key=lambda r: float(r["Net_Sharpe"]))
