"""Creator input boundaries, destination previews, and generated setup contracts."""

from pathlib import Path
from typing import Any

import pytest

from template_creator import cli, generate
from template_creator.config import Config, load, save, validate
from template_creator.render import render
from template_creator.snapshot import Snapshot
from template_creator.wizard import edit, section


@pytest.mark.parametrize("length", [31, 32, 33])
def test_prefix_boundary(recipe: dict[str, Any], snapshot: Snapshot, length: int) -> None:
    recipe["project"]["prefix"] = "a" * length
    if length > 32:
        with pytest.raises(ValueError, match=r"project\.prefix.*at most 32"):
            validate(recipe, snapshot)
    else:
        assert validate(recipe, snapshot).prefix == "a" * length


@pytest.mark.parametrize("field", ["docs_url", "contact"])
@pytest.mark.parametrize("port", ["abc", "", "0", "-1", "65536", "99999"])
def test_invalid_https_ports(
    recipe: dict[str, Any], snapshot: Snapshot, field: str, port: str
) -> None:
    group = "github" if field == "docs_url" else "security"
    recipe[group][field] = f"https://docs.example.com:{port}/"
    with pytest.raises(ValueError, match=rf"{group}\.{field}"):
        validate(recipe, snapshot)


@pytest.mark.parametrize(
    "url",
    ["https://docs.example.com/", "https://docs.example.com:1/", "https://[::1]:65535/"],
)
def test_valid_https_ports(recipe: dict[str, Any], snapshot: Snapshot, url: str) -> None:
    recipe["github"]["docs_url"] = recipe["security"]["contact"] = url
    validate(recipe, snapshot)


def test_malformed_https_address_is_field_error(recipe: dict[str, Any], snapshot: Snapshot) -> None:
    recipe["github"]["docs_url"] = "https://[broken/"
    with pytest.raises(ValueError, match=r"github\.docs_url"):
        validate(recipe, snapshot)


@pytest.mark.parametrize("year", ["²", "٢٠٢٦", "999", "0000", "10000", "year"])
def test_year_reprompts_without_losing_answers(
    recipe: dict[str, Any], monkeypatch: pytest.MonkeyPatch, year: str
) -> None:
    answers = iter(["MIT", year, "2027", "Updated holder"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    section(6, recipe)
    assert recipe["license"]["year"] == 2027
    assert recipe["license"]["holder"] == "Updated holder"


def test_prefix_reprompts_at_field(recipe: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["", "", "New description", "a" * 33, "class", "a" * 32, ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    section(1, recipe)
    assert recipe["project"]["prefix"] == "a" * 32
    assert recipe["project"]["description"] == "New description"


def test_edit_overlong_prefix_shows_menu_and_repairs_recipe(
    tmp_path: Path,
    recipe: dict[str, Any],
    snapshot: Snapshot,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipe["project"]["prefix"] = "a" * 33
    source, output = tmp_path / "input.toml", tmp_path / "output.toml"
    save(Config(recipe), source)
    original = source.read_bytes()
    answers = iter(["1", "", "", "", "acme", "", "save"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    edit(snapshot, source, output)
    assert source.read_bytes() == original
    assert load(output, snapshot).prefix == "acme"
    display = capsys.readouterr().out
    for label in (
        "1. Project and naming",
        "2. GitHub and documentation",
        "3. Author",
        "4. Security contact",
        "5. Ownership",
        "6. License",
    ):
        assert display.count(label) == 2


@pytest.mark.parametrize("command, option", [("wizard", "--config"), ("edit", "--output")])
def test_recipe_collision_names_destination_option(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    option: str,
) -> None:
    existing = tmp_path / "existing.toml"
    existing.write_text("keep")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    arguments = [command, "--config", str(existing)]
    if command == "edit":
        arguments.extend(["--output", str(existing)])
    assert cli.main(arguments) == 1
    assert f"choose another {option} path" in capsys.readouterr().err
    assert existing.read_text() == "keep"


@pytest.mark.parametrize(
    "kind", ["file", "directory", "symlink", "dangling", "parent-file", "missing"]
)
@pytest.mark.parametrize("preview", [False, True])
def test_destination_preflight_never_probes_or_changes_files(
    tmp_path: Path, config: Config, monkeypatch: pytest.MonkeyPatch, kind: str, preview: bool
) -> None:
    recipe = tmp_path / "recipe.toml"
    save(config, recipe)
    marker = tmp_path / "keep"
    marker.write_text("original")
    destination = tmp_path / "output"
    if kind == "file":
        destination.write_text("original")
    elif kind == "directory":
        destination.mkdir()
    elif kind in {"symlink", "dangling"}:
        try:
            destination.symlink_to(marker if kind == "symlink" else tmp_path / "absent")
        except OSError:
            pytest.skip("creating symlinks requires platform permission")
    elif kind == "parent-file":
        destination = marker / "output"
    else:
        destination = tmp_path / "absent" / "output"
    before = set(tmp_path.iterdir())
    monkeypatch.setattr(generate, "require_uv", lambda: pytest.fail("unexpected uv probe"))
    arguments = ["generate", "--config", str(recipe), "--output", str(destination)]
    if preview:
        arguments.append("--dry-run")
    assert cli.main(arguments) == 1
    assert set(tmp_path.iterdir()) == before
    assert marker.read_text() == "original"
    if kind == "file":
        assert destination.read_text() == "original"
    if kind in {"symlink", "dangling"}:
        assert destination.is_symlink()


def test_generated_setup_includes_hosting_guide_and_excludes_old_migration(
    snapshot: Snapshot, config: Config
) -> None:
    files = render(snapshot, config)
    setup = files["docs/adopting.md"].decode()
    assert config.data["github"]["docs_url"] in setup
    assert "github-setup.md#documentation-hosting" in setup
    assert "github-setup.md#repository-settings" in setup
    assert "docs/github-setup.md" in files
    assert b"Existing clone migration" not in files["docs/CONTRIBUTING.md"]
    assert b"## Change requirements" in files["docs/CONTRIBUTING.md"]
