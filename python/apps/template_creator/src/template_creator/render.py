"""Apply explicit naming and metadata transformations to canonical template files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import tomlkit

from template_creator.config import Config, serialize
from template_creator.snapshot import PACKAGE, SOURCE_URL, Snapshot

CREATOR = "monorepo-template-creator"
BEGIN = "# BEGIN TEMPLATE CREATOR ONLY"
END = "# END TEMPLATE CREATOR ONLY"


def without_creator(text: str) -> str:
    """Remove marked upstream-only integration blocks, checking paired anchors."""
    if text.count(BEGIN) != text.count(END):
        raise ValueError("unbalanced creator-only template anchors")
    text = re.sub(
        r"(?s)<!-- BEGIN TEMPLATE CREATOR ONLY -->.*?<!-- END TEMPLATE CREATOR ONLY -->\n",
        "",
        text,
    )
    return re.sub(
        r"(?m)^[ \t]*# BEGIN TEMPLATE CREATOR ONLY\n.*?^[ \t]*# END TEMPLATE CREATOR ONLY\n",
        "",
        text,
        flags=re.DOTALL,
    )


def license_text(config: Config) -> str:
    license = config.data["license"]
    choice = license["choice"]
    if choice == "Custom":
        return license["text"].rstrip() + "\n"
    if choice == "Proprietary":
        return f"Copyright (c) {license['year']} {license['holder']}. All rights reserved.\n"
    content = (PACKAGE / "licenses" / f"{choice.lower()}.txt").read_text(encoding="utf-8")
    return (
        content.replace("[year]", str(license["year"]))
        .replace("[fullname]", license["holder"])
        .replace("[yyyy]", str(license["year"]))
        .replace("[name of copyright owner]", license["holder"])
    )


def rewrite_toml(content: str, config: Config, *, root: bool, private: bool) -> str:
    document: Any = tomlkit.parse(content)
    project = document["project"]
    data = config.data
    if not private:
        project["version"] = data["project"]["version"]
    if root:
        project["description"] = data["project"]["description"]
        tool = document["tool"]
        tool["uv"]["sources"].pop(CREATOR, None)
        document["dependency-groups"].pop("creator-build", None)
        for table, key in (
            (tool["coverage"]["run"], "source"),
            (tool["ruff"]["lint"]["isort"], "known-first-party"),
        ):
            table[key] = [name for name in table[key] if name != "template_creator"]
        tool["ruff"]["lint"]["per-file-ignores"].pop("python/apps/template_creator/**", None)
        tool["ruff"]["lint"]["per-file-ignores"].pop("tools/creator/**", None)
    project["authors"] = [data["author"]]
    choice = data["license"]["choice"]
    project["license"] = {
        "Custom": "LicenseRef-Custom",
        "Proprietary": "LicenseRef-Proprietary",
    }.get(choice, choice)
    project["license-files"] = ["LICENSE"]
    project["urls"] = {
        "Repository": config.repository_url,
        "Documentation": data["github"]["docs_url"],
    }
    prefix = config.distribution_prefix + "-"
    project["dependencies"] = [
        re.sub(r">=.*", ">=" + data["project"]["version"], dependency)
        if dependency.startswith(prefix)
        else dependency
        for dependency in project.get("dependencies", [])
    ]
    return tomlkit.dumps(document)


def render(snapshot: Snapshot, config: Config) -> dict[str, bytes]:
    """Prepare the complete output in memory, without running code or writing files."""
    data = config.data
    project = data["project"]
    substitutions = {
        **{
            f"example-{suffix}": f"{config.distribution_prefix}-{suffix}"
            for suffix in ("core", "package-a", "package-b", "package-a-cli")
        },
        "example_": config.prefix + "_",
        "EXAMPLE_": config.prefix.upper() + "_",
        "example::": config.prefix + "::",
        "example/": config.prefix + "/",
        "MonorepoTemplate": config.cmake_package,
        "monorepo_template": config.prefix,
        "package-a-cli": config.distribution_prefix + "-package-a-cli",
        "python-c-monorepo-template": project["slug"],
        "Python and C Monorepo Template": project["name"],
        "dlly11": data["github"]["owner"],
    }
    pattern = re.compile(
        "|".join(re.escape(key) for key in sorted(substitutions, key=len, reverse=True))
    )

    def renamed(value: str) -> str:
        return pattern.sub(lambda match: substitutions[match.group()], value)

    files: dict[str, bytes] = {}
    license = license_text(config)
    for old_name, source in snapshot.files.items():
        name = renamed(old_name)
        if name in files:
            raise ValueError(f"generated path collision: {name}")
        # uv alone regenerates its lock; no text replacements inside generated metadata.
        if name == "uv.lock":
            files[name] = source
            continue
        content = renamed(without_creator(source.decode("utf-8")))
        if name == "docs/index.md":
            content = content.replace("../python/apps/template_creator/docs/index\n", "")
        if name == "tools/doxygen/Doxyfile":
            content, count = re.subn(
                r"(?m)^PROJECT_NAME\s*=.*$",
                lambda _: (
                    f"PROJECT_NAME           = {json.dumps(project['name'], ensure_ascii=False)}"
                ),
                content,
            )
            if count != 1:
                raise ValueError("template Doxygen PROJECT_NAME anchor changed")
        if name.endswith("pyproject.toml"):
            content = rewrite_toml(
                content, config, root=name == "pyproject.toml", private=name.startswith("tools/")
            )
            files[str(Path(name).with_name("LICENSE")).replace("\\", "/")] = license.encode()
        if name == "tools/release-please/config.json":
            release = json.loads(content)
            entries = release["packages"]["."]["extra-files"]
            release["packages"]["."]["extra-files"] = [
                entry
                for entry in entries
                if "python/apps/template_creator/" not in entry.get("path", "")
            ]
            content = json.dumps(release, indent=2) + "\n"
        if name == "tools/github/repository-policy.json":
            policy = json.loads(content)
            checks = policy["protection"]["required_status_checks"]["checks"]
            policy["protection"]["required_status_checks"]["checks"] = [
                check for check in checks if not check["context"].startswith("Repository creator (")
            ]
            content = json.dumps(policy, indent=2) + "\n"
        if name == "CMakeLists.txt":
            content, count = re.subn(
                r"VERSION \d+\.\d+\.\d+ # x-release-please-version",
                f"VERSION {project['version']} # x-release-please-version",
                content,
            )
            if count != 1:
                raise ValueError("template CMake project VERSION anchor changed")
            content += (
                "\ninstall(FILES LICENSE DESTINATION "
                f'"${{CMAKE_INSTALL_DATADIR}}/licenses/{project["slug"]}")\n'
            )
        if name == "tools/sphinx/conf.py":
            values = {
                "project": project["name"],
                "author": data["author"]["name"],
                "copyright": f"{data['license']['year']}, {data['license']['holder']}",
                "html_baseurl": data["github"]["docs_url"],
            }
            for key, value in values.items():
                content, count = re.subn(
                    rf"(?m)^{key} = .*?$",
                    lambda _, key=key, value=value: (
                        f"{key} = {json.dumps(value, ensure_ascii=False)}"
                    ),
                    content,
                )
                if count != 1:
                    raise ValueError(f"template Sphinx {key} anchor changed")
        # A custom documentation host must also reach each distribution README.
        default_docs = f"https://{data['github']['owner']}.github.io/{project['slug']}/"
        content = content.replace(default_docs, data["github"]["docs_url"].rstrip("/") + "/")
        files[name] = content.encode("utf-8")

    files["version.txt"] = (project["version"] + "\n").encode()
    files["tools/release-please/manifest.json"] = (
        json.dumps({".": project["version"]}, indent=2) + "\n"
    ).encode()
    files["CHANGELOG.md"] = (
        f"# Changelog\n\n## {project['version']}\n\nInitial project baseline.\n".encode()
    )
    files[".github/CODEOWNERS"] = (
        "# Later matching rules take precedence.\n* "
        + " ".join(data["ownership"]["default"])
        + "\n"
        + "".join(
            rule["pattern"] + " " + " ".join(rule["owners"]) + "\n"
            for rule in data["ownership"]["rules"]
        )
    ).encode()
    contact = data["security"]["contact"]
    target = contact if contact.startswith("https://") else "mailto:" + contact
    files["docs/SECURITY.md"] = (
        f"# Security policy\n\nReport suspected vulnerabilities privately to <{target}>.\n"
        "Do not include vulnerability details in public issues or pull requests.\n\n"
        "Include the affected version or commit, reproduction steps, and potential impact.\n"
        "Omit credentials and personal data from examples. Reports against the current main\n"
        "branch are accepted; no response deadline is promised.\n"
    ).encode()
    readme = files["README.md"].decode().split("## Reuse permission", 1)[0]
    readme = re.sub(
        r"(?s)(^# .*?\n\n).*?(?=```text)",
        lambda match: match[1] + project["description"] + "\n\n",
        readme,
        count=1,
    )
    readme += (
        "## License\n\nSee [LICENSE](LICENSE) for this project's licensing terms.\n\n"
        f"Created from the [Python and C monorepo template]({SOURCE_URL}), "
        f"version {snapshot.version}.\n"
    )
    files["README.md"] = readme.encode()
    files["docs/adopting.md"] = setup_guide(config).encode()
    files["template-config.toml"] = serialize(config).encode()
    return files


def setup_guide(config: Config) -> str:
    github = config.data["github"]
    return f"""# Project setup

