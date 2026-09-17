"""Validate and serialize the portable, versioned creation recipe."""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from email.errors import HeaderParseError
from email.headerregistry import Address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomlkit

from template_creator.snapshot import SOURCE_URL, Snapshot

LICENSES = ("MIT", "Apache-2.0", "BSD-3-Clause", "Proprietary", "Custom")
FIELDS = {
    "project": {"name", "slug", "description", "prefix", "version"},
    "github": {"owner", "repository", "docs_url"},
    "author": {"name", "email"},
    "security": {"contact"},
    "ownership": {"default", "rules"},
    "license": {"choice", "holder", "year", "text"},
    "template": {"version", "digest", "source"},
}
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
PREFIX = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
MAX_PREFIX_LENGTH = 32
EMAIL = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+")
OWNER = re.compile(
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:_[A-Za-z0-9]+)?(?:/[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?)?"
)
RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(10)),
    *(f"lpt{i}" for i in range(10)),
}


@dataclass(frozen=True)
class Config:
    """A validated document and derived naming families."""

    data: dict[str, Any]

    @property
    def prefix(self) -> str:
        return self.data["project"]["prefix"]

    @property
    def distribution_prefix(self) -> str:
        return self.prefix.replace("_", "-")

    @property
    def cmake_package(self) -> str:
        return "".join(part.capitalize() for part in self.prefix.split("_"))

    @property
    def repository_url(self) -> str:
        github = self.data["github"]
        return f"https://github.com/{github['owner']}/{github['repository']}"


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field}: expected nonempty single-line text")
    return value


def https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and not parsed.netloc.endswith(":")
        and (port is None or 1 <= port <= 65535)
        and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
        and not any(c.isspace() or c in '<>"\\' for c in value)
    )


def validate_prefix(prefix: str) -> None:
    if (
        len(prefix) > MAX_PREFIX_LENGTH
        or not PREFIX.fullmatch(prefix)
        or keyword.iskeyword(prefix)
        or prefix in RESERVED | {"example", "repo_tools", "template_creator"}
    ):
        raise ValueError(
            f"project.prefix: use a new lowercase identifier of at most {MAX_PREFIX_LENGTH} "
            "characters, optionally separated by underscores"
        )


def owners(value: Any, field: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field}: provide at least one @user, @org/team, or email")
    for owner in value:
        if (
            not isinstance(owner, str)
            or any(ord(c) < 32 or ord(c) == 127 or c.isspace() or c in '#\\"' for c in owner)
            or not (OWNER.fullmatch(owner) or EMAIL.fullmatch(owner))
        ):
            raise ValueError(f"{field}: invalid owner {owner!r}")


