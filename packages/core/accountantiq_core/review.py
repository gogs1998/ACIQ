"""Review queue storage backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence, cast

from accountantiq_schemas import (
    ApprovalRequest,
    BankTxn,
    OverrideRequest,
    ReviewItem,
    ReviewStatus,
    Suggestion,
)

from .workspace import review_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_items (
    txn_id TEXT PRIMARY KEY,
    txn_json TEXT NOT NULL,
    suggestion_json TEXT NOT NULL,
    status TEXT NOT NULL,
    nominal_final TEXT,
    tax_code_final TEXT,
    notes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewStore:
    """Provide CRUD semantics for the review queue."""

    def __init__(self, client_slug: str) -> None:
        self.client_slug = client_slug
        self.db_path = review_db_path(client_slug)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def import_batch(
        self,
        txns: Sequence[BankTxn],
        suggestions: Sequence[Suggestion],
        reset: bool = True,
    ) -> list[ReviewItem]:
        if len(txns) != len(suggestions):
            msg = "Transactions and suggestions must be the same length"
            raise ValueError(msg)
        now = _utc_now().isoformat()
        with self._connect() as conn:
            if reset:
                conn.execute("DELETE FROM review_items")
            for txn, suggestion in zip(txns, suggestions, strict=True):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO review_items (
                        txn_id,
                        txn_json,
                        suggestion_json,
                        status,
                        nominal_final,
                        tax_code_final,
                        notes_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        txn.id,
                        json.dumps(txn.model_dump(mode="json")),
                        json.dumps(suggestion.model_dump(mode="json")),
                        ReviewStatus.PENDING.value,
                        suggestion.nominal_suggested,
                        suggestion.tax_code_suggested,
                        json.dumps([]),
                        now,
                        now,
                    ),
                )
        return self.list_items()

    def list_items(self) -> list[ReviewItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def approve(
        self, txn_id: str, payload: ApprovalRequest | None = None
    ) -> ReviewItem:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_items WHERE txn_id = ?",
                (txn_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Transaction {txn_id} not found in review queue")
            notes = json.loads(row["notes_json"])
            if payload and payload.note:
                notes.append(payload.note)
            conn.execute(
                """
                UPDATE review_items
                SET status = ?,
                    nominal_final = CASE
                        WHEN nominal_final IS NULL THEN ?
                        ELSE nominal_final
                    END,
                    tax_code_final = CASE
                        WHEN tax_code_final IS NULL THEN ?
                        ELSE tax_code_final
                    END,
                    notes_json = ?,
                    updated_at = ?
                WHERE txn_id = ?
                """,
                (
                    ReviewStatus.APPROVED.value,
                    self._suggestion_value(
                        row, "nominal_final", "suggestion_json", "nominal_suggested"
                    ),
                    self._suggestion_value(
                        row, "tax_code_final", "suggestion_json", "tax_code_suggested"
                    ),
                    json.dumps(notes),
                    _utc_now().isoformat(),
                    txn_id,
                ),
            )
        return self.get_item(txn_id)

    def override(self, txn_id: str, payload: OverrideRequest) -> ReviewItem:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_items WHERE txn_id = ?",
                (txn_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Transaction {txn_id} not found in review queue")
            notes = json.loads(row["notes_json"])
            if payload.note:
                notes.append(payload.note)
            conn.execute(
                """
                UPDATE review_items
                SET status = ?,
                    nominal_final = ?,
                    tax_code_final = ?,
                    notes_json = ?,
                    updated_at = ?
                WHERE txn_id = ?
                """,
                (
                    ReviewStatus.OVERRIDDEN.value,
                    payload.nominal_code,
                    payload.tax_code,
                    json.dumps(notes),
                    _utc_now().isoformat(),
                    txn_id,
                ),
            )
        return self.get_item(txn_id)

    def get_item(self, txn_id: str) -> ReviewItem:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_items WHERE txn_id = ?",
                (txn_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Transaction {txn_id} not found in review queue")
        return self._row_to_item(row)

    @staticmethod
    def _suggestion_value(
        row: sqlite3.Row,
        column: str,
        suggestion_column: str,
        suggestion_key: str,
    ) -> str | None:
        current = row[column]
        if current is not None:
            return cast(str, current)
        suggestion_payload = json.loads(row[suggestion_column])
        value: Any = suggestion_payload.get(suggestion_key)
        return cast(str | None, value)

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> ReviewItem:
        txn = BankTxn.model_validate_json(row["txn_json"])
        suggestion = Suggestion.model_validate_json(row["suggestion_json"])
        status = ReviewStatus(row["status"])
        notes = json.loads(row["notes_json"]) or []
        return ReviewItem(
            txn=txn,
            suggestion=suggestion,
            status=status,
            nominal_final=row["nominal_final"],
            tax_code_final=row["tax_code_final"],
            notes=notes,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def pending_items(items: Iterable[ReviewItem]) -> list[ReviewItem]:
    return [item for item in items if item.status == ReviewStatus.PENDING]


def approved_items(items: Iterable[ReviewItem]) -> list[ReviewItem]:
    return [item for item in items if item.status != ReviewStatus.PENDING]
