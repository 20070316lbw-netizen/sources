from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf


def save_yahoo_history(
    *,
    symbols: Sequence[str] | None = None,
    universe_csv: str | Path | None = None,
    start: str | date,
    days: int,
    output: str | Path,
) -> Path:
    """Download daily Yahoo history and save it as a Parquet file."""
    if days <= 0:
        raise ValueError("days must be positive")

    start_date = date.fromisoformat(start) if isinstance(start, str) else start
    end_date = start_date + timedelta(days=days)

    if symbols is None and universe_csv is None:
        raise ValueError("provide a symbol source: symbols or universe_csv")
    if symbols is not None and universe_csv is not None:
        raise ValueError("provide only one symbol source")

    if symbols is None:
        with Path(universe_csv).open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None or "symbol" not in reader.fieldnames:
                raise ValueError("universe CSV must contain a symbol column")
            symbols = [row["symbol"] for row in reader]

    canonical_symbols = [
        symbol.strip().upper() for symbol in symbols if symbol.strip()
    ]
    if not canonical_symbols:
        raise ValueError("provide at least one symbol")

    yahoo_symbols = [symbol.replace(".", "-") for symbol in canonical_symbols]
    yahoo_to_canonical = dict(zip(yahoo_symbols, canonical_symbols, strict=True))

    history = yf.download(
        tickers=yahoo_symbols,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        actions=False,
        progress=False,
        multi_level_index=True,
    )
    if history is None or history.empty:
        raise ValueError("Yahoo returned no history for the requested window")

    history = history.rename(columns=yahoo_to_canonical, level=0)
    history.columns.names = ["symbol", "field"]
    history.index.name = "date"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    history.to_parquet(output_path)
    return output_path
