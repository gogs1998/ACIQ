"""Audit profile helpers."""

from __future__ import annotations

from pathlib import Path

import yaml
from accountantiq_schemas import ProfileColumn, ProfileDefinition

from .workspace import profiles_path

_DEFAULT_PROFILE = ProfileDefinition(
    name="default",
    columns=[
        ProfileColumn(field="transaction_id", header="Reference"),
        ProfileColumn(field="date", header="Date"),
        ProfileColumn(field="description", header="Details"),
        ProfileColumn(field="nominal_code", header="Nominal Code"),
        ProfileColumn(field="tax_code", header="Tax Code"),
        ProfileColumn(field="net_amount", header="Net Amount"),
    ],
)


def profile_path(client_slug: str, name: str) -> Path:
    return profiles_path(client_slug) / f"{name}.yaml"


def load_profile(client_slug: str, name: str = "default") -> ProfileDefinition:
    path = profile_path(client_slug, name)
    if not path.exists():
        save_profile(client_slug, _DEFAULT_PROFILE)
        return _DEFAULT_PROFILE
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ProfileDefinition.model_validate(raw)


def save_profile(client_slug: str, profile: ProfileDefinition) -> None:
    path = profile_path(client_slug, profile.name)
    payload = profile.model_dump()
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def list_profiles(client_slug: str) -> list[ProfileDefinition]:
    directory = profiles_path(client_slug)
    profiles: list[ProfileDefinition] = []
    for file in directory.glob("*.yaml"):
        raw = yaml.safe_load(file.read_text(encoding="utf-8"))
        profiles.append(ProfileDefinition.model_validate(raw))
    if not profiles:
        profiles.append(load_profile(client_slug))
    return profiles
