"""Integration tests for the suggest endpoints."""

from __future__ import annotations

from pathlib import Path

from accountantiq_core import BankCsvParser, SageHistoryParser
from accountantiq_engine.main import app
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"

client = TestClient(app)
bank_parser = BankCsvParser()
history_parser = SageHistoryParser()


def test_suggest_endpoint_returns_suggestions() -> None:
    transactions = bank_parser.parse(EXAMPLES_DIR / "bank_sample_01.csv")
    history = history_parser.parse(EXAMPLES_DIR / "sage_history_sample.csv")

    payload = {
        "transactions": [txn.model_dump(mode="json") for txn in transactions],
        "history": [entry.model_dump(mode="json") for entry in history],
    }

    response = client.post("/suggest", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert len(data["suggestions"]) == len(transactions)
    assert data["suggestions"][0]["nominal_suggested"] == "5100"
    assert data["suggestions"][0]["tax_code_suggested"] == "T1"


def test_suggest_from_csv_endpoint_parses_and_scores() -> None:
    payload = {
        "bank_csv": (EXAMPLES_DIR / "bank_sample_01.csv").read_text(encoding="utf-8"),
        "history_csv": (EXAMPLES_DIR / "sage_history_sample.csv").read_text(
            encoding="utf-8"
        ),
    }

    response = client.post("/suggest/from-csv", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert len(data["transactions"]) == 3
    assert len(data["suggestions"]) == 3
    assert data["transactions"][0]["description_clean"].startswith("wrights uk")
    assert data["suggestions"][0]["confidence"] > 0.5