def validate_structure(data: dict[str, Any], snapshot: Snapshot) -> None:
    """Require a compatible recipe whose fields can safely be presented for editing."""
    if (
        set(data) != {"schema_version", *FIELDS}
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError(
            "configuration requires schema_version = 1 and exactly the documented sections"
        )
    for section, fields in FIELDS.items():
        values = data[section]
        if not isinstance(values, dict) or set(values) != fields:
            raise ValueError(f"{section}: expected fields {', '.join(sorted(fields))}")
        for key, value in values.items():
            if (section, key) not in {
                ("ownership", "default"),
                ("ownership", "rules"),
                ("license", "year"),
            } and not isinstance(value, str):
                raise ValueError(f"{section}.{key}: expected text")
    ownership = data["ownership"]
    if not isinstance(ownership["default"], list) or any(
        not isinstance(owner, str) for owner in ownership["default"]
    ):
        raise ValueError("ownership.default: expected a list of owner strings")
    if not isinstance(ownership["rules"], list):
        raise ValueError("ownership.rules: expected a list")
    for rule in ownership["rules"]:
        if (
            not isinstance(rule, dict)
            or set(rule) != {"pattern", "owners"}
            or not isinstance(rule["pattern"], str)
            or not isinstance(rule["owners"], list)
            or any(not isinstance(owner, str) for owner in rule["owners"])
        ):
            raise ValueError("ownership.rules: each rule requires a pattern and owner strings")
    if type(data["license"]["year"]) is not int:
        raise ValueError("license.year: expected an integer")
    if data["template"] != {
        "version": snapshot.version,
        "digest": snapshot.digest,
        "source": SOURCE_URL,
    }:
        raise ValueError(
            "template identity mismatch: use the original creator download, "
            "or create a new config with this release"
        )


def validate(data: dict[str, Any], snapshot: Snapshot) -> Config:
    """Reject omissions and typos before any output is created."""
    validate_structure(data, snapshot)
    for section, fields in FIELDS.items():
        for key in fields:
            if (section, key) not in {
                ("ownership", "default"),
                ("ownership", "rules"),
                ("license", "year"),
                ("license", "text"),
            }:
                text(data[section][key], f"{section}.{key}")
    project = data["project"]
    if not SLUG.fullmatch(project["slug"]) or project["slug"] in RESERVED:
        raise ValueError(
            "project.slug: use lowercase hyphen-separated words, starting with a letter"
        )
    prefix = project["prefix"]
    validate_prefix(prefix)
    if project["slug"] in {
        f"{prefix.replace('_', '-')}-{suffix}"
        for suffix in ("core", "package-a", "package-b", "package-a-cli")
    } | {"monorepo-repo-tools", "monorepo-template-creator"}:
        raise ValueError("project.slug collides with a package name")
    if not VERSION.fullmatch(project["version"]):
        raise ValueError("project.version: expected numeric X.Y.Z")
    github = data["github"]
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", github["owner"]):
        raise ValueError("github.owner: invalid GitHub owner")
    if github["repository"] != project["slug"]:
        raise ValueError("github.repository must equal project.slug")
    if not https_url(github["docs_url"]):
        raise ValueError(
            "github.docs_url: expected an HTTPS URL without credentials, query, or fragment"
        )
    if not EMAIL.fullmatch(data["author"]["email"]):
        raise ValueError("author.email: invalid email address")
    try:
        # Setuptools serializes author mailboxes with the same parser. Catch errors
        # here so a saved recipe cannot defer this failure until package building.
        Address(addr_spec=data["author"]["email"])
    except (ValueError, HeaderParseError) as error:
        raise ValueError(
            "author.email: expected a valid package-author email address; "
            "use your public email or personal GitHub noreply address"
        ) from error
    contact = data["security"]["contact"]
    if not (EMAIL.fullmatch(contact) or https_url(contact)):
        raise ValueError("security.contact: expected an email address or HTTPS URL")
    owners(data["ownership"]["default"], "ownership.default")
    rules = data["ownership"]["rules"]
    for rule in rules:
        pattern = text(rule["pattern"], "ownership.rules.pattern")
        if any(c.isspace() or c in "#![]\\" for c in pattern):
            raise ValueError(
                "ownership.rules.pattern: use a CODEOWNERS glob without spaces, negation, or ranges"
            )
        owners(rule["owners"], "ownership.rules.owners")
    license = data["license"]
    if license["choice"] not in LICENSES or not 1000 <= license["year"] <= 9999:
        raise ValueError("license: choose a supported license and four-digit copyright year")
    if "\x00" in license["text"]:
        raise ValueError("license.text: expected text without NUL characters")
    if (license["choice"] == "Custom") != bool(license["text"].strip()):
        raise ValueError("license.text must be provided only for Custom licensing")
    return Config(data)


def load(path: Path, snapshot: Snapshot) -> Config:
    return validate(load_editable(path, snapshot), snapshot)


def load_editable(path: Path, snapshot: Snapshot) -> dict[str, Any]:
    data = tomlkit.parse(path.read_text(encoding="utf-8")).unwrap()
    validate_structure(data, snapshot)
    return data


def serialize(config: Config) -> str:
    return (
        "# Repository creation recipe; contains public project identity, never credentials.\n"
        + tomlkit.dumps(config.data)
    )


def save(config: Config, path: Path) -> None:
    """Never overwrite an existing recipe."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialize(config))
