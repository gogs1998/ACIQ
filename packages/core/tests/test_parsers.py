"""Tests for the Stage 1 CSV parsers."""

from __future__ import annotations

from pathlib import Path

from accountantiq_core import BankCsvParser, SageHistoryParser, clean_description

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"


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
