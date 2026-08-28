# FaultTeX

> Controlled fault injection for scientific papers written in LaTeX.

FaultTeX takes a clean LaTeX paper project and an explicit mutation spec, applies one
precise and reproducible source change to an independent copy, and recompiles the mutated
paper as a PDF. It is designed for constructing controlled paper defects and evaluating
claim--evidence consistency, fact checking, and scientific-paper understanding systems.

FaultTeX is being developed as a supporting tool for a broader research project on
AI-assisted scientific-paper understanding and evaluation. Within that project, it
provides a fast way to generate large collections of controlled, independently mutated
papers for research datasets and experiments.

FaultTeX v0.1 provides a strict workflow based on exact raw-LaTeX matching, isolated
mutations, explicit failures, and ordinary `latexmk` compilation.

## Technology Stack

FaultTeX v0.1 uses a deliberately small Python stack:

- [PyYAML](https://pyyaml.org/) safely loads and writes human-authored mutation YAML.
- [Pydantic](https://docs.pydantic.dev/) defines and validates mutation and result
  models after parsing.
- [Typer](https://typer.tiangolo.com/) provides the `apply`, `batch`, and `check`
  command-line interface.
- Python's `pathlib`, `shutil`, and `tempfile` modules handle safe path resolution,
  independent project copies, and temporary working directories.
- [`latexmk`](https://mg.readthedocs.io/latexmk.html) compiles each mutated project.
  It is an external runtime prerequisite and is expected to be available on `PATH`;
  FaultTeX does not install a TeX distribution.
- [structlog](https://www.structlog.org/) provides structured runtime logging.

## Project Documentation

- [Design](docs/design.md): goals, architecture, principles, scope, and acceptance
  criteria.
- [Mutation spec](docs/mutation-spec.md): YAML schema, supported changes, exact matching,
  authoring requirements, and examples.
- [Mutation runner](docs/runner.md): validation, project isolation, application,
  compilation, and failure semantics.
- [CLI and results](docs/cli-and-results.md): commands, batch progress, output artifacts,
  and structured JSON results.
- [Installation](docs/installation.md): installing uv, Python, project dependencies, and
  a LaTeX toolchain.

## Working with a Coding Agent

This repository includes [`AGENTS.md`](AGENTS.md), with the build, test, dependency,
layout, and release conventions a coding agent needs for routine work.
`CLAUDE.md` imports the same instructions for Claude Code.

For an ordinary change, tell your agent: “Read `AGENTS.md`, implement this change, and
run the required checks.”
For toolchain or template maintenance, ask it to use the
[simple-modern-uv skill](https://github.com/jlevy/simple-modern-uv/tree/main/skills/simple-modern-uv),
which distinguishes selective feature adoption from a full Copier update.

*This project was built from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).*

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
