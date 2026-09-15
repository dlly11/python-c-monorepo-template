"""Installed header and test-dependency validation."""

from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def installation(tmp_path: Path, scripts: dict[str, ModuleType]) -> Path:
    checker = scripts["check_native_install"]
    for relative_path, prefix in checker.COMPONENTS.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(checker.expected_definitions(prefix, "1.2.3")) + "\n", encoding="utf-8"
        )
    return tmp_path


def test_valid_installation(installation: Path, scripts: dict[str, ModuleType]) -> None:
    assert scripts["check_native_install"].install_errors(installation, "1.2.3") == []


@pytest.mark.parametrize(
    "defect", ["missing_header", "missing_macro", "stale_string", "stale_number"]
)
def test_invalid_version_header(
    defect: str, installation: Path, scripts: dict[str, ModuleType]
) -> None:
    header = installation / "include/example/core_version.h"
    if defect == "missing_header":
        header.unlink()
    else:
        contents = header.read_text(encoding="utf-8")
        if defect == "missing_macro":
            contents = contents.replace("#define EXAMPLE_CORE_VERSION_MAJOR 1\n", "")
        elif defect == "stale_string":
            contents = contents.replace('"1.2.3"', '"1.2.2"')
        else:
            contents = contents.replace("VERSION_PATCH 3", "VERSION_PATCH 2")
        header.write_text(contents, encoding="utf-8")
    errors = scripts["check_native_install"].install_errors(installation, "1.2.3")
    assert len(errors) == 1
    assert "core_version.h" in errors[0]


def test_cpputest_content_is_rejected(installation: Path, scripts: dict[str, ModuleType]) -> None:
    library = installation / "lib/libCppUTest.a"
    library.parent.mkdir()
    library.touch()
    errors = scripts["check_native_install"].install_errors(installation, "1.2.3")
    assert len(errors) == 1
    assert "test-only CppUTest content was installed" in errors[0]
