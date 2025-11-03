"""Audit trail exporter."""

from __future__ import annotations

import csv
from datetime import datetime
from typing import Callable

from accountantiq_schemas import ProfileDefinition, ReviewItem

from .workspace import outputs_path

_FIELD_RESOLVERS: dict[str, Callable[[ReviewItem], str]] = {
    "transaction_id": lambda item: item.txn.id,
    "date": lambda item: item.txn.date.isoformat(),
    "details": lambda item: item.txn.description_raw,
    "description": lambda item: item.txn.description_raw,
    "account_id": lambda item: item.txn.account_id,
    "direction": lambda item: item.txn.direction,
    "nominal_code": lambda item: (
        item.nominal_final or item.suggestion.nominal_suggested or ""
    ),
    "tax_code": lambda item: (
        item.tax_code_final or item.suggestion.tax_code_suggested or ""
    ),
    "net_amount": lambda item: f"{item.txn.amount:.2f}",
    "confidence": lambda item: f"{int(round(item.suggestion.confidence * 100))}",
    "status": lambda item: item.status.value,
}


def build_row(item: ReviewItem, profile: ProfileDefinition) -> list[str]:
    row: list[str] = []
    for column in profile.columns:
        resolver = _FIELD_RESOLVERS.get(column.field)
        value = resolver(item) if resolver else ""
        row.append(value)
    return row


def export_review(
    client_slug: str,
    items: list[ReviewItem],
    profile: ProfileDefinition,
) -> str:
    output_dir = outputs_path(client_slug)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"sage_import_{timestamp}.csv"
    destination = output_dir / filename

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([column.header for column in profile.columns])
        for item in items:
            writer.writerow(build_row(item, profile))

    return str(destination)
