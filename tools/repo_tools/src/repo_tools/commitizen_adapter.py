"""Optional Commitizen authoring adapter; ordinary maintenance commands do not import it."""

from collections.abc import Mapping
from typing import Any

from commitizen.cz.base import BaseCommitizen, ValidationResult
from commitizen.exceptions import CustomError
from commitizen.question import Choice, CzQuestion

from repo_tools.context import resolve_root
from repo_tools.conventional_commits import SUBJECT_PATTERN, TYPES, scope_policy, subject_errors


class RepositoryCz(BaseCommitizen):
    """Use exactly the same types and scopes as commit hooks and GitHub validation."""

    def scopes(self) -> dict[str, str]:
        return scope_policy(resolve_root(None)) or {}

    def questions(self) -> list[CzQuestion]:
        scopes = self.scopes()
        choices: list[Choice] = [{"name": "No scope", "value": ""}]
        choices.extend(
            {"name": f"{name} ({path})", "value": name} for name, path in sorted(scopes.items())
        )
        return [
            {
                "type": "list",
                "name": "type",
                "message": "Change type",
                "choices": [{"name": name, "value": name} for name in TYPES],
            },
            {
                "type": "list",
                "name": "scope",
                "message": "Scope (does not select releases)",
                "choices": choices,
            },
            {"type": "input", "name": "description", "message": "Short description"},
            {"type": "input", "name": "body", "message": "Body (optional)"},
            {
                "type": "confirm",
                "name": "breaking",
                "message": "Breaking change?",
                "default": False,
            },
            {
                "type": "input",
                "name": "migration",
                "message": "Breaking change explanation (optional)",
            },
            {"type": "input", "name": "footer", "message": "Other footers (optional)"},
        ]

    def message(self, answers: Mapping[str, Any]) -> str:
        scope = f"({answers['scope']})" if answers.get("scope") else ""
        breaking = "!" if answers.get("breaking") else ""
        subject = f"{answers['type']}{scope}{breaking}: {answers['description'].strip()}"
        errors = subject_errors(subject, self.scopes())
        if errors:
            raise CustomError("; ".join(errors))
        sections = [subject, str(answers.get("body", "")).strip()]
        if answers.get("breaking") and answers.get("migration"):
            sections.append("BREAKING CHANGE: " + str(answers["migration"]).strip())
        sections.append(str(answers.get("footer", "")).strip())
        return "\n\n".join(section for section in sections if section)

    def validate_commit_message(self, *, commit_msg: str, **kwargs: Any) -> ValidationResult:
        errors = subject_errors(commit_msg.partition("\n")[0], self.scopes())
        return ValidationResult(not errors, errors)

    def example(self) -> str:
        return "fix: handle empty input"

    def schema(self) -> str:
        return "type(scope)!: description (scope and ! are optional)"

    def schema_pattern(self) -> str:
        return SUBJECT_PATTERN.pattern

    def info(self) -> str:
        return "Use list-scopes for scopes. Release Please owns version bumps and changelogs."
