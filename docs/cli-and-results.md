# CLI and Results

This document defines the FaultTeX v0.1 command-line interface, output artifacts,
progress behavior, and structured result formats.

See [runner.md](runner.md) for execution semantics and
[mutation-spec.md](mutation-spec.md) for mutation files.

## Command Structure

FaultTeX provides three commands:

```text
faulttex apply PROJECT MUTATION --output OUTPUT_DIR
faulttex check PROJECT MUTATION
faulttex batch PROJECT MUTATIONS_DIR --output OUTPUT_DIR
```

Required input resources are positional arguments. Output destinations and behavior
switches are options. Invoking `faulttex` without a command only displays help and does
not modify or compile a project.

The LaTeX entrypoint is not a CLI argument. Every mutation spec declares its own
project-relative `entrypoint`, allowing one project and one mutation spec to define a
complete mutation run.

## Global Options

```text
--help
--version
-v, --verbose
-q, --quiet
```

`--verbose` shows additional runner progress and failure detail. `--quiet` suppresses
normal progress and success summaries but does not suppress errors. The two options are
mutually exclusive.

## `apply`

`apply` executes one mutation against one clean LaTeX project:

```bash
faulttex apply PROJECT MUTATION --output OUTPUT_DIR
```

Example:

```bash
faulttex apply \
  /path/to/latex-project \
  /another/path/change.yaml \
  --output /desired/run-output
```

### Arguments

`PROJECT` is the existing LaTeX project root. It may be located anywhere and is never
modified in place.

`MUTATION` is one existing mutation YAML file. Its filename and location have no schema
meaning and are not used as a mutation ID.

### Options

```text
-o, --output PATH    Required output directory for this run.
--keep-source        Retain the mutated project copy in the output.
--overwrite          Replace existing FaultTeX-owned artifacts at the destination.
```

Without `--overwrite`, FaultTeX refuses to replace an existing output artifact. With
`--overwrite`, it may replace documented FaultTeX artifacts but must not recursively
clear unrelated files from a caller-owned directory.

### Behavior

`apply` validates the spec, creates an independent working copy, applies exactly one
change, compiles the spec's `entrypoint`, and writes one result. A domain failure returns
a failed `result.json` whenever the output destination remains writable.

## `check`

`check` validates one mutation without copying, modifying, or compiling the project:

```bash
faulttex check PROJECT MUTATION
```

Example:

```bash
faulttex check /path/to/latex-project /another/path/change.yaml
```

It verifies:

- The YAML and schema are valid.
- `entrypoint` exists and remains inside the project.
- `change.file` exists and remains inside the project.
- The complete mutation `needle` occurs exactly once in `change.file`.

`check` has one command-specific option:

```text
--json    Write a machine-readable check result to stdout.
```

By default it writes a concise human-readable result. With `--json`, stdout contains only
the JSON result; diagnostic logging remains on stderr. `check` never writes an artifact
directory.

## `batch`

`batch` applies every discovered mutation in one directory independently to the same
clean project:

```bash
faulttex batch PROJECT MUTATIONS_DIR --output OUTPUT_DIR
```

Example:

```bash
faulttex batch \
  /path/to/latex-project \
  /path/to/mutations \
  --output /desired/batch-output
```

This interface is intended for research workloads that generate hundreds or thousands
of mutated PDFs from one original paper.

### Arguments

`PROJECT` has the same meaning as for `apply`.

`MUTATIONS_DIR` is an existing directory containing mutation specs. The directory may be
located anywhere and does not need to be adjacent to the project or output.

### Options

```text
-o, --output PATH    Required root directory for batch artifacts.
--recursive          Also discover mutation YAML files in subdirectories.
--keep-source        Retain every mutated project copy.
--overwrite          Replace existing FaultTeX-owned batch artifacts.
```

FaultTeX v0.1 executes batch items sequentially. Parallel execution and a `--jobs` option
are future extensions.

### Mutation Discovery

Without `--recursive`, FaultTeX discovers regular `*.yaml` and `*.yml` files directly
inside `MUTATIONS_DIR`. With `--recursive`, it discovers them at every depth.

Discovered specs are ordered lexicographically by their path relative to
`MUTATIONS_DIR`. This ordering is deterministic and is used only for execution order and
batch run IDs; the filename is not a semantic mutation ID. Non-YAML files are ignored.
An empty discovery result is a batch failure.

Every discovered YAML is attempted. A schema, matching, application, or compilation
failure in one item is recorded and does not prevent later items from running.

### Reuse of Single-Mutation Execution

Batch is an orchestration layer over the same single-mutation runner used by `apply`:

```text
for each discovered mutation:
    apply the mutation independently to the same clean project
    write one apply-compatible output directory
    collect its result
```

Batch must not implement separate matching, mutation, or compilation logic.

### Batch Run IDs

