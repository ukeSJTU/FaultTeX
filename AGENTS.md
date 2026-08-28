# Project Instructions for AI Agents

Instructions for AI coding agents working on faulttex.

This file follows the [AGENTS.md](https://agents.md) convention.
Claude Code reads `CLAUDE.md`, which imports this file through its `@AGENTS.md` line, so
both instruction paths stay aligned.

## Project Purpose

FaultTeX is a controlled mutation tool for scientific papers written in LaTeX. It takes
a clean LaTeX project and an explicit mutation spec, applies a precise and reproducible
mutation to an independent project copy, recompiles that copy, and records the mutated
PDF and execution result.

FaultTeX is being developed as a supporting tool for a broader research project on
AI-assisted scientific-paper understanding and evaluation. It enables that project to
quickly generate large collections of controlled, independently mutated papers for
research datasets and experiments.

The project supports controlled research datasets and evaluations involving known paper
defects, including claim--evidence inconsistencies, corrupted numbers or entities,
reversed conclusions, and omitted information. FaultTeX executes mutations; it does not
decide whether claims are scientifically true or generate mutation content itself.

## Core Behavioral Contract

- The original LaTeX project is immutable. Every mutation runs against its own copy of
  the same clean project.
- Mutations are independent and deterministic; outputs from one mutation are never used
  as input to another.
- The runner applies only targets explicitly identified by a mutation spec. The current
  schema uses raw LaTeX in a named file and exact matching; do not add implicit guessing,
  normalization, or cross-file search outside a versioned design change.
- Ambiguous or missing targets and compilation errors produce explicit failures rather
  than automatic repair or best-effort output.
- Mutation authors are responsible for the semantic intent and replacement LaTeX. The
  runner is responsible for validation, exact application, compilation, and results.
- Version-specific constraints and interfaces belong in the product documentation. Do
  not broaden them implicitly while implementing a feature.

See [docs/design.md](docs/design.md) for the product design,
[docs/mutation-spec.md](docs/mutation-spec.md) for mutation schema 1,
[docs/runner.md](docs/runner.md) for execution semantics, and
[docs/cli-and-results.md](docs/cli-and-results.md) for the CLI and artifact
contracts.

## Development Workflow

This project uses [uv](https://docs.astral.sh/uv/) for Python and dependency management.
See [docs/installation.md](docs/installation.md) for uv, Python, and `latexmk`
prerequisites. The `Makefile` selects the checked-in `uv.toml` automatically and wraps
the common development commands:

```bash
make install     # uv sync --all-extras --all-groups (install all deps into .venv)
make             # install, lint, and test
make lint        # auto-format and lint: codespell, ruff check --fix, ruff format, basedpyright
make lint-check  # check-only variant, matching CI (fails instead of fixing)
make test        # uv run pytest
make build       # locked, non-isolated uv build (wheel and sdist)
make clean       # remove generated build, test, lint, cache, and virtualenv artifacts
make upgrade     # upgrade all locked dependency groups under the project cooldown policy
```

Run targeted checks directly when appropriate:

```bash
UV_CONFIG_FILE=uv.toml uv run pytest tests/test_foo.py
UV_CONFIG_FILE=uv.toml uv run pytest -s tests/test_foo.py::test_name
UV_CONFIG_FILE=uv.toml uv run faulttex --help
```

Before handing off a change, run checks in proportion to its risk. Documentation-only
changes require at least `make lint-check`; implementation changes normally require both
`make lint-check` and `make test`. Run `make build` when packaging or entry points change.

## Conventions

- **Layout**: `src/` layout; code in `src/faulttex/`, tests in `tests/`.

- **Python**: 3.11+ only; use modern typing (full annotations, no `from __future__`).

- **Lint/format**: ruff (line length 100) plus codespell; type checking is
  [basedpyright](https://docs.basedpyright.com/). Tool settings live in
  `pyproject.toml`; project-owned uv settings live in `uv.toml`. Run `make lint` before
  committing.

- **Dependencies**: vet package necessity and spelling before adding it. Add with
  `UV_CONFIG_FILE=uv.toml uv add --exclude-newer "14 days"` (runtime) or
  `UV_CONFIG_FILE=uv.toml uv add --dev --exclude-newer "14 days"` (dev). Commit
  `pyproject.toml` and `uv.lock` together. Don’t use pip, poetry, or requirements.txt.

- **Supply-chain policy**: `uv.toml` enforces a 14-day dependency cooldown. Keep project
  configuration selected so ambient user settings cannot alter `uv.lock`. A reviewed
  emergency bypass must be explicit for one invocation with `UV_EXCLUDE_NEWER="0 days"`
  and document why the normal gate was bypassed. Use a larger value for stricter updates.

- **Versioning**: the version comes from git tags via dynamic versioning; never edit a
  version number in `pyproject.toml`.

## Template Maintenance

This project was built from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).
Routine project work uses the instructions above; do not fetch the upstream template for
every task.

For toolchain changes, selective adoption of another template feature, or a Copier
update, use the portable
[simple-modern-uv skill](https://github.com/jlevy/simple-modern-uv/tree/main/skills/simple-modern-uv).
It preserves project-specific choices and distinguishes selective changes from full
template management.
`.copier-answers.yml` records this project’s update lineage.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
