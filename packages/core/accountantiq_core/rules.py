"""Rule management utilities."""

from __future__ import annotations

import re
from typing import Iterable

import yaml
from accountantiq_schemas import BankTxn, RuleDefinition

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


def append_rule(client_slug: str, rule: RuleDefinition) -> list[RuleDefinition]:
    rules = load_rules(client_slug)
    rules.append(rule)
    save_rules(client_slug, rules)
    return rules


def match_rule(rules: Iterable[RuleDefinition], txn: BankTxn) -> RuleDefinition | None:
    description = txn.description_clean or txn.description_raw.lower()
    for rule in rules:
        if re.search(rule.pattern, description, flags=re.IGNORECASE):
            return rule
    return None