After sorting, batch assigns six-digit sequential IDs beginning at `000001`:

```text
000001
000002
000003
...
```

These IDs identify runs within one batch output and name their directories. They are not
stored in mutation specs and are not derived from mutation filenames. `batch-result.json`
records the mapping from each ID to its input spec.

### Progress Output

Batch uses Typer's native `typer.progressbar(...)` support. In an interactive terminal it
shows total progress, ETA, success and failure counts, and the current mutation path. A
representative display is:

```text
FaultTeX  [########------------]  347/1200  success=342 failed=5
```

Progress is diagnostic output and is written to stderr so that stdout remains available
for machine-readable output. Compiler output is captured in each run's `compile.log`
rather than streamed into the progress display.

`--quiet` hides the progress bar. `--verbose` may emit per-mutation start and completion
details in addition to progress. Batch always prints or logs a final summary unless
`--quiet` is active.

## Output Layout

The caller chooses each apply output directory and each batch output root. No relationship
is required among the project, mutation input, and output paths.

### Apply Output

A successful apply output is:

```text
OUTPUT_DIR/
├── <entrypoint-stem>.pdf
├── result.json
├── compile.log
└── source/                    # only with --keep-source
```

For example, `entrypoint: main.tex` produces `main.pdf`, while
`entrypoint: manuscript.tex` produces `manuscript.pdf`.

If execution fails before compilation, `compile.log` is absent. If compilation fails,
the log and failed result are retained but the PDF is absent. `source/` is present only
when requested and a working copy was created.

### Batch Output

Each batch run directory has exactly the same artifact structure and result schema as an
`apply` output:

```text
BATCH_OUTPUT/
├── batch-result.json
├── 000001/
│   ├── main.pdf
│   ├── result.json
│   └── compile.log
├── 000002/
│   ├── main.pdf
│   ├── result.json
│   └── compile.log
└── 000003/
    └── result.json
```

The actual PDF name in each directory follows that mutation spec's `entrypoint`. Because
every spec is self-contained, specs in one batch may technically declare different
entrypoints, although the common research workflow uses the same entrypoint throughout.

## Mutation Result

FaultTeX writes program-generated JSON to `result.json`. Mutation specs remain YAML
because they contain author-edited multiline LaTeX.

### Successful Result

```json
{
  "schema": 1,
  "status": "success",
  "artifacts": {
    "pdf": "main.pdf",
    "log": "compile.log"
  }
}
```

If `--keep-source` is active, the result includes the retained source:

```json
{
  "schema": 1,
  "status": "success",
  "artifacts": {
    "pdf": "main.pdf",
    "log": "compile.log",
    "source": "source"
  }
}
```

Artifact paths are relative to the directory containing `result.json`.

### Matching Failure

```json
{
  "schema": 1,
  "status": "failed",
  "stage": "match",
  "error": "The complete target text occurred 0 times in sections/results.tex.",
  "artifacts": {}
}
```

### Compilation Failure

```json
{
  "schema": 1,
  "status": "failed",
  "stage": "compile",
  "error": "LaTeX compilation returned a non-zero exit code.",
  "artifacts": {
    "log": "compile.log"
  }
}
```

Failure-stage meanings are defined in [runner.md](runner.md).

## Batch Result

`batch-result.json` summarizes the complete batch and maps sequential run IDs to input
mutation paths and individual results:

```json
{
  "schema": 1,
  "status": "partial_failure",
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "runs": [
    {
      "id": "000001",
      "mutation": "replace-number.yaml",
      "result": "000001/result.json",
      "status": "success"
    },
    {
      "id": "000002",
      "mutation": "reverse-conclusion.yaml",
      "result": "000002/result.json",
      "status": "success"
    },
    {
      "id": "000003",
      "mutation": "delete-evidence.yaml",
      "result": "000003/result.json",
      "status": "failed"
    }
  ]
}
```

Mutation paths in `batch-result.json` are relative to `MUTATIONS_DIR`. Recursive batches
therefore retain enough path information to distinguish equal filenames in different
subdirectories.

The aggregate status is `success` when every item succeeds and `partial_failure` when at
least one item fails after discovery has begun.

## Exit Codes

FaultTeX uses a small exit-code contract:

```text
0    The command succeeded; for batch, every mutation succeeded.
1    A FaultTeX validation, mutation, compilation, or output failure occurred.
2    The command line or option usage is invalid.
3    An unexpected internal error occurred.
```

Batch continues after item-level failures, writes the aggregate result, and exits with
code `1` after all items finish if any item failed.

## Result Scope

FaultTeX v0.1 results intentionally do not record:

- A semantic mutation ID inferred from a spec filename.
- SHA-256 hashes.
- PDF page bounding boxes.
- Compiler image digests.
- Character offsets or LaTeX AST data.
- Page-level visual differences.
- Automatic semantic validation.

These may be added later if required by real workflows.
