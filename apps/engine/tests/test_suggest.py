"""Integration tests for engine endpoints."""

from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

from accountantiq_core import BankCsvParser, SageHistoryParser
from accountantiq_engine.main import app
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples"
CLIENTS_ROOT = REPO_ROOT / "data" / "clients"

client = TestClient(app)
bank_parser = BankCsvParser()
history_parser = SageHistoryParser()


def _build_csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue().strip()


def _sample_bank_csv() -> str:
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
    return _build_csv(rows)


def _sample_history_csv() -> str:
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
    return _build_csv(rows)


def _reset_client(client_slug: str) -> None:
    root = CLIENTS_ROOT / client_slug
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


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


def test_review_workflow_happy_path() -> None:
    client_slug = "test_review_client"
    _reset_client(client_slug)

    import_payload = {
        "client_slug": client_slug,
        "bank_csv": _sample_bank_csv(),
        "history_csv": _sample_history_csv(),
        "reset": True,
    }

    response = client.post("/review/import", json=import_payload)
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("rules_created") is None
    queue = payload["items"]
    assert len(queue) == 2

    first_txn = queue[0]["txn"]["id"]
    second_txn = queue[1]["txn"]["id"]

    approve_response = client.post(
        f"/review/{client_slug}/items/{first_txn}/approve",
        json={"note": "Looks good"},
    )
    assert approve_response.status_code == 200
    override_response = client.post(
        f"/review/{client_slug}/items/{second_txn}/override",
        json={"nominal_code": "8200", "tax_code": "T1", "note": "Manual override"},
    )
    assert override_response.status_code == 200

    rule_response = client.post(
        f"/review/{client_slug}/rules",
        json={
            "name": "Amazon rule",
            "pattern": "amazon",
            "nominal": "5000",
            "tax_code": "T9",
        },
    )
    assert rule_response.status_code == 200
    assert len(rule_response.json()) == 1

    auto_rules_response = client.post(f"/review/{client_slug}/auto-rules")
    assert auto_rules_response.status_code == 200
    auto_payload = auto_rules_response.json()
    assert auto_payload["created"] >= 0

    response = client.post(
        "/review/import",
        json={
            "client_slug": client_slug,
            "bank_csv": _sample_bank_csv(),
            "history_csv": _sample_history_csv(),
            "reset": True,
            "auto_rules": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("rules_created") is not None

    queue_response = client.get(f"/review/{client_slug}/queue")
    items = queue_response.json()["items"]
    amazon_item = next(
        item for item in items if "amazon" in item["txn"]["description_clean"]
    )
    assert amazon_item["suggestion"]["nominal_suggested"] == "5000"
    assert amazon_item["suggestion"]["tax_code_suggested"] == "T9"

    for item in items:
        txn_id = item["txn"]["id"]
        client.post(f"/review/{client_slug}/items/{txn_id}/approve")

    export_response = client.post(
        f"/review/{client_slug}/export", json={"profile_name": "default"}
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    exported_path = Path(export_payload["exported_path"])
    assert exported_path.exists()
    assert export_payload["row_count"] == len(items)

    _reset_client(client_slug)
