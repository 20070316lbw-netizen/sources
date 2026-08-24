from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import pandas as pd
import requests


SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500_symbols() -> list[str]:
    """Fetch the current S&P 500 constituent symbols."""
    response = requests.get(
        SP500_URL,
        headers={"User-Agent": "sources/0.1 (+https://en.wikipedia.org/)"},
        timeout=30,
    )
    response.raise_for_status()

    table = pd.read_html(
        StringIO(response.text), attrs={"id": "constituents"}
    )[0]
    return table["Symbol"].astype(str).str.strip().tolist()


def save_sp500_csv(output: str | Path) -> Path:
    """Fetch the S&P 500 symbols and save them as a CSV file."""
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["symbol"])
        writer.writerows([symbol] for symbol in fetch_sp500_symbols())

    return output_path
