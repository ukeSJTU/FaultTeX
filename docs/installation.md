# Installation

FaultTeX currently runs from a source checkout. It requires uv for the Python environment
and an external LaTeX toolchain for compiling mutated projects.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) in the version range
  accepted by `uv.toml`.
- Python 3.11 or newer and earlier than Python 4. uv can install a compatible interpreter.
- `latexmk`, `synctex`, and the LaTeX packages required by the input paper, available on
  `PATH`.
- Git for cloning the repository.

FaultTeX installs Python packages but does not install a TeX distribution. The exact
LaTeX package set depends on the papers being mutated.

## Install uv and Python

Follow the official
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/). On macOS
or Linux, the standalone installer is:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Homebrew users can install uv with:

```bash
brew install uv
```

Verify the installation:

```bash
uv --version
```

uv normally obtains a compatible Python interpreter while synchronizing the project. To
install one explicitly, run:

```bash
uv python install 3.13
```

FaultTeX supports Python 3.11 through 3.14 under the current project configuration.

## Install a LaTeX Toolchain

Install a TeX distribution appropriate for the operating system:

- [TeX Live](https://www.tug.org/texlive/) on Linux and other supported platforms.
- [MacTeX](https://www.tug.org/mactex/) on macOS.
- [MiKTeX](https://miktex.org/download) on Windows and other supported platforms.

Choose an installation that provides `latexmk`, `synctex`, and the packages used by the
target papers. Minimal TeX installations may require additional packages later.

Verify that FaultTeX can find the compiler:

```bash
latexmk --version
synctex help
```

FaultTeX v0.1 invokes `latexmk -pdf` with SyncTeX enabled, so the distribution must also
provide a working PDF LaTeX engine and any bibliography or auxiliary tools required by
the paper. The locked Python environment includes `pdfplumber` and `pypdf` for locating,
writing, and verifying native PDF annotations.

## Set Up the Repository

Clone the repository and enter it:

```bash
git clone https://github.com/ukeSJTU/faulttex.git
cd faulttex
```

Install all locked runtime, development, and build dependencies:

```bash
make install
```

The Makefile selects the checked-in `uv.toml`, creates `.venv`, and runs the equivalent
of `uv sync --all-extras --all-groups`.

## Verify the Setup

Run the repository checks:

```bash
make lint-check
make test
```

Verify the command-line entry point:

```bash
uv run faulttex --help
```

During development, run FaultTeX through `uv run` so it uses the locked project
environment. Build, test, dependency, and code-style instructions for coding agents are
maintained in [AGENTS.md](../AGENTS.md).

## Common Installation Problems

If `uv` reports that its version is unsupported, install a version accepted by the
`required-version` setting in `uv.toml`.

If `latexmk` or `synctex` is not found, verify that the TeX distribution's binary
directory is on `PATH` and restart the shell after installation.

If `latexmk` starts but a paper fails because a `.sty`, bibliography tool, font, or LaTeX
package is missing, install that dependency through the selected TeX distribution. The
required package set belongs to the input paper rather than FaultTeX itself.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
