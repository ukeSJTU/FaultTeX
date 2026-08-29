# FaultTeX Design

> Controlled fault injection for scientific papers written in LaTeX.

This document describes the product goals, architecture, design principles, scope, and
acceptance criteria for FaultTeX v0.1. The mutation file format is specified in
[mutation-spec.md](mutation-spec.md), runner behavior in [runner.md](runner.md), and the
initial command-line and result interfaces in
[cli-and-results.md](cli-and-results.md).

## Project Overview

FaultTeX is a controlled mutation tool for scientific papers. It takes a complete LaTeX
paper project and one or more mutation spec files, applies precise and reproducible text
changes to the source, and recompiles each changed project as a PDF.

FaultTeX is being developed as a supporting tool for a broader research project on
AI-assisted scientific-paper understanding and evaluation. Its role in that project is
to quickly generate large collections of controlled, independently mutated papers for
research datasets and experiments.

FaultTeX is not intended to repair LaTeX automatically or understand every possible TeX
construct. Its purpose is to provide a simple, transparent, and deterministic pipeline:

```text
Clean LaTeX paper
        +
Explicit mutation description
        ↓
Mutated LaTeX paper
        ↓
Mutated PDF
```

FaultTeX primarily supports the following use cases:

- Building scientific-paper datasets containing known defects.
- Creating claim--evidence inconsistencies.
- Changing experimental results, numbers, entities, or conclusion directions.
- Removing important information from abstracts, conclusions, or body text.
- Generating controlled test samples for paper understanding, fact checking, and
  consistency detection systems.
- Studying whether AI systems can identify errors, contradictions, and missing
  information in papers.

FaultTeX v0.1 focuses on the smallest useful end-to-end workflow. It does not attempt
complex LaTeX semantic parsing or automatic layout analysis.

## Core Design Principles

### One Mutation File Describes One Mutation

Each mutation spec file describes one independent mutation and declares a stable ID that
is unique within the clean project it targets. A spec's path and filename remain
organizational choices made by the caller; they do not define its identity or output
location.

Multiple specs may target the same original LaTeX project, but they do not build on one
another. Every execution starts from the original clean project:

```text
clean project + mutation A → mutant A
clean project + mutation B → mutant B
clean project + mutation C → mutant C
```

The following cumulative process is invalid:

```text
clean project
    → mutation A
    → apply mutation B to the result of A
    → apply mutation C to the result of B
```

This isolation prevents mutations from contaminating one another and gives every mutant
a clear source.

### One Mutation Contains One Change

FaultTeX v0.1 permits exactly one `change` in each mutation spec. A mutation may, for
example:

- Replace one claim.
- Change one experimental number.
- Delete one sentence from an abstract.
- Modify one piece of evidence.
- Reverse one conclusion from an improvement to a decline.

Changing two different locations requires two mutation files. A future schema may allow
multiple atomic changes in one mutation, but that is outside the v0.1 scope.

### Mutation Text Is Raw LaTeX Source

FaultTeX v0.1 does not distinguish among natural language, mathematical expressions,
LaTeX commands, citations, emphasized text, or macro calls. Every matching and
replacement field is treated as a raw LaTeX string.

For example, both of the following can be mutation targets:

```latex
The accuracy is $94.2\%$.
```

```latex
Our \textbf{proposed method} improves accuracy by $4.8\%$.
```

The runner does not parse these strings into text and formatting components. Mutation
authors are primarily responsible for producing valid replacement LaTeX; subsequent
compilation determines whether the mutated project remains compilable.

### Targets Use Exact Context, Not Positional Metadata

FaultTeX v0.1 does not locate changes with:

- Character or byte offsets.
- Line numbers.
- AST node identifiers.
- Occurrence indexes.
- Fuzzy matching.
- Semantic similarity.

Instead, a target is located with exact source context:

```text
before_context + target_text + after_context
```

The complete string must occur exactly once in the specified file. The exact schema and
matching algorithms are defined in [mutation-spec.md](mutation-spec.md).

### Failure Is Better Than Guessing

FaultTeX does not guess where a mutation belongs. A missing target, an ambiguous target,
or a compilation failure produces an explicit failure result.

FaultTeX does not:

- Select the most similar sentence automatically.
- Ignore whitespace differences automatically.
- Repair LaTeX automatically.
- Rewrite a mutation spec automatically.
- Choose an occurrence automatically.
- Skip a failed change silently.
- Search other files after a target-file match fails.

This strict behavior prevents mutations from being applied to unintended locations.

## Architecture and Responsibilities

The v0.1 workflow has three main roles:

```text
Mutation Author
        ↓
Mutation Spec
        ↓
Mutation Runner
        ↓
Mutated LaTeX Project
        ↓
LaTeX Compiler
        ↓
PDF Annotation Resolver
        ↓
Annotated Mutated PDF + Mutation Result
```

### Mutation Author

The Mutation Author decides:

- What defect to create.
- Whether to change a claim or its evidence.
- Which project-relative `.tex` entrypoint to compile.
- Which LaTeX file to modify.
- What the original and replacement text are.
- What semantic effect the mutation should have.

