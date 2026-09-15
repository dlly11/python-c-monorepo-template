# Workstation setup

Use the section for your operating system, then run the common initialization commands from the
repository root. Git is assumed to be installed. Python-only work needs just Python and uv;
native, analysis, documentation, and coverage tools can be installed when those workflows are needed.

## Requirements and validated versions

| Tool | Requirement | Validated on the Linux development host |
| --- | --- | --- |
| Python | 3.12 or newer; CI tests 3.12, 3.13, and 3.14 | 3.12.14 |
| uv | 0.10.9 or newer for workspace build constraints | 0.12.11 |
| CMake | 3.25 or newer | 4.4.2 |
| Ninja | Required by the presets | 1.13.2 |
| C / C++ compiler | C17 / C++17; C++ is needed for native tests | GCC/G++ 15.3.0 |
| clang-format / clang-tidy | Required for the analysis workflow | 21.1.8 |
| cppcheck | Required for the analysis workflow | 2.21.1 |
| Doxygen | 1.9.2 or newer | 1.17.0 |
| gcov | From the same GCC toolchain used for coverage | 15.3.0 |

These validated versions are a development-host snapshot, not minimums or pinned CI image versions.
The package-manager recipes below may install different versions. The current CI uses GCC on Linux,
Apple Clang on macOS, and MinGW GCC on Windows; native analysis and coverage run on Linux.
The macOS and Windows setup recipes have been checked against upstream instructions but have not
been executed on those operating systems during this change.

## Ubuntu 24.04 or newer

In Bash, install the native tools and uv:

```bash
sudo apt-get update
sudo apt-get install --yes build-essential cmake ninja-build clang-format clang-tidy cppcheck doxygen curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal, or source the environment file named by the uv installer, so `uv` is on PATH.
Select the same compiler family as Linux CI:

```bash
export CC=gcc
export CXX=g++
```

The GCC packages supply gcov. When multiple GCC versions are installed, use matching GCC, G++, and
gcov executables on PATH. The coverage preset explicitly selects `gcc` and `g++`.
See the [official uv installation options](https://docs.astral.sh/uv/getting-started/installation/)
for package-manager and standalone alternatives.

## macOS

Install Apple's command-line developer tools if they are not already present, then use an existing
[Homebrew installation](https://brew.sh/):

```bash
xcode-select --install
brew install uv cmake ninja llvm cppcheck doxygen
export PATH="$(brew --prefix llvm)/bin:$PATH"
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
```

The explicit compiler paths retain Apple Clang for builds, matching CI. Homebrew's
[LLVM formula](https://formulae.brew.sh/formula/llvm) supplies clang-format and clang-tidy and is
keg-only, so its `bin` directory must be added to PATH. Add the exports to your shell profile if you
want them in new terminals. Run native coverage on Linux; the coverage preset is unavailable on macOS.

## Windows

Install [MSYS2](https://www.msys2.org/), open its **UCRT64** terminal, and update it:

```bash
pacman -Syu
```

If the update closes the terminal, reopen UCRT64 and repeat the command before installing packages:

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja
pacman -S --needed mingw-w64-ucrt-x86_64-clang-tools-extra mingw-w64-ucrt-x86_64-cppcheck mingw-w64-ucrt-x86_64-doxygen
```

Use the UCRT64 packages consistently; MSYS2 documents its different
[compiler/runtime environments](https://www.msys2.org/docs/environments/).
The [Clang extra tools package](https://packages.msys2.org/packages/mingw-w64-ucrt-x86_64-clang-tools-extra)
provides clang-tidy and depends on Clang, which also supplies clang-format.

Install native Windows uv from PowerShell:

```powershell
winget install --id=astral-sh.uv -e
```

Open a new PowerShell terminal and add the native tools to this session's PATH. Adjust the MSYS2
installation path if necessary:

```powershell
$env:Path = "C:\msys64\ucrt64\bin;$env:Path"
$env:CC = "gcc"
$env:CXX = "g++"
Get-Command uv, gcc, g++, cmake, ninja
```

Run the common commands below from PowerShell using uv's managed CPython. Do not use MSYS2's Python
for the workspace. For persistence, add the UCRT64 directory to your user PATH through Windows
environment settings. Native coverage and the sanitizer preset are unavailable on Windows.

## Initialize and validate the checkout

From the repository root, these commands work in Bash, Zsh, and PowerShell:

```text
uv python install 3.12
uv sync --locked --all-packages
uv run python scripts/doctor.py --profile python
uv run pytest
uv run python scripts/check_python_install.py
```

For native development:

```text
uv run python scripts/doctor.py --profile native
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

Set `CC` and `CXX` before the first CMake configure. When changing compiler families, use a fresh
build directory; an existing CMake cache retains its compiler selection. Native tests fetch
CppUTest on first configure. Restricted environments can pass
`-DFETCHCONTENT_SOURCE_DIR_CPPUTEST=/approved/sources/cpputest` to configure with an existing
CppUTest 4.0 source tree. Also set `-DFETCHCONTENT_FULLY_DISCONNECTED=ON` when network access must
be disabled.

Select optional workflows explicitly:

```text
uv run python scripts/doctor.py --profile analysis
uv sync --locked --all-packages --group docs
uv run --group docs python scripts/doctor.py --profile docs
uv run --group docs python scripts/build_docs.py
```

On Linux, also synchronize the `coverage` group and follow the [coverage guide](testing.md).
Install both the `pre-commit` and `commit-msg` hooks with `uv run pre-commit install` after the
analysis tools are available. Existing clones must rerun this command to add the message hook.
See [Contributing](CONTRIBUTING.md) for the Conventional Commit policy and repair commands.

## Understanding doctor output

Run `python scripts/doctor.py --profile all` with an existing Python 3.12+ interpreter for a read-only
check of all system prerequisites. The script itself never installs packages or changes PATH.
Using the `uv run` prefix above can synchronize the workspace before the script starts.

| Profile | Tools checked in addition to the running Python interpreter |
| --- | --- |
| `python` | uv |
| `native` | CMake, Ninja, C and C++ compilers |
| `analysis` | Native tools plus clang-format, clang-tidy, and cppcheck |
| `docs` | uv, CMake, Ninja, C compiler, Doxygen |
| `coverage` | uv, CMake, Ninja, GCC, G++, gcov; requires Linux |
| `all` (default) | All applicable tools; skips native coverage outside Linux |

`OK` includes the executable path and version. `FAIL` identifies missing tools, unsuccessful or
timed-out probes, and known unsupported versions. Fix the reported PATH or installation and rerun.
The command returns 1 if any prerequisite fails and 0 otherwise. Each executable probe times out
after ten seconds. `CC`/`CXX` may name executable paths or compiler launcher commands such as
`ccache gcc`; they are passed as arguments without a shell.

Doctor checks system prerequisites, not Python dependency-group contents or C/C++ language features.
Use `uv sync --locked` with the appropriate group to install Python tools, then run the actual
[quality checks](CONTRIBUTING.md) to validate the resulting toolchain.

The root uv configuration pins setuptools to 84.0.0 for editable installs and distribution builds.
You do not need to install setuptools globally. See the [backend upgrade procedure](dependencies.md)
when deliberately changing that pin.
