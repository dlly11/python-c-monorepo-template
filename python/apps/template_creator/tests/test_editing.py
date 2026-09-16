"""Recipe editing, derived defaults, and safe template transformations."""

from pathlib import Path
from typing import Any

import pytest
import tomlkit

from template_creator import cli
from template_creator.config import Config, load, owners, save
from template_creator.render import without_creator
from template_creator.snapshot import Snapshot
from template_creator.wizard import edit, section


@pytest.mark.parametrize("owner", ["@ada", "@ada_acme", "@acme/native-team", "ada@example.com"])
def test_supported_owners(owner: str) -> None:
    owners([owner], "owners")


@pytest.mark.parametrize(
    "owner",
    [
        "#security@example.com",
        "ada#note@example.com",
        "ada\\name@example.com",
        '"ada"@example.com',
        "@ada\x7f",
        "@ada\n",
        "@org/.",
        "@org/-",
        "@ada user",
    ],
)
def test_unrepresentable_owners(owner: str) -> None:
    with pytest.raises(ValueError, match="invalid owner"):
        owners([owner], "owners")


@pytest.mark.parametrize("custom", [False, True])
def test_derived_urls_follow_edits(
    recipe: dict[str, Any], monkeypatch: pytest.MonkeyPatch, custom: bool
) -> None:
    original = "https://custom.invalid/docs/" if custom else "https://acme.github.io/acme-project/"
    recipe["github"]["docs_url"] = original
    answers = iter(["", "new-project", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    section(1, recipe)
    assert recipe["github"]["repository"] == "new-project"
    assert recipe["github"]["docs_url"] == (
        original if custom else "https://acme.github.io/new-project/"
    )
    answers = iter(["new-owner", "", "last-owner", ""])
    section(2, recipe)
    section(2, recipe)
    assert recipe["github"]["docs_url"] == (
        original if custom else "https://last-owner.github.io/new-project/"
    )


@pytest.mark.parametrize(
    "style", ["# {} TEMPLATE CREATOR ONLY", "<!-- {} TEMPLATE CREATOR ONLY -->"]
)
def test_marker_removal_preserves_other_content(style: str) -> None:
    text = "before\n  " + style.format("BEGIN") + "\nprivate\n" + style.format("END")
    assert without_creator(text, "README.md") == "before\n"
    assert without_creator(text + "\nafter\n", "README.md") == "before\nafter\n"


@pytest.mark.parametrize(
    "markers",
    [
        ["<!-- BEGIN TEMPLATE CREATOR ONLY -->"],
        ["<!-- END TEMPLATE CREATOR ONLY -->"],
        ["# END TEMPLATE CREATOR ONLY", "# BEGIN TEMPLATE CREATOR ONLY"],
        ["# BEGIN TEMPLATE CREATOR ONLY", "<!-- END TEMPLATE CREATOR ONLY -->"],
        [
            "# BEGIN TEMPLATE CREATOR ONLY",
            "# BEGIN TEMPLATE CREATOR ONLY",
            "# END TEMPLATE CREATOR ONLY",
            "# END TEMPLATE CREATOR ONLY",
        ],
    ],
)
def test_bad_markers_name_source(markers: list[str]) -> None:
    with pytest.raises(ValueError, match=r"README\.md.*anchors"):
        without_creator("\n".join(markers), "README.md")


def test_edit_repairs_values_without_changing_source(
    tmp_path: Path, recipe: dict[str, Any], snapshot: Snapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe["author"]["email"] = "not-an-email"
    recipe["license"].update(choice="Custom", text="My embedded license.\n")
    source, output = tmp_path / "source.toml", tmp_path / "revised.toml"
    source.write_text(tomlkit.dumps(recipe), encoding="utf-8")
    original = source.read_bytes()
    answers = iter(["3", "", "new@example.com", "save"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    edit(snapshot, source, output)
    revised = load(output, snapshot).data
    assert revised["author"]["email"] == "new@example.com"
    assert revised["license"] == recipe["license"]
    assert revised["ownership"] == recipe["ownership"]
    assert source.read_bytes() == original


@pytest.mark.parametrize("change", ["schema", "identity", "field", "type", "toml"])
def test_incompatible_edit_fails_before_prompt(
    tmp_path: Path,
    recipe: dict[str, Any],
    snapshot: Snapshot,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    if change == "schema":
        recipe["schema_version"] = 2
    elif change == "identity":
        recipe["template"]["digest"] = "wrong"
    elif change == "field":
        recipe["unexpected"] = "value"
    elif change == "type":
        recipe["ownership"]["rules"] = ["wrong"]
    source, output = tmp_path / "source.toml", tmp_path / "revised.toml"
    source.write_text("[" if change == "toml" else tomlkit.dumps(recipe), encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("unexpected prompt"))
    with pytest.raises(ValueError):
        edit(snapshot, source, output)
    assert not output.exists()


def test_edit_cli_saves_only_and_preserves_existing_files(
    tmp_path: Path, config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, output = tmp_path / "source.toml", tmp_path / "revised.toml"
    save(config, source)
    original = source.read_bytes()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "save")
    monkeypatch.setattr(cli, "generate", lambda *_: pytest.fail("unexpected generation"))
    arguments = ["edit", "--config", str(source), "--output", str(output)]
    assert cli.main(arguments) == 0
    saved = output.read_bytes()
    assert cli.main(arguments) == 1
    assert cli.main(["edit", "--config", str(source), "--output", str(source)]) == 1
    assert source.read_bytes() == original
    assert output.read_bytes() == saved


def test_edit_cancel_and_noninteractive(
    tmp_path: Path, config: Config, snapshot: Snapshot, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, output = tmp_path / "source.toml", tmp_path / "revised.toml"
    save(config, source)
    arguments = ["edit", "--config", str(source), "--output", str(output)]
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(_: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", cancel)
    assert cli.main(arguments) == 130
    assert not output.exists()
    assert load(source, snapshot) == config
