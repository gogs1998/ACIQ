"""CSV parsers and normalisation helpers."""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar, Sequence, Union

from accountantiq_schemas import BankTxn, Direction, SageHistoryEntry

CsvSource = Union[Path, str, io.TextIOBase]

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


def _resolve_field(row: dict[str, str], candidates: Sequence[str]) -> str:
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return row[candidate]
    raise KeyError(f"Could not resolve any of {candidates} in row: {row}")


def _read_csv_rows(source: CsvSource) -> list[list[str]]:
    """Return a trimmed list of CSV rows from any supported source."""
    if isinstance(source, io.TextIOBase):
        text = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
    else:
        path = Path(source)
        text = path.read_text(encoding="utf-8-sig")
    buffer = io.StringIO(text)
    reader = csv.reader(buffer)
    rows: list[list[str]] = []
    for row in reader:
        trimmed = [cell.strip() for cell in row]
        if any(trimmed):
            rows.append(trimmed)
    return rows


def _row_looks_like_header(row: Sequence[str], expected_tokens: Sequence[str]) -> bool:
    if not row:
        return False
    lowercased = {cell.lower() for cell in row if cell}
    return any(token in lowercased for token in expected_tokens)


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
    _header_tokens: ClassVar[tuple[str, ...]] = (
        date_headers + amount_headers + description_headers
    )

    def parse(self, source: CsvSource) -> list[BankTxn]:
        rows = _read_csv_rows(source)
        if not rows:
            return []
        if _row_looks_like_header(rows[0], self._header_tokens):
            return self._parse_with_headers(rows)
        return self._parse_without_headers(rows)

    def _parse_with_headers(self, rows: list[list[str]]) -> list[BankTxn]:
        fieldnames = [cell.lower() for cell in rows[0]]
        data_rows = rows[1:]
        results: list[BankTxn] = []
        for idx, raw in enumerate(data_rows, start=1):
            if not any(raw):
                continue
            normalised_row = {
                fieldnames[col_index]: raw[col_index]
                for col_index in range(min(len(fieldnames), len(raw)))
                if fieldnames[col_index]
            }
            try:
                results.append(self._build_bank_txn(normalised_row, idx))
            except (KeyError, ValueError):
                continue
        return results

    def _parse_without_headers(self, rows: list[list[str]]) -> list[BankTxn]:
        results: list[BankTxn] = []
        for idx, raw in enumerate(rows, start=1):
            if len(raw) < 11:
                continue
            date_raw = raw[4]
            amount_raw = raw[10] or raw[8]
            if not date_raw or not amount_raw:
                continue
            description_tokens = [
                raw[7],
                raw[3] if len(raw) > 3 else "",
                raw[2] if len(raw) > 2 else "",
            ]
            description_raw = " ".join(
                token for token in description_tokens if token
            ).strip()
            if not description_raw:
                continue
            account_raw = raw[0] or (raw[1] if len(raw) > 1 else "default")
            parsed_amount = _parse_amount(amount_raw)
            direction: Direction = "debit" if parsed_amount < 0 else "credit"
            results.append(
                BankTxn(
                    id=_deterministic_id(
                        date_raw, amount_raw, description_raw, str(idx)
                    ),
                    date=_parse_date(date_raw),
                    amount=parsed_amount,
                    direction=direction,
                    description_raw=description_raw,
                    description_clean=clean_description(description_raw),
                    account_id=account_raw or "default",
                )
            )
        return results

    def _build_bank_txn(self, row: dict[str, str], idx: int) -> BankTxn:
        date_raw = _resolve_field(row, self.date_headers)
        amount_raw = _resolve_field(row, self.amount_headers)
        description_raw = _resolve_field(row, self.description_headers)
        try:
            account_raw = _resolve_field(row, self.account_headers)
        except KeyError:
            account_raw = "default"
        parsed_amount = _parse_amount(amount_raw)
        direction: Direction = "debit" if parsed_amount < 0 else "credit"
        clean = clean_description(description_raw)
        txn_id = _deterministic_id(date_raw, amount_raw, description_raw, str(idx))
        return BankTxn(
            id=txn_id,
            date=_parse_date(date_raw),
            amount=parsed_amount,
            direction=direction,
            description_raw=description_raw,
            description_clean=clean,
            account_id=account_raw or "default",
        )


