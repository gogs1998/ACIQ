"""Rule management utilities."""

from __future__ import annotations

import re
from typing import Iterable

import yaml
from accountantiq_schemas import BankTxn, RuleDefinition

from .parsers import clean_description
from .workspace import rules_path


def load_rules(client_slug: str) -> list[RuleDefinition]:
    path = rules_path(client_slug)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        return []
    return [RuleDefinition.model_validate(item) for item in raw]


def save_rules(client_slug: str, rules: Iterable[RuleDefinition]) -> None:
    path = rules_path(client_slug)
    serialisable = [rule.model_dump() for rule in rules]
    path.write_text(yaml.safe_dump(serialisable, sort_keys=False), encoding="utf-8")


def _rule_exists(existing: Iterable[RuleDefinition], candidate: RuleDefinition) -> bool:
    for rule in existing:
        if (
            rule.pattern == candidate.pattern
            and rule.nominal == candidate.nominal
            and rule.tax_code == candidate.tax_code
        ):
            return True
    return False


def add_rule(client_slug: str, rule: RuleDefinition) -> bool:
    rules = load_rules(client_slug)
    if _rule_exists(rules, rule):
        return False
    rules.append(rule)
    save_rules(client_slug, rules)
    return True


def append_rule(client_slug: str, rule: RuleDefinition) -> list[RuleDefinition]:
    add_rule(client_slug, rule)
    return load_rules(client_slug)


def match_rule(rules: Iterable[RuleDefinition], txn: BankTxn) -> RuleDefinition | None:
    description = txn.description_clean or txn.description_raw.lower()
    for rule in rules:
        if re.search(rule.pattern, description, flags=re.IGNORECASE):
            return rule
    return None


def create_rule_from_transaction(
    txn: BankTxn, nominal: str, tax_code: str | None = None
) -> RuleDefinition | None:
    description = txn.description_clean or clean_description(txn.description_raw)
    tokens = [token for token in description.split() if token]
    if not tokens:
        fallback = txn.description_raw.strip() or txn.account_id.strip()
        if not fallback:
            return None
        tokens = [fallback.lower()]
    selected = tokens[:3]
    pattern = "(?i)" + ".*".join(re.escape(token) for token in selected)
    name_source = txn.description_raw.strip() or txn.description_clean or txn.id
    name = name_source[:32] or txn.id[:8]
    return RuleDefinition(
        name=name,
        pattern=pattern,
        nominal=nominal,
        tax_code=tax_code or "T0",
    )
