"""Helpers for managing client workspace paths."""

from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path("data/clients")


def client_root(client_slug: str) -> Path:
    root = DATA_ROOT / client_slug
    root.mkdir(parents=True, exist_ok=True)
    return root


def inputs_path(client_slug: str) -> Path:
    path = client_root(client_slug) / "inputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def workspace_path(client_slug: str) -> Path:
    path = client_root(client_slug) / "workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_path(client_slug: str) -> Path:
    path = client_root(client_slug) / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def rules_path(client_slug: str) -> Path:
    path = workspace_path(client_slug) / "rules"
    path.mkdir(parents=True, exist_ok=True)
    return path / "rules.yaml"


def profiles_path(client_slug: str) -> Path:
    path = workspace_path(client_slug) / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def review_db_path(client_slug: str) -> Path:
    return workspace_path(client_slug) / "review.db"
