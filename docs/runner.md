# Mutation Runner

This document defines the execution behavior of the FaultTeX v0.1 Mutation Runner. The
runner turns one validated mutation spec and one clean LaTeX project into an independent
mutated project, compilation artifacts, and a mutation result.

The mutation format is defined in [mutation-spec.md](mutation-spec.md). Commands, output
handling, and result JSON examples are documented in
[cli-and-results.md](cli-and-results.md).

## Responsibilities

For each mutation, the runner is responsible for:

1. Reading the mutation YAML.
2. Validating mutation schema 1.
3. Copying the original LaTeX project.
4. Opening the explicitly named target file in the copy.
5. Performing strict string matching.
6. Applying one replacement or deletion.
7. Saving the mutated source.
8. Invoking the LaTeX compiler.
9. Recording the mutation result and compilation log.

The runner is not responsible for:

- Determining whether a claim is scientifically correct.
- Finding claim--evidence pairs automatically.
- Generating new mutation text.
- Understanding mathematical expressions or a LaTeX AST.
- Determining whether the requested mutation creates the intended scientific defect.

## Execution Process

### 1. Load YAML

The runner reads the mutation spec with a safe YAML parser. Unsafe object construction
must not be enabled.

### 2. Validate the Schema

The runner checks at least:

- `schema` exists and equals `1`.
- `entrypoint`, `description`, `label`, and `change` exist.
- `entrypoint` is a nonempty path value.
- `change.type` is supported.
- `change.file` exists in the spec.
- All fields required by the selected operation are present and valid.

For `text.replace`, the operation fields are `file`, `before_context`, `old_text`,
`new_text`, and `after_context`; `old_text` and `new_text` must be nonempty.

For `text.delete`, the operation fields are `file`, `before_context`, `text`, and
`after_context`; `text` must be nonempty.

Invalid input fails at the `schema` stage before the project is changed or compiled.

### 3. Copy the Original Project

The runner creates an independent working copy of the complete original project. Every
read-write operation after this point targets the copy.

The original project is immutable from FaultTeX's perspective and must never be edited
in place. Each batch item starts from this same clean project rather than the output of a
previous mutation.

The working copy's location and whether it is retained after execution are output-policy
decisions. They are not constraints on how the caller organizes the input project,
mutation spec, or final PDF.

### 4. Resolve Project Paths

`entrypoint` and `change.file` are interpreted relative to the copied project root. Both
resolved paths must remain inside that root and refer to existing files.

Allowed examples include:

```text
main.tex
sections/results.tex
appendix/additional_results.tex
```

Paths that must be rejected for either field include:

```text
/absolute/path/main.tex
../another-project/main.tex
../../secret.txt
```

The runner does not search for another entrypoint or target file when a specified path
does not exist. It also does not search other files when the target file does not contain
the mutation target.

### 5. Read the Target File

FaultTeX v0.1 reads target files as UTF-8 text. A read failure is reported without
attempting to infer another encoding or target file.

### 6. Perform Exact Matching

The runner constructs the operation's complete `needle` as specified in
[mutation-spec.md](mutation-spec.md):

```python
# text.replace
needle = before_context + old_text + after_context

# text.delete
needle = before_context + text + after_context
```

It counts exact occurrences in the named file:

- Zero occurrences fail at the `match` stage.
- More than one occurrence fails at the `match` stage.
- Exactly one occurrence permits execution to continue.

The runner does not normalize whitespace, select an occurrence, perform fuzzy matching,
or continue searching elsewhere.

### 7. Apply the Change

For `text.replace`, the replacement is:

```python
replacement = before_context + new_text + after_context
```

For `text.delete`, the replacement is:

```python
replacement = before_context + after_context
```

The runner replaces the complete `needle` once in memory, then writes the mutated target
back to the copied project. It does not perform any additional formatting, whitespace
cleanup, or LaTeX repair.

Read or write failures at this point fail at the `apply` stage.

### 8. Compile the Mutated Project

The runner enters the copied project directory and invokes ordinary `latexmk`. The
recommended v0.1 invocation is:

```bash
latexmk \
  -pdf \
  -interaction=nonstopmode \
  -halt-on-error \
  <entrypoint>
```

The runner reads `<entrypoint>` from the mutation spec. The CLI does not guess or
override it. See [mutation-spec.md](mutation-spec.md).

The runner captures compiler output in the mutation's compilation log. Compilation fails
when `latexmk` returns a nonzero exit code or when the expected PDF is not produced.

FaultTeX v0.1 does not depend on arXiv submission-tools, a remote compiler API,
distributed workers, or a particular cloud provider.

### 9. Save the Result

The runner writes one structured JSON result for every attempted mutation when the result
destination is writable. A successful result identifies the compiled PDF. A failed
result identifies the stage and error. A retained working copy and compilation log may
be reported as additional artifacts when present.

The output layout and result schema are defined in
[cli-and-results.md](cli-and-results.md).

## Failure Stages

FaultTeX v0.1 distinguishes at least these stages:

### `schema`

The mutation YAML is malformed, uses an unsupported schema or operation, omits a required
field, or otherwise fails schema validation.

### `file`

The entrypoint or target file does not exist, or either path escapes the project root.

### `match`

The complete target string occurs zero times or more than once.

### `apply`

The runner cannot read or write the source while applying the change.

### `compile`

LaTeX compilation fails or does not produce the expected PDF.

### `output`

The runner cannot prepare the configured output destination or write the mutation result
or required artifacts.

These stages are intended for clear debugging. FaultTeX v0.1 does not require a complex
numeric error-code system.

## Batch Isolation

Batch execution is equivalent to applying each mutation independently:

```text
apply(clean project, mutation A)
apply(clean project, mutation B)
apply(clean project, mutation C)
```

It is not equivalent to applying mutations in sequence to one working copy. Every batch
item receives its own project copy and distinct output destination. A failure in one item
must not prevent remaining mutations from running.

The batch command is an orchestration layer over the same single-mutation runner used by
`apply`; it must not implement a separate matching, application, or compilation path.

## Strictness Guarantees

The runner must never make a mutation appear successful by:

- Guessing a different target.
- Relaxing exact matching.
- Editing another file.
- Applying only part of a requested change.
- Skipping a failed change.
- Repairing the mutation spec or mutated LaTeX automatically.

If the runner cannot perform the requested operation exactly and compile its result, it
records an explicit failure.
