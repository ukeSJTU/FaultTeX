<h1 align="center">FaultTeX</h1>

<p align="center">
  Controlled, reproducible fault injection for scientific papers written in LaTeX.
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://img.shields.io/badge/uv-0.12-DE5FE9?style=for-the-badge&logo=uv&logoColor=white" alt="uv 0.12"></a>
  <a href="https://docs.pydantic.dev/"><img src="https://img.shields.io/badge/Pydantic-2-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic 2"></a>
  <a href="https://typer.tiangolo.com/"><img src="https://img.shields.io/badge/Typer-CLI-009688?style=for-the-badge&logo=typer&logoColor=white" alt="Typer CLI"></a>
  <a href="https://mg.readthedocs.io/latexmk.html"><img src="https://img.shields.io/badge/LaTeX-latexmk-008080?style=for-the-badge&logo=latex&logoColor=white" alt="LaTeX with latexmk"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#write-a-mutation">Write a mutation</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#agent-skill">Agent skill</a> ·
  <a href="#documentation">Documentation</a>
</p>

FaultTeX takes a clean LaTeX project and an explicit YAML mutation, applies exactly one
source change to an independent copy, recompiles that copy, and records the resulting PDF
and a structured execution result.

It is built for research datasets and evaluations that need known paper defects, such as
corrupted numbers or entities, reversed conclusions, claim--evidence inconsistencies, and
omitted information.

```text
clean LaTeX project + mutation.yaml
                  │
                  ├─ copy project
                  ├─ match one exact target
                  ├─ apply one change
                  ├─ compile with latexmk + SyncTeX
                  └─ add native PDF annotations
                           ↓
              annotated mutated PDF + result.json
```

> [!IMPORTANT]
> FaultTeX executes mutations; it does not invent them or decide whether a scientific
> claim is true. Targets, replacement LaTeX, and semantic intent must be supplied
> explicitly by a person, generator, or agent.

## Why FaultTeX?

- **Reproducible:** raw LaTeX is matched exactly; no fuzzy search or hidden repair.
- **Isolated:** every mutation starts from the same clean project, including batch runs.
- **Safe by design:** the original project is never edited in place.
- **Explicit on failure:** missing, ambiguous, invalid, or uncompilable mutations produce
  structured failures instead of best-effort output.
- **Automation-friendly:** human-authored YAML goes in; stable JSON results and PDFs come
  out.

## Quick start

### Requirements

