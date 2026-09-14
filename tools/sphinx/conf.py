"""Sphinx configuration for the repository-wide documentation site."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

project = "Python and C Monorepo Template"
author = "Python and C Monorepo Template contributors"
copyright = "2026, Python and C Monorepo Template contributors"
release = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
version = release

extensions = [
    "breathe",
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]

root_doc = "docs/index"
source_suffix = {".md": "markdown"}
exclude_patterns = [
    ".git/**",
    ".github/**",
    ".venv/**",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "build/**",
    "dist/**",
    "stage/**",
    "**/__pycache__/**",
    "**/*.egg-info/**",
    "README.md",
    "CHANGELOG.md",
    "tools/README.md",
    "python/**/README.md",
]

myst_enable_extensions = ["colon_fence"]
myst_fence_as_directive = ["mermaid"]

breathe_projects = {"native": str(ROOT / "build/docs/doxygen/xml")}
breathe_default_project = "native"
breathe_domain_by_extension = {"h": "c"}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
nitpicky = True
nitpick_ignore_regex = [
    ("py:class", r"argparse\..*"),
    ("py:class", r"collections\.abc\..*"),
    ("c:identifier", r"size_t"),
    ("cpp:identifier", r"size_t"),
]

templates_path = [str(ROOT / "tools/sphinx/templates")]
html_additional_pages = {"index": "redirect.html"}
html_theme = "furo"
html_title = f"{project} {release}"
html_baseurl = "https://dlly11.github.io/python-c-monorepo-template/"
html_theme_options = {
    "source_repository": "https://github.com/dlly11/python-c-monorepo-template/",
    "source_branch": "main",
    "source_directory": "",
}
