"""Package canonical template files without requiring Git at runtime."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

SOURCE_URL = "https://github.com/dlly11/python-c-monorepo-template"
PACKAGE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Snapshot:
    """The immutable input files and their portable content identity."""

    files: dict[str, bytes]

    @property
    def version(self) -> str:
        return self.files["version.txt"].decode().strip()

    @property
    def digest(self) -> str:
        digest = hashlib.sha256()
        for name, content in sorted(self.files.items()):
            digest.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
        return digest.hexdigest()


def safe_name(name: str) -> bool:
    """Accept only regular relative paths portable to Windows and POSIX."""
    path = PurePosixPath(name)
    return (
        bool(name)
        and not path.is_absolute()
        and all(
            part not in {"", ".", ".."} and ":" not in part and "\\" not in part
            for part in name.split("/")
        )
    )


def checkout_root() -> Path | None:
    """Recognize this application's source layout, never the user's cwd."""
    parents = PACKAGE.parents
    if len(parents) > 4:
        root = parents[4]
        if (root / "python/apps/template_creator/src/template_creator") == PACKAGE:
            return root
    return None


def collect(root: Path) -> Snapshot:
    """Read only the explicitly classified canonical files."""
    inventory = json.loads((PACKAGE / "inventory.json").read_text(encoding="utf-8"))
    files = {}
    for name in inventory["include"]:
        if not safe_name(name):
            raise ValueError(f"unsafe template path: {name}")
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError(f"template path must be a regular file: {name}")
        # Git's attributes prescribe LF; normalize Windows source archives too.
        files[name] = path.read_bytes().replace(b"\r\n", b"\n")
    return Snapshot(files)


def load() -> Snapshot:
    """Read the packaged snapshot, or the canonical files in an editable checkout."""
    root = checkout_root()
    if root is not None:
        return collect(root)
    with ZipFile(PACKAGE / "_template.zip") as archive:
        files = {}
        total = 0
        for entry in archive.infolist():
            total += entry.file_size
            if (
                not safe_name(entry.filename)
                or entry.filename in files
                or entry.is_dir()
                or (entry.external_attr >> 16) & 0o170000 == 0o120000
                or total > 50_000_000
            ):
                raise ValueError("invalid bundled template archive")
            files[entry.filename] = archive.read(entry)
    return Snapshot(files)


def pack(snapshot: Snapshot) -> bytes:
    """Produce the same archive bytes for the same canonical inputs."""
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(snapshot.files.items()):
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    return output.getvalue()