The author may be a researcher, a rule-based generator, an LLM, an agent, or a
FactCC-style mutation program. Authoring rules and examples are included in
[mutation-spec.md](mutation-spec.md).

### Mutation Runner

The Mutation Runner is FaultTeX's core execution program. It validates a mutation,
copies the clean project, changes one target file through strict string matching,
invokes the compiler, adds verified native PDF annotations, and records the result.

The runner does not:

- Determine whether a scientific claim is correct.
- Discover claim--evidence pairs automatically.
- Generate replacement text.
- Interpret mathematical expressions or a LaTeX AST.
- Determine whether a change truly constitutes a scientific error.

The complete execution contract is defined in [runner.md](runner.md).

### LaTeX Compiler

FaultTeX v0.1 uses ordinary `latexmk` compilation. It does not depend on an arXiv
compilation service, HTTP compilation API, distributed task queue, or specific cloud
service. Additional compiler backends may be introduced later without changing the
meaning of existing mutation specs.

### PDF Annotation Resolver

The resolver combines the exact applied source position, SyncTeX output, and PDF text
geometry. It highlights rendered replacement text in green and places a provenance
comment beside it. For a deletion, it places a red provenance comment at the resolved
gap. It updates the normal PDF artifact in place and never injects annotation commands
into the LaTeX source.

## Explicit Non-Goals for v0.1

FaultTeX v0.1 does not:

- Parse a complete LaTeX AST or depend on `pylatexenc` or TexSoup.
- Recover LaTeX source from a PDF.
- Identify claim--evidence pairs automatically.
- Include a built-in LLM or invoke FactCC automatically.
- Perform fuzzy matching or normalize whitespace and line breaks.
- Modify source based on line numbers or offsets.
- Modify multiple locations in one mutation.
- Apply cumulative mutations.
- Validate automatically that the intended semantic defect really exists.
- Compare PDF pages visually or guarantee unchanged pagination.
- Modify figures, tables, fonts, font sizes, boldface, or italics as dedicated
  operations.
- Provide an arXiv submission-tools compilation service.
- Manage large-scale dataset storage or versioning.
- Check paper copyright licenses automatically.
- Reuse previous mutation outputs or mutable LaTeX build state across runs.

These limitations are intentional. The v0.1 goal is a reliable minimal loop:

```text
Agent produces an explicit mutation
        ↓
FaultTeX applies it exactly
        ↓
LaTeX compiles successfully
        ↓
An independent mutated PDF is produced
```

## Acceptance Criteria

FaultTeX v0.1 is complete when it satisfies the following criteria.

### Mutation Specs

- Read a YAML mutation file.
- Require a project-relative `.tex` entrypoint.
- Support `text.replace` and `text.delete`.
- Match exact before, target, and after text.
- Require the complete target to occur exactly once.

### Project Handling

- Never modify the original project.
- Create an independent project copy for each mutation.
- Allow multiple mutations to target the same original project.
- Keep mutation outputs isolated from one another.

### Compilation

- Invoke `latexmk`.
- Read and validate the main `.tex` entrypoint from the mutation spec.
- Preserve the generated PDF and compilation log.
- Return a clear result when compilation fails.

### PDF Annotations

- Enable SyncTeX during compilation.
- Add native annotations to the normal mutated PDF without changing its page geometry or
  extracted text.
- Fail explicitly instead of guessing when the rendered mutation target is missing or
  ambiguous.

### Results

- Produce one structured JSON result for every mutation.
- Include the PDF artifact in successful results.
- Include a failure stage and error message in failed results.
- Continue other mutations in batch mode when one mutation fails.

The runner may retain a mutated source copy and compilation log as additional artifacts.
Their retention and placement are output-policy decisions rather than requirements on
the caller's workspace layout.

### Agent Compatibility

- Allow an agent to generate a valid mutation from the documented schema alone.
- Require no character offsets or knowledge of internal compilation APIs.
- Require only exact LaTeX source fragments from the agent.

## Possible Future Extensions

The deliberately small schema can later add operations such as:

```text
text.insert_before
text.insert_after
citation.replace
reference.delete
figure.replace
table.replace
equation.replace
section.delete
section.move
```

Other possible extensions include:

- Multiple changes in one mutation.
- FactCC-style automatic mutation generators.
- A built-in claim--evidence agent.
- LaTeX AST targeting or whitespace-tolerant matching.
- Mutation diff export.
- PDF text validation and visual comparison.
- Mutation difficulty levels and structured claim--evidence annotations.
- Automatic dataset indexes and train/dev/test splits.
- Parallel batch compilation and Dockerized compiler environments.
- An arXiv submission-tools backend.
- Mutation provenance and project or artifact hashes.

These features should be considered only after the v0.1 loop is stable.

## Summary

FaultTeX v0.1 is a strict, deterministic executor for controlled mutations of LaTeX
papers:

```text
one mutation = one YAML file
one mutation = one change
one mutation = one independent paper variant
```

The Mutation Author finds and understands the target and produces exact old and new
LaTeX. The runner copies the project, matches and applies the change, compiles the PDF,
and records the outcome. Uncertainty always results in an explicit failure rather than a
guess.
