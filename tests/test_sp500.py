from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from sources.universe.sp500 import fetch_sp500_symbols, save_sp500_csv


CONSTITUENTS_HTML = """
<table id="constituents">
  <thead><tr><th>Symbol</th><th>Security</th></tr></thead>
  <tbody>
    <tr><td>MMM</td><td>3M</td></tr>
    <tr><td>AAPL</td><td>Apple Inc.</td></tr>
    <tr><td>BRK.B</td><td>Berkshire Hathaway</td></tr>
  </tbody>
</table>
"""


class FetchSp500SymbolsTests(unittest.TestCase):
    @patch("sources.universe.sp500.requests.get")
    def test_returns_symbols_from_the_sp500_constituents_table(
        self, get: Mock
    ) -> None:
        response = Mock()
        response.text = CONSTITUENTS_HTML
        get.return_value = response

        symbols = fetch_sp500_symbols()

        self.assertEqual(symbols, ["MMM", "AAPL", "BRK.B"])

    @patch("sources.universe.sp500.requests.get")
    def test_saves_symbols_to_csv(self, get: Mock) -> None:
        response = Mock()
        response.text = CONSTITUENTS_HTML
        get.return_value = response

        with TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "sp500.csv"

            saved_path = save_sp500_csv(output)

            self.assertEqual(saved_path, output)
            self.assertEqual(
                output.read_text(), "symbol\nMMM\nAAPL\nBRK.B\n"
            )


if __name__ == "__main__":
    unittest.main()
