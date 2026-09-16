"""Representative portable creator configurations."""

from copy import deepcopy
from typing import Any

import pytest

from template_creator.config import Config, validate
from template_creator.snapshot import SOURCE_URL, Snapshot, load


@pytest.fixture
def snapshot() -> Snapshot:
    return load()


@pytest.fixture
def recipe(snapshot: Snapshot) -> dict[str, Any]:
    return deepcopy(
        {
            "schema_version": 1,
            "project": {
                "name": 'Acme "Research"',
                "slug": "acme-project",
                "description": "Tools for café research.",
                "prefix": "acme_lab",
                "version": "0.2.0",
            },
            "github": {
                "owner": "acme",
                "repository": "acme-project",
                "docs_url": "https://docs.acme.invalid/",
            },
            "author": {"name": "Ada O'Connor", "email": "ada@acme.invalid"},
            "security": {"contact": "https://acme.invalid/security"},
            "ownership": {
                "default": ["@ada", "@acme/maintainers"],
                "rules": [{"pattern": "/native/", "owners": ["@acme/native"]}],
            },
            "license": {"choice": "MIT", "holder": "Acme Research", "year": 2026, "text": ""},
            "template": {
                "version": snapshot.version,
                "digest": snapshot.digest,
                "source": SOURCE_URL,
            },
        }
    )


@pytest.fixture
def config(recipe: dict[str, Any], snapshot: Snapshot) -> Config:
    return validate(recipe, snapshot)
