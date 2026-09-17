"""A small terminal guide with review, section editing, and save-for-later support."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from template_creator.config import (
    LICENSES,
    MAX_PREFIX_LENGTH,
    MAX_SLUG_LENGTH,
    Config,
    load_editable,
    owners,
    save,
    validate,
    validate_prefix,
    validate_slug,
)
from template_creator.generate import generate
from template_creator.snapshot import SOURCE_URL, Snapshot

SECTIONS = (
    "Project and naming",
    "GitHub and documentation",
    "Author",
    "Security contact",
    "Ownership",
    "License",
)


def ask(label: str, default: str = "") -> str:
    """Keep defaults visible and never silently accept empty required answers."""
    while True:
        value = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip()
        if value or default:
            return value or default
        print("Please enter a value.")


def ask_yes_no(label: str, *, default: bool) -> bool:
    """Accept common abbreviations without silently treating typos as no."""
    while True:
        value = ask(f"{label} yes/no", "yes" if default else "no").lower()
        if value in {"yes", "y", "no", "n"}:
            return value in {"yes", "y"}
        print("Please answer yes/y or no/n.")


def ask_owners(label: str, previous: list[str]) -> list[str]:
    """Replace the complete owner list and reject invalid syntax immediately."""
    while True:
        value = ask(label, " ".join(previous)).split()
        try:
            owners(value, label)
        except ValueError as error:
            print(error)
        else:
            return value


def summary(config: Config) -> str:
    data = config.data
    return "\n".join(
        (
            f"Project: {data['project']['name']} ({data['project']['version']})",
            f"Repository: {config.repository_url}",
            f"Documentation: {data['github']['docs_url']}",
            f"Python: {config.distribution_prefix}-core / {config.prefix}_core",
            f"C/CMake: {config.prefix}::core / {config.cmake_package}Core",
            f"Executable: {config.distribution_prefix}-package-a-cli",
            f"Author: {data['author']['name']} <{data['author']['email']}>",
            f"Security contact: {data['security']['contact']}",
            f"Ownership: {data['ownership']}",
            f"License: {data['license']['choice']}; "
            f"{data['license']['year']} {data['license']['holder']}",
            f"Template: {data['template']['version']} ({data['template']['digest'][:12]})",
        )
    )


def default_docs_url(owner: str, slug: str) -> str:
    return f"https://{owner}.github.io/{slug}/"


def section(number: int, data: dict[str, Any]) -> None:
    """Edit one section while retaining previous answers as defaults."""
    if number == 1:
        old = data.get("project", {})
        name = ask("Project display name", old.get("name", ""))
        print("The repository slug is the name in OWNER/REPOSITORY, for example acme-tools.")
        while True:
            slug = ask(
                f"Repository slug (maximum {MAX_SLUG_LENGTH} characters)",
                old.get("slug", re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")),
            )
            try:
                validate_slug(slug)
            except ValueError as error:
                print(error)
            else:
                break
        description = ask("One-line description", old.get("description", ""))
        while True:
            prefix = ask(
                f"Shared Python/C namespace prefix (maximum {MAX_PREFIX_LENGTH} characters)",
                old.get("prefix", slug.replace("-", "_")),
            )
            try:
                validate_prefix(prefix)
            except ValueError as error:
                print(error)
            else:
                break
        data["project"] = {
            "name": name,
            "slug": slug,
            "description": description,
            "prefix": prefix,
            "version": ask("Initial component version", old.get("version", "0.1.0")),
        }
        if "github" in data:
            github = data["github"]
            if github["docs_url"] == default_docs_url(github["owner"], github["repository"]):
                github["docs_url"] = default_docs_url(github["owner"], slug)
            data["github"]["repository"] = slug
    elif number == 2:
        old = data.get("github", {})
        owner = ask("GitHub repository owner (user or organization)", old.get("owner", ""))
        slug = data["project"]["slug"]
        docs_url = old.get("docs_url", default_docs_url(owner, slug))
        if old and docs_url == default_docs_url(old["owner"], old["repository"]):
            docs_url = default_docs_url(owner, slug)
        data["github"] = {
            "owner": owner,
            "repository": slug,
            "docs_url": ask("Documentation URL", docs_url),
        }
    elif number == 3:
        old = data.get("author", {})
        data["author"] = {
            "name": ask("Author name", old.get("name", "")),
            "email": ask("Public author email", old.get("email", "")),
        }
    elif number == 4:
        data["security"] = {
            "contact": ask(
                "Private vulnerability reporting email or HTTPS URL",
                data.get("security", {}).get("contact", data["author"]["email"]),
            )
        }
    elif number == 5:
        old = data.get("ownership", {})
        print(
            "Enter the complete owner list to replace it; omit any owners you want to remove.\n"
            "Enter keeps the displayed list. At least one default owner is required."
        )
        default = ask_owners(
            "Default CODEOWNERS (@user, @org/team, or email; separate with spaces)",
            old.get("default", []),
        )
        rules = []
        for index, rule in enumerate(old.get("rules", []), start=1):
            print(f"Rule {index}: {rule['pattern']} {' '.join(rule['owners'])}")
            while (action := ask("Keep, edit, or remove this rule?", "keep").lower()) not in {
                "keep",
                "edit",
                "remove",
            }:
                print("Choose keep, edit, or remove.")
            if action == "keep":
                rules.append(rule)
            elif action == "edit":
                rules.append(
                    {
                        "pattern": ask("CODEOWNERS path pattern", rule["pattern"]),
                        "owners": ask_owners("Owners (separate with spaces)", rule["owners"]),
                    }
                )
        while ask_yes_no("Add a path-specific ownership rule?", default=False):
            rules.append(
                {
                    "pattern": ask("CODEOWNERS path pattern"),
                    "owners": ask_owners("Owners (separate with spaces)", []),
                }
            )
        data["ownership"] = {"default": default, "rules": rules}
    elif number == 6:
        old = data.get("license", {})
        print("License choices: " + ", ".join(LICENSES))
        while (choice := ask("License", old.get("choice", ""))) not in LICENSES:
            print("Choose one of the listed names exactly.")
        year = ask("Copyright year", str(old.get("year", date.today().year)))
        while not re.fullmatch(r"[0-9]{4}", year) or not 1000 <= int(year) <= 9999:
            year = ask("Enter a four-digit copyright year")
        content = ""
        if choice == "Custom":
            content = old.get("text", "")
            if content and ask_yes_no("Replace the existing custom license text?", default=False):
                content = ""
            while not content:
                try:
                    replacement = (
                        Path(ask("UTF-8 license file")).expanduser().read_text(encoding="utf-8")
                    )
                    if not replacement.strip():
                        raise ValueError("license file is empty")
                    if "\x00" in replacement:
                        raise ValueError("license file contains NUL characters")
                    content = replacement
                except (OSError, ValueError) as error:
                    print(error)
        data["license"] = {
            "choice": choice,
            "holder": ask("Copyright holder", old.get("holder", data["author"]["name"])),
            "year": int(year),
            "text": content,
        }


def require_new_config(path: Path, option: str = "--config") -> None:
    if os.path.lexists(path):
        raise ValueError(f"config already exists: {path}; choose another {option} path")
    if not path.parent.is_dir():
        raise ValueError(f"config parent does not exist: {path.parent}")


def review(snapshot: Snapshot, data: dict[str, Any], path: Path) -> None:
    """Share section editing and full validation between new and existing recipes."""
    while True:
        print("\n".join(f"{number}. {label}" for number, label in enumerate(SECTIONS, start=1)))
        try:
            config = validate(data, snapshot)
        except ValueError as error:
            print(f"Please correct the configuration: {error}")
            choice = ask("Section to edit (1-6)")
        else:
            print("\nReview\n" + summary(config))
            choice = ask("Save or edit a section (1-6)?", "save").lower()
            if choice == "save":
                save(config, path)
                break
        if choice not in {"1", "2", "3", "4", "5", "6"}:
            choice = ask("Section to edit (1-6)")
        if choice in {"1", "2", "3", "4", "5", "6"}:
            section(int(choice), data)
    print(f"Saved {path}")


def edit(snapshot: Snapshot, source: Path, output: Path) -> None:
    """Edit a compatible saved recipe into a new file without generating a project."""
    require_new_config(output, "--output")
    data = load_editable(source, snapshot)
    review(snapshot, data, output)


def wizard(snapshot: Snapshot, path: Path) -> None:
    """Save first, then reload the exact persisted recipe for generation."""
    from template_creator.config import load

    require_new_config(path)
    print(
        "Create a Python/C repository in six steps. Names, emails, ownership, and license\n"
        "will be written to public project files. Do not enter passwords or tokens.\n"
        "Creation needs uv >=0.10.9; it may download Python, metadata, and formatters.\n"
        "Ctrl+C cancels. Nothing is generated until the configuration is saved.\n"
    )
    data: dict[str, Any] = {
        "schema_version": 1,
        "template": {"version": snapshot.version, "digest": snapshot.digest, "source": SOURCE_URL},
    }
    for number, label in enumerate(SECTIONS, start=1):
        print(f"\nStep {number}/{len(SECTIONS)}: {label}")
        section(number, data)
    review(snapshot, data, path)
    if ask_yes_no("Create repository now?", default=True):
        destination = Path(ask("New destination directory", f"./{data['project']['slug']}"))
        generate(snapshot, load(path, snapshot), destination)
