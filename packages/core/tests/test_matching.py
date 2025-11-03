"""Tests for the vendor matcher and confidence scoring."""

from __future__ import annotations

from pathlib import Path

from accountantiq_core import (
    BankCsvParser,
    SageHistoryParser,
    VendorMatcher,
    suggest_for_transactions,
)
from accountantiq_schemas import BankTxn, SageHistoryEntry

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"

_bank_parser = BankCsvParser()
_history_parser = SageHistoryParser()


def load_bank() -> list[BankTxn]:
    bank_files = ["bank_sample_01.csv", "bank_sample_02.csv"]
    txns: list[BankTxn] = []
    for filename in bank_files:
        txns.extend(_bank_parser.parse(EXAMPLES_DIR / filename))
    return txns


def load_history() -> list[SageHistoryEntry]:
    return _history_parser.parse(EXAMPLES_DIR / "sage_history_sample.csv")


def test_vendor_matcher_returns_high_confidence_for_known_vendor() -> None:
    match = VendorMatcher(load_history())
    bank_txn = load_bank()[0]

    suggestion = match.suggest(bank_txn)

    assert suggestion.nominal_suggested == "5100"
    assert suggestion.tax_code_suggested == "T1"
    assert suggestion.confidence >= 0.7
    assert any("vendor" in note.lower() for note in suggestion.explanations)


def test_vendor_matcher_handles_unknown_vendor_gracefully() -> None:
    match = VendorMatcher(load_history())
    amazon_txn = next(txn for txn in load_bank() if "amazon" in txn.description_clean)

    suggestion = match.suggest(amazon_txn)

    assert suggestion.nominal_suggested is None
    assert suggestion.confidence == 0.0
    assert "no high-confidence" in suggestion.explanations[0].lower()


def test_suggest_for_transactions_matches_batch_output() -> None:
    bank_txns = load_bank()[:2]
    history = load_history()

    suggestions = suggest_for_transactions(bank_txns, history)

    assert len(suggestions) == len(bank_txns)
    assert suggestions[0].txn_id == bank_txns[0].id