- [uv](https://docs.astral.sh/uv/) 0.12
- Python 3.11 or newer
- [`latexmk`](https://mg.readthedocs.io/latexmk.html), `synctex`, and the LaTeX packages
  required by your paper
- Git and Make

FaultTeX currently runs from a source checkout. Clone the repository and install its
locked environment:

```bash
git clone https://github.com/ukeSJTU/FaultTeX.git
cd FaultTeX
make install
```

Verify the CLI and LaTeX toolchain:

```bash
uv run faulttex --help
latexmk --version
synctex help
```

See the [installation guide](docs/installation.md) for TeX distribution choices and
troubleshooting.

### Run the included example

The [`examples/minimal`](examples/minimal) fixture contains one clean multi-file paper and
three independent mutations: a changed result, a reversed conclusion, and a deleted
claim.

First, validate a mutation without modifying or compiling anything:

```bash
uv run faulttex check \
  examples/minimal/project \
  examples/minimal/mutations/replace-number.yaml
```

Expected output:

```text
OK replace_abstract_accuracy: target occurs exactly once in main.tex
```

Then apply and compile it:

```bash
uv run faulttex apply \
  examples/minimal/project \
  examples/minimal/mutations/replace-number.yaml \
  --output tmp/examples/minimal/replace-number
```

FaultTeX writes the mutated PDF with native annotations, the retained mutation, the
compilation log, and `result.json` to the output directory. Replacement text has a green
highlight and comment; a deletion has a red comment at the deletion point. The annotations
are visible in PDF readers such as macOS Preview. The source under
`examples/minimal/project` remains unchanged.

To run all three mutations independently:

```bash
uv run faulttex batch \
  examples/minimal/project \
  examples/minimal/mutations \
  --output tmp/examples/minimal/batch
```

## Write a mutation

One YAML file describes one independent change and declares the LaTeX entrypoint to
compile. This example changes the accuracy in the paper's abstract:

```yaml
schema: 1
id: replace_abstract_accuracy
entrypoint: main.tex
description: >
  Change the abstract accuracy while leaving the result table unchanged.
label: number_corruption

change:
  type: text.replace
  file: main.tex
  before_context: |-
    accuracy of $
  old_text: |-
    84.6
  new_text: |-
    74.6
  after_context: |-
    \%$ while retaining competitive calibration error.
```

The complete target is assembled as:

```text
before_context + old_text + after_context
```

It must occur **exactly once** in the named file. Zero matches and multiple matches both
fail. For deletions, use `type: text.delete` with a `text` field instead of `old_text` and
`new_text`.

> [!TIP]
> Use YAML literal blocks (`|-`) for exact source fields. Folded blocks (`>`) can change
> line breaks and make an otherwise correct target fail to match.

Read the complete [mutation schema](docs/mutation-spec.md) for field constraints,
multiline LaTeX guidance, and more examples.

## Commands

| Command | Purpose | Writes or compiles? |
| --- | --- | --- |
| `faulttex check PROJECT MUTATION` | Validate schema, paths, and exact target uniqueness | No |
| `faulttex apply PROJECT MUTATION -o OUTPUT` | Apply one mutation and compile one independent project copy | Yes |
| `faulttex batch PROJECT MUTATIONS_DIR -o OUTPUT` | Apply every discovered YAML mutation independently | Yes |

Useful options:

- `--json` gives `check` machine-readable output.
- `--keep-source` retains the mutated project copy for `apply` or `batch`.
- `--overwrite` replaces existing FaultTeX-owned artifacts at the destination.
- `--recursive` lets `batch` discover YAML files in nested directories.
- `--verbose` adds execution detail; `--quiet` suppresses normal progress and success
  summaries.

For the authoritative interface and exit behavior, see [CLI and results](docs/cli-and-results.md).

## Outputs

A successful `apply` run produces:

```text
OUTPUT/
├── mutation.yaml
├── main.pdf
├── compile.log
├── result.json
└── source/            # only with --keep-source
```

`main.pdf` is the ordinary mutated PDF artifact and also contains the native annotations;
FaultTeX does not create a second annotated-PDF filename or require annotation CLI options.

`result.json` is designed for downstream tooling:

```json
{
  "schema": 1,
  "id": "replace_abstract_accuracy",
  "status": "success",
  "artifacts": {
    "mutation": "mutation.yaml",
    "pdf": "main.pdf",
    "log": "compile.log"
  }
}
```

Batch runs add a `batch-result.json` summary and place each mutation under
`mutations/<mutation-id>/`. If one item fails after batch preflight, later items still run
and the aggregate status becomes `partial_failure`.

## Behavioral contract

FaultTeX deliberately keeps its execution model narrow:

- It supports `text.replace` and `text.delete` in schema 1.
- Each spec contains exactly one change.
- It edits only the explicitly named project-relative file.
- It does not normalize whitespace, search other files, choose among matches, or repair
  LaTeX.
- It invokes ordinary `latexmk -pdf` with SyncTeX data, then adds and verifies native PDF
  annotations without rewriting the LaTeX mutation.
- Batch execution is sequential, deterministic, and non-cumulative.

These constraints make every generated defect traceable. See the
[runner contract](docs/runner.md) for validation stages, path safety, compilation, and
failure semantics.

## Agent skill

FaultTeX ships with the official
[`faulttex-author-mutations`](skills/faulttex-author-mutations/SKILL.md) skill. It helps a
coding agent inspect a clean LaTeX project, author exact `text.replace` or `text.delete`
YAML files, and validate them before execution.

Install it with the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add ukeSJTU/FaultTeX --skill faulttex-author-mutations
```

Add `--global` to install it for all projects. Then ask your agent, for example:

```text
Use $faulttex-author-mutations to create three independent mutations for this paper:
corrupt the headline result, reverse the conclusion, and omit the main ablation claim.
```

The skill authors and validates specs; it does not modify the clean project or compile
PDFs unless you explicitly request execution. Its validator expects `faulttex` on `PATH`.

## Documentation

- [Installation](docs/installation.md) — uv, Python, `latexmk`, and common setup issues
- [Mutation spec](docs/mutation-spec.md) — schema 1 and exact-match authoring rules
- [CLI and results](docs/cli-and-results.md) — commands, artifacts, JSON, and batch behavior
- [Runner](docs/runner.md) — execution stages, isolation, and failure semantics
- [Design](docs/design.md) — goals, architecture, and intentional non-goals
- [Minimal example](examples/minimal/README.md) — a runnable paper and three mutations

## Development

To change FaultTeX itself, start with [`AGENTS.md`](AGENTS.md). It is the single entry
point for repository layout, dependency policy, implementation conventions, and required
checks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
