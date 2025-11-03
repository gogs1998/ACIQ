"""Tests for the Stage 1 CSV parsers."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from accountantiq_core import BankCsvParser, SageHistoryParser, clean_description

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _build_csv(rows: list[list[str]]) -> io.StringIO:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    buffer.seek(0)
    return buffer


def test_bank_parser_normalises_example_bank_csv() -> None:
    parser = BankCsvParser()
    txns = parser.parse(EXAMPLES_DIR / "bank_sample_01.csv")

    assert len(txns) == 3
    first = txns[0]
    assert first.direction == "debit"
    assert first.description_clean == "wrights uk ltd inv"
    assert first.account_id == "BAILLI-CHK"


def test_sage_history_parser_extracts_vendor_hint() -> None:
    parser = SageHistoryParser()
    entries = parser.parse(EXAMPLES_DIR / "sage_history_sample.csv")

    assert len(entries) == 3
    wrights = entries[0]
    assert wrights.vendor_hint == "wrights uk ltd"
    assert wrights.nominal_code == "5100"


def test_clean_description_removes_dates_and_numbers() -> None:
    raw = "ACME SUPPLIES 22/01/25 INV 104948"
    assert clean_description(raw) == "acme supplies inv"


def test_bank_parser_handles_headerless_sage_export() -> None:
    rows = [
        [
            "1210",
            "Bank Current A/C- Ltd Co",
            "5178",
            "BR",
            "26/05/2023",
            "1105",
            "61",
            "APPLE",
            "59.00",
            "0.00",
            "59.00",
            "N",
            "",
            "59.00",
            "0.00",
            "59.00",
        ],
        [
            "1210",
            "Bank Current A/C- Ltd Co",
            "6006",
            "BP",
            "03/04/2023",
            "5000",
            "0",
            "AMAZON",
            "0.00",
            "0.00",
            "-3.98",
            "N",
            "",
            "-3.98",
            "0.00",
            "-3.98",
        ],
    ]
    parser = BankCsvParser()
    txns = parser.parse(_build_csv(rows))

    assert len(txns) == 2
    assert txns[0].amount == 59.0
    assert txns[1].amount == -3.98
    assert txns[1].direction == "debit"
    assert "amazon" in txns[1].description_clean


def test_sage_history_parser_handles_audit_trail_export_without_headers() -> None:
    rows = [
        [
            "6006",
            "BP",
            "1210",
            "03/04/2023",
            "11",
            "0.00",
            "19.05",
            "Y",
            "19.05",
            "N",
            "",
            "6006",
            "5000",
            "0",
            "AMAZON",
            "0.00",
            "3.98",
            "T9",
            "3.98",
            " -",
            "",
            "",
            "",
            "0.00",
        ],
        [
            "5178",
            "BR",
            "1210",
            "26/05/2023",
            "61",
            "466.00",
            "0.00",
            "Y",
            "466.00",
            "N",
            "",
            "5178",
            "1105",
            "0",
            "APPLE",
            "59.00",
            "0.00",
            "T9",
            "59.00",
            " -",
            "",
            "",
            "",
            "0.00",
        ],
    ]
    parser = SageHistoryParser()
    entries = parser.parse(_build_csv(rows))

    assert len(entries) == 2
    amazon, apple = entries
    assert amazon.amount == -3.98
    assert amazon.tax_code == "T9"
    assert apple.amount == 59.0
    assert amazon.nominal_code == "5000"
    assert apple.nominal_code == "1105"