@dataclass(slots=True)
class SageHistoryParser:
    """Parse Sage history exports to the canonical schema."""

    date_headers: ClassVar[tuple[str, ...]] = ("date",)
    net_amount_headers: ClassVar[tuple[str, ...]] = ("net amount", "net")
    details_headers: ClassVar[tuple[str, ...]] = ("details", "description")
    nominal_headers: ClassVar[tuple[str, ...]] = ("nominal code", "account")
    tax_code_headers: ClassVar[tuple[str, ...]] = ("tax code", "tax")
    reference_headers: ClassVar[tuple[str, ...]] = ("reference", "ref")
    _header_tokens: ClassVar[tuple[str, ...]] = (
        "date",
        "details",
        "description",
        "nominal code",
        "tax code",
    )

    def parse(self, source: CsvSource) -> list[SageHistoryEntry]:
        rows = _read_csv_rows(source)
        if not rows:
            return []
        if _row_looks_like_header(rows[0], self._header_tokens):
            return self._parse_with_headers(rows)
        return self._parse_without_headers(rows)

    def _parse_with_headers(self, rows: list[list[str]]) -> list[SageHistoryEntry]:
        fieldnames = [cell.lower() for cell in rows[0]]
        data_rows = rows[1:]
        results: list[SageHistoryEntry] = []
        for idx, raw in enumerate(data_rows, start=1):
            if not any(raw):
                continue
            normalised_row = {
                fieldnames[col_index]: raw[col_index]
                for col_index in range(min(len(fieldnames), len(raw)))
                if fieldnames[col_index]
            }
            try:
                results.append(self._build_history_entry(normalised_row, idx))
            except (KeyError, ValueError):
                continue
        return results

    def _parse_without_headers(self, rows: list[list[str]]) -> list[SageHistoryEntry]:
        results: list[SageHistoryEntry] = []
        for idx, raw in enumerate(rows, start=1):
            if len(raw) < 18:
                continue
            date_raw = raw[3]
            nominal_raw = raw[12] if len(raw) > 12 else ""
            description_raw = raw[14] if len(raw) > 14 else ""
            tax_code_raw = raw[17] if len(raw) > 17 else ""
            if not date_raw or not nominal_raw or not description_raw:
                continue
            amount_candidates = [
                raw[18] if len(raw) > 18 else "",
                raw[15] if len(raw) > 15 else "",
                raw[6] if len(raw) > 6 else "",
            ]
            amount_raw = next(
                (candidate for candidate in amount_candidates if candidate), ""
            )
            if not amount_raw:
                continue
            parsed_amount = _parse_amount(amount_raw) * _infer_audit_sign(
                raw[1] if len(raw) > 1 else ""
            )
            vendor_hint = self._derive_vendor_hint(clean_description(description_raw))
            entry_id = _deterministic_id(
                date_raw, nominal_raw, description_raw, str(idx)
            )
            results.append(
                SageHistoryEntry(
                    id=entry_id,
                    date=_parse_date(date_raw),
                    amount=parsed_amount,
                    nominal_code=nominal_raw,
                    tax_code=tax_code_raw or "T0",
                    description_raw=description_raw,
                    description_clean=clean_description(description_raw),
                    vendor_hint=vendor_hint,
                )
            )
        return results

    def _build_history_entry(self, row: dict[str, str], idx: int) -> SageHistoryEntry:
        date_raw = _resolve_field(row, self.date_headers)
        amount_raw = _resolve_field(row, self.net_amount_headers)
        description_raw = _resolve_field(row, self.details_headers)
        nominal_raw = _resolve_field(row, self.nominal_headers)
        tax_code_raw = _resolve_field(row, self.tax_code_headers)
        reference_raw = row.get(self.reference_headers[0], str(idx))
        clean = clean_description(description_raw)
        vendor_hint = self._derive_vendor_hint(clean)
        entry_id = _deterministic_id(
            date_raw, amount_raw, description_raw, nominal_raw, reference_raw
        )
        return SageHistoryEntry(
            id=entry_id,
            date=_parse_date(date_raw),
            amount=_parse_amount(amount_raw),
            nominal_code=nominal_raw,
            tax_code=tax_code_raw,
            description_raw=description_raw,
            description_clean=clean,
            vendor_hint=vendor_hint,
        )

    @staticmethod
    def _derive_vendor_hint(cleaned_description: str) -> str | None:
        if not cleaned_description:
            return None
        tokens = cleaned_description.split()
        if not tokens:
            return None
        return " ".join(tokens[:3])


def _infer_audit_sign(tx_type: str) -> float:
    tx_type = tx_type.upper()
    if tx_type in {"BP", "JD"}:
        return -1.0
    return 1.0


__all__ = ["BankCsvParser", "SageHistoryParser", "clean_description"]
