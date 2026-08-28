---
name: faulttex-author-mutations
description: Create and validate FaultTeX mutation YAML files from a LaTeX source project and a requested text edit or scientific-paper mutation. Use when an agent must author one or many exact text.replace or text.delete specs; do not use merely to execute existing specs or modify FaultTeX itself.
---

# Author FaultTeX Mutations

Turn the user's requested change into valid, independently executable FaultTeX mutation
specs. Preserve the user's intent: a direct text edit does not need to be reframed as a
scientific defect.

## Authoring Workflow

1. Identify the clean LaTeX project, its compilation entrypoint, the requested change,
   the number of mutations, and the destination for generated YAML files. If the
   entrypoint is ambiguous after inspecting likely root files, ask the user instead of
   guessing.
2. Read raw `.tex` source. Follow relevant `\input` and `\include` references when the
   target is not in the entrypoint. Do not derive exact mutation text from a rendered PDF.
3. Create one YAML file per independent change. Every spec must target the original clean
   project, never the output of another mutation.
4. Copy target text and context exactly from one source file, preserving whitespace,
   newlines, comments, commands, and escapes. Never use ellipses, offsets, line numbers,
   occurrence numbers, fuzzy matching, or whitespace normalization.
5. Use enough `before_context` and `after_context` to make the complete target unique.
   Start with concise context; expand it only when validation reports multiple matches.
   When validation reports zero matches, recopy the source rather than approximating it.
6. Assign each spec a stable `id` that is unique within the clean paper project. Use a
   lowercase ASCII slug containing only letters, digits, underscores, and hyphens; the
   filename may be descriptive but carries no mutation-ID meaning.
7. Write the specs to the user's chosen destination.
8. Run the bundled validator against every generated spec. Fix all schema, file, and
   matching failures before reporting completion.

Do not modify the clean LaTeX project. Do not run `faulttex apply` or compile PDFs unless
the user also asks for execution.

## Mutation Shapes

Use schema `1` and project-relative paths. Exact source fields should use YAML literal
blocks (`|-`). A replacement has this shape:

```yaml
schema: 1
id: abstract_claim_direction_001
entrypoint: main.tex
description: >-
  Describe the requested change and its intended effect.
label: requested_text_change
change:
  type: text.replace
  file: sections/results.tex
  before_context: |-
    Exact source immediately before the target
  old_text: |-
    Exact source to replace
  new_text: |-
    Exact replacement source
  after_context: |-
    Exact source immediately after the target
```

A deletion uses the same top-level fields and this change shape:

```yaml
change:
  type: text.delete
  file: sections/results.tex
  before_context: |-
    Exact source immediately before the target
  text: |-
    Exact source to delete
  after_context: |-
    Exact source immediately after the target
```

`label` describes the effect, not the edit operator. Prefer lowercase `snake_case`; use a
plain label such as `requested_text_change` when the user requests an ordinary edit with
no defect taxonomy.

`id` identifies one mutation within the clean paper project. Keep it stable when moving
or renaming the YAML file, and never infer it from the filename during validation or
execution. The bundled validator rejects duplicate IDs when validating a directory.

## Validate Generated Specs

Resolve `scripts/validate_mutations.py` relative to this `SKILL.md`, then run it with the
clean project and either one YAML file or a directory:

```bash
scripts/validate_mutations.py PROJECT MUTATION_OR_DIRECTORY
```

Use `--recursive` for nested mutation directories and `--json` when structured output is
useful. The script delegates to `faulttex check`, so the `faulttex` command must be on
`PATH`. It validates the authoritative FaultTeX schema, project-relative paths, target
files, and exact-match uniqueness without modifying or compiling the project.

Treat a nonzero exit as a validation failure. Report the generated file paths and the
validation summary; do not claim a mutation is ready when validation failed.
