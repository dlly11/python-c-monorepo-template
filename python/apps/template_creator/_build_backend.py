"""Add canonical template resources to ordinary PEP 517 builds."""

import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

from setuptools import build_meta as backend
from setuptools.build_meta import (  # noqa: F401
    build_editable,
    get_requires_for_build_editable,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
    prepare_metadata_for_build_editable,
    prepare_metadata_for_build_wheel,
)


def prepare_template() -> None:
    """Source distributions already contain the complete template payload."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    try:
        from template_creator.snapshot import PACKAGE, checkout_root, collect, pack

        root = checkout_root()
        if root is not None:
            with NamedTemporaryFile(dir=PACKAGE, delete=False) as temporary:
                temporary.write(pack(collect(root)))
            Path(temporary.name).replace(PACKAGE / "_template.zip")
        elif not (PACKAGE / "_template.zip").is_file():
            raise ValueError("source distribution is missing its template snapshot")
    finally:
        sys.path.pop(0)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    prepare_template()
    return backend.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    prepare_template()
    return backend.build_sdist(sdist_directory, config_settings)
