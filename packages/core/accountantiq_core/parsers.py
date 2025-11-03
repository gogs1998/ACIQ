"""CSV parsers and normalisation helpers."""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar, Mapping, Sequence, Union

from accountantiq_schemas import BankTxn, Direction, SageHistoryEntry

_DATE_FORMATS: Sequence[str] = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
)

_NON_ALPHA_RE = re.compile(r"[^a-z\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")
_DATE_TOKEN_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_NUMERIC_TOKEN_RE = re.compile(r"\b\d+\b")


def clean_description(raw: str) -> str:
    """Normalise descriptions for matching by stripping noise."""
    lowered = raw.lower()
    without_dates = _DATE_TOKEN_RE.sub(" ", lowered)
    without_numbers = _NUMERIC_TOKEN_RE.sub(" ", without_dates)
    alpha_only = _NON_ALPHA_RE.sub(" ", without_numbers)
    squashed = _MULTI_SPACE_RE.sub(" ", alpha_only)
    return squashed.strip()


def _parse_date(value: str) -> date:
    candidate = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(candidate).date()
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise ValueError(f"Unsupported date format: {value}") from exc


def _parse_amount(value: str) -> float:
    cleaned = value.replace(",", "").strip()
    if cleaned == "":
        raise ValueError("Amount column cannot be empty")
    return float(cleaned)


def _deterministic_id(*parts: str) -> str:
    key = "|".join(part.strip() for part in parts)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _resolve_field(row: Mapping[str, str], candidates: Sequence[str]) -> str:
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    raise KeyError(f"Could not resolve any of {candidates} in row: {row}")


@dataclass(slots=True)
class BankCsvParser:
    """Parse bank CSV exports into the canonical schema."""

    date_headers: ClassVar[tuple[str, ...]] = ("date", "transaction date")
    amount_headers: ClassVar[tuple[str, ...]] = ("amount", "value", "net amount")
    description_headers: ClassVar[tuple[str, ...]] = (
        "description",
        "details",
        "narrative",
        "description_raw",
    )
    account_headers: ClassVar[tuple[str, ...]] = (
        "account",
        "account id",
        "account number",
    )

    def parse(self, source: Union[Path, str, io.TextIOBase]) -> list[BankTxn]:
        with _ensure_text_io(source) as handle:
            reader = csv.DictReader(handle)
            results: list[BankTxn] = []
            for idx, row in enumerate(reader, start=1):
                normalised_row = {
                    key.strip().lower(): value.strip()
                    for key, value in row.items()
                    if value is not None
                }
                date_raw = _resolve_field(normalised_row, self.date_headers)
                amount_raw = _resolve_field(normalised_row, self.amount_headers)
                description_raw = _resolve_field(
                    normalised_row, self.description_headers
                )
                try:
                    account_raw = _resolve_field(normalised_row, self.account_headers)
                except KeyError:
                    account_raw = "default"

                parsed_amount = _parse_amount(amount_raw)
                direction: Direction = "debit" if parsed_amount < 0 else "credit"

                clean = clean_description(description_raw)
                txn_id = _deterministic_id(
                    date_raw, amount_raw, description_raw, str(idx)
                )

                results.append(
                    BankTxn(
                        id=txn_id,
                        date=_parse_date(date_raw),
                        amount=parsed_amount,
                        direction=direction,
                        description_raw=description_raw,
                        description_clean=clean,
                        account_id=account_raw or "default",
                    )
                )
        return results


@dataclass(slots=True)
class SageHistoryParser:
    """Parse Sage history exports to the canonical schema."""

    date_headers: ClassVar[tuple[str, ...]] = ("date",)
    net_amount_headers: ClassVar[tuple[str, ...]] = ("net amount", "net")
    details_headers: ClassVar[tuple[str, ...]] = ("details", "description")
    nominal_headers: ClassVar[tuple[str, ...]] = ("nominal code", "account")
    tax_code_headers: ClassVar[tuple[str, ...]] = ("tax code", "tax")
    reference_headers: ClassVar[tuple[str, ...]] = ("reference", "ref")

    def parse(self, source: Union[Path, str, io.TextIOBase]) -> list[SageHistoryEntry]:
        with _ensure_text_io(source) as handle:
            reader = csv.DictReader(handle)
            results: list[SageHistoryEntry] = []
            for idx, row in enumerate(reader, start=1):
                normalised_row = {
                    key.strip().lower(): value.strip()
                    for key, value in row.items()
                    if value is not None
                }
                date_raw = _resolve_field(normalised_row, self.date_headers)
                amount_raw = _resolve_field(normalised_row, self.net_amount_headers)
                description_raw = _resolve_field(normalised_row, self.details_headers)
                nominal_raw = _resolve_field(normalised_row, self.nominal_headers)
                tax_code_raw = _resolve_field(normalised_row, self.tax_code_headers)
                reference_raw = normalised_row.get(self.reference_headers[0], str(idx))

                clean = clean_description(description_raw)
                vendor_hint = self._derive_vendor_hint(clean)
                entry_id = _deterministic_id(
                    date_raw,
                    amount_raw,
                    description_raw,
                    nominal_raw,
                    reference_raw,
                )

                results.append(
                    SageHistoryEntry(
                        id=entry_id,
                        date=_parse_date(date_raw),
                        amount=_parse_amount(amount_raw),
                        nominal_code=nominal_raw,
                        tax_code=tax_code_raw,
                        description_raw=description_raw,
                        description_clean=clean,
                        vendor_hint=vendor_hint,
                    )
                )
        return results

    @staticmethod
    def _derive_vendor_hint(cleaned_description: str) -> str | None:
        if not cleaned_description:
            return None
        tokens = cleaned_description.split()
        if not tokens:
            return None
        return " ".join(tokens[:3])


class _TempFileWrapper:
    """Context manager ensuring all sources act like TextIO."""

    def __init__(self, handle: io.TextIOBase, close: bool) -> None:
        self._handle = handle
        self._close = close

    def __enter__(self) -> io.TextIOBase:
        return self._handle

    def __exit__(self, *_args: object) -> None:
        if self._close:
            self._handle.close()


def _ensure_text_io(source: Union[Path, str, io.TextIOBase]) -> _TempFileWrapper:
    if isinstance(source, io.TextIOBase):
        return _TempFileWrapper(source, close=False)
    path = Path(source)
    handle = path.open("r", encoding="utf-8")
    return _TempFileWrapper(handle, close=True)


__all__ = ["BankCsvParser", "SageHistoryParser", "clean_description"]
