"""Vendor matching and confidence scoring."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Sequence

from accountantiq_schemas import BankTxn, Direction, SageHistoryEntry, Suggestion
from rapidfuzz import fuzz, process

from .parsers import clean_description

_MIN_FUZZY_SCORE = 60
_ALIAS_SCORE_WEIGHT = 0.6
_DIRECTION_BONUS = 0.2
_AMOUNT_BONUS = 0.1


@dataclass(slots=True)
class VendorProfile:
    """Aggregated signals for a single vendor."""

    vendor_key: str
    aliases: set[str] = field(default_factory=set)
    nominal_counts: Counter[str] = field(default_factory=Counter)
    tax_counts: Counter[str] = field(default_factory=Counter)
    direction_counts: Counter[Direction] = field(default_factory=Counter)
    amounts: list[float] = field(default_factory=list)

    def register_entry(self, entry: SageHistoryEntry) -> None:
        self.nominal_counts[entry.nominal_code] += 1
        self.tax_counts[entry.tax_code] += 1
        direction: Direction = "debit" if entry.amount < 0 else "credit"
        self.direction_counts[direction] += 1
        self.amounts.append(abs(entry.amount))

    def dominant_nominal(self) -> str | None:
        if not self.nominal_counts:
            return None
        return self.nominal_counts.most_common(1)[0][0]

    def dominant_tax_code(self) -> str | None:
        if not self.tax_counts:
            return None
        return self.tax_counts.most_common(1)[0][0]

    def dominant_direction(self) -> Direction | None:
        if not self.direction_counts:
            return None
        return self.direction_counts.most_common(1)[0][0]

    def amount_summary(self) -> float | None:
        if not self.amounts:
            return None
        return median(self.amounts)


def _generate_aliases(seed: str) -> set[str]:
    tokens = [token for token in seed.split() if token]
    variants = {seed}
    if len(tokens) >= 2:
        variants.add(" ".join(tokens[:2]))
    if len(tokens) >= 3:
        variants.add(" ".join(tokens[:3]))
    return {variant for variant in variants if variant}


class VendorMatcher:
    """Provide suggestions for bank transactions using vendor history."""

    def __init__(self, history: Sequence[SageHistoryEntry]) -> None:
        self._profiles = self._build_profiles(history)
        self._alias_lookup: dict[str, VendorProfile] = {}
        for profile in self._profiles.values():
            for alias in profile.aliases:
                self._alias_lookup[alias] = profile
        self._aliases: tuple[str, ...] = tuple(self._alias_lookup.keys())

    def suggest(self, txn: BankTxn) -> Suggestion:
        if not self._aliases:
            return Suggestion(
                txn_id=txn.id,
                confidence=0.0,
                explanations=["No vendor history available"],
            )

        cleaned_description = txn.description_clean or clean_description(
            txn.description_raw
        )
        match_alias = (
            cleaned_description if cleaned_description in self._alias_lookup else None
        )
        match_score = 100 if match_alias else 0

        if not match_alias:
            result = process.extractOne(
                cleaned_description,
                self._aliases,
                scorer=fuzz.token_set_ratio,
            )
            if result is not None:
                match_alias = result[0]
                match_score = int(result[1] or 0)

        if match_alias is None or match_score < _MIN_FUZZY_SCORE:
            return Suggestion(
                txn_id=txn.id,
                confidence=0.0,
                explanations=["No high-confidence vendor match found"],
            )

        profile = self._alias_lookup[match_alias]
        explanations: list[str] = []
        confidence = min(_ALIAS_SCORE_WEIGHT, (match_score / 100) * _ALIAS_SCORE_WEIGHT)

        if match_score == 100:
            explanations.append(f"Exact vendor alias match '{profile.vendor_key}'")
        else:
            explanations.append(
                f"Fuzzy vendor match '{profile.vendor_key}' with score {match_score}"
            )

        if profile.dominant_nominal() is None or profile.dominant_tax_code() is None:
            explanations.append("Vendor profile lacks sufficient coding history")

        dominant_direction = profile.dominant_direction()
        if dominant_direction is not None:
            if txn.direction == dominant_direction:
                confidence += _DIRECTION_BONUS
                explanations.append(
                    "Transaction direction matches historical "
                    f"{dominant_direction} postings"
                )
            else:
                explanations.append(
                    "Direction mismatch between transaction direction "
                    f"{txn.direction} and history {dominant_direction}"
                )

        amount_median = profile.amount_summary()
        if amount_median is not None:
            tolerance = max(1.0, amount_median * 0.15)
            delta = abs(abs(txn.amount) - amount_median)
            if delta <= tolerance:
                confidence += _AMOUNT_BONUS
                explanations.append(
                    "Amount within tolerance of historical median "
                    f"{amount_median:.2f} (|delta|={delta:.2f}, tol={tolerance:.2f})"
                )
            else:
                explanations.append(
                    "Amount differs from historical median "
                    f"{amount_median:.2f} by {delta:.2f} (tol {tolerance:.2f})"
                )

        confidence = min(confidence, 0.99)

        return Suggestion(
            txn_id=txn.id,
            nominal_suggested=profile.dominant_nominal(),
            tax_code_suggested=profile.dominant_tax_code(),
            confidence=round(confidence, 2),
            explanations=explanations,
        )

    def suggest_many(self, transactions: Sequence[BankTxn]) -> list[Suggestion]:
        return [self.suggest(txn) for txn in transactions]

    @staticmethod
    def _build_profiles(
        history: Sequence[SageHistoryEntry],
    ) -> dict[str, VendorProfile]:
        profiles: dict[str, VendorProfile] = {}
        for entry in history:
            base = entry.vendor_hint or entry.description_clean
            cleaned = clean_description(base)
            if not cleaned:
                continue
            profile = profiles.get(cleaned)
            if profile is None:
                profile = VendorProfile(vendor_key=cleaned)
                profiles[cleaned] = profile
            profile.aliases.update(_generate_aliases(cleaned))
            profile.aliases.add(entry.description_clean)
            if entry.vendor_hint:
                profile.aliases.update(_generate_aliases(entry.vendor_hint))
            profile.register_entry(entry)
        return profiles


def suggest_for_transactions(
    transactions: Sequence[BankTxn], history: Sequence[SageHistoryEntry]
) -> list[Suggestion]:
    """Convenience helper for batch suggestion generation."""
    matcher = VendorMatcher(history)
    return matcher.suggest_many(transactions)


__all__ = ["VendorMatcher", "suggest_for_transactions"]