This project was generated from a saved `template-config.toml`. That file records the
initial creation inputs and template identity; it does not synchronize subsequent edits.

## Develop locally

Follow [workstation setup](workstation.md), then run:

```bash
uv sync --locked --all-packages
uv run repo-tools check-workspace
uv run repo-tools check-versions
```

Run the [validation checklist](testing.md#local-validation) before the first push.
The generated configuration does not install compilers or development dependencies.

## Initialize GitHub

1. Initialize a local Git repository with `git init --initial-branch=main`.
2. Review all files, then create a Conventional Commit such as `chore: initialize project`.
3. Create an empty GitHub repository at `{github["owner"]}/{github["repository"]}` and push
   the initial `main` branch. Do not initialize the remote with a separate README or license.
4. Enable Actions and GitHub Pages using the Actions deployment source. The intended
   documentation address is <{github["docs_url"]}>.
5. Let initialization CI pass. If no run is created, dispatch `ci.yml` on `main`.
6. Configure the merge methods, required checks, release permissions, and branch protection
   in the [release guide](releases.md#github-repository-settings). Confirm CODEOWNERS entries
   have access to the repository; syntax validation cannot check GitHub permissions.
7. Run `uv run repo-tools check-github-settings --repo {github["owner"]}/{github["repository"]}`.
8. Make subsequent changes on a branch and open the first protected PR. Its verified merge
   establishes normal release automation. Initialization itself does not authorize a release.

The generator creates local files only. It does not create commits, remotes, tags,
or GitHub settings.

For new components, follow the [architecture guide](architecture.md).
"""
