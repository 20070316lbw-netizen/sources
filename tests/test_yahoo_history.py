from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pandas as pd

from sources.yahoo.history import save_yahoo_history


def yahoo_frame(*symbols: str) -> pd.DataFrame:
    columns = pd.MultiIndex.from_product(
        [symbols, ["Open", "Close"]], names=["Ticker", "Price"]
    )
    return pd.DataFrame(
        [[100.0 + offset for offset in range(len(columns))]],
        index=pd.DatetimeIndex(["2026-01-02"], name="Date"),
        columns=columns,
    )


class SaveYahooHistoryTests(unittest.TestCase):
    def test_requires_a_symbol_source(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "history.parquet"

            with self.assertRaisesRegex(ValueError, "symbol source"):
                save_yahoo_history(
                    start="2026-01-01",
                    days=5,
                    output=output,
                )

    def test_rejects_multiple_symbol_sources(self) -> None:
        with TemporaryDirectory() as directory:
            universe_csv = Path(directory) / "sp500.csv"
            universe_csv.write_text("symbol\nMMM\n")
            output = Path(directory) / "history.parquet"

            with self.assertRaisesRegex(ValueError, "only one symbol source"):
                save_yahoo_history(
                    symbols=["AAPL"],
                    universe_csv=universe_csv,
                    start="2026-01-01",
                    days=5,
                    output=output,
                )

    def test_requires_positive_days(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "history.parquet"

            with self.assertRaisesRegex(ValueError, "days must be positive"):
                save_yahoo_history(
                    symbols=["AAPL"],
                    start="2026-01-01",
                    days=0,
                    output=output,
                )

    def test_requires_symbol_column_in_universe_csv(self) -> None:
        with TemporaryDirectory() as directory:
            universe_csv = Path(directory) / "sp500.csv"
            universe_csv.write_text("ticker\nAAPL\n")
            output = Path(directory) / "history.parquet"

            with self.assertRaisesRegex(ValueError, "symbol column"):
                save_yahoo_history(
                    universe_csv=universe_csv,
                    start="2026-01-01",
                    days=5,
                    output=output,
                )

    def test_requires_at_least_one_symbol(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "history.parquet"

            with self.assertRaisesRegex(ValueError, "at least one symbol"):
                save_yahoo_history(
                    symbols=[],
                    start="2026-01-01",
                    days=5,
                    output=output,
                )

    @patch("sources.yahoo.history.yf.download")
    def test_saves_requested_symbols_for_the_natural_day_window(
        self, download: Mock
    ) -> None:
        download.return_value = yahoo_frame("BRK-B", "AAPL")

        with TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "history.parquet"

            saved_path = save_yahoo_history(
                symbols=["BRK.B", "AAPL"],
                start="2026-01-01",
                days=10,
                output=output,
            )

            saved = pd.read_parquet(output)
            self.assertEqual(saved_path, output)
            self.assertEqual(
                saved.columns.tolist(),
                [
                    ("BRK.B", "Open"),
                    ("BRK.B", "Close"),
                    ("AAPL", "Open"),
                    ("AAPL", "Close"),
                ],
            )
            self.assertEqual(saved.columns.names, ["symbol", "field"])
            self.assertEqual(saved.index.name, "date")

        download.assert_called_once_with(
            tickers=["BRK-B", "AAPL"],
            start="2026-01-01",
            end="2026-01-11",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            progress=False,
            multi_level_index=True,
        )

    @patch("sources.yahoo.history.yf.download")
    def test_saves_all_symbols_from_a_universe_csv(self, download: Mock) -> None:
        download.return_value = yahoo_frame("MMM", "AAPL")

        with TemporaryDirectory() as directory:
            universe_csv = Path(directory) / "sp500.csv"
            universe_csv.write_text("symbol\nMMM\nAAPL\n")
            output = Path(directory) / "history.parquet"

            save_yahoo_history(
                universe_csv=universe_csv,
                start="2026-01-01",
                days=5,
                output=output,
            )

            saved = pd.read_parquet(output)
            self.assertEqual(
                saved.columns.get_level_values("symbol").unique().tolist(),
                ["MMM", "AAPL"],
            )


if __name__ == "__main__":
    unittest.main()
