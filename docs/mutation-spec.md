# Mutation Spec

This document defines the FaultTeX mutation schema used by FaultTeX v0.1. A mutation
spec is a YAML file containing one independent mutation and exactly one source change.
It is the interface between a human or automated Mutation Author and the Mutation
Runner.

For product-level constraints, see [design.md](design.md). For execution behavior, see
[runner.md](runner.md).

## Why YAML

FaultTeX uses YAML for mutation specs because mutation fields often contain multiline
LaTeX source. Execution results are program-generated JSON as described in
[cli-and-results.md](cli-and-results.md).

JSON requires escaping LaTeX backslashes and newlines:

```json
{
  "old_text": "The first line.\nThe accuracy is $94.2\\%$."
}
```

YAML can preserve the source directly:

```yaml
old_text: |-
  The first line.
  The accuracy is $94.2\%$.
```

YAML also allows researchers to add comments:

```yaml
# This mutation changes the main abstract conclusion.
label: claim_evidence_mismatch
```

## YAML Conventions

Fields used for exact matching or replacement must use a literal block:

```yaml
old_text: |-
  Exact LaTeX source here.
```

They must not use a folded block:

```yaml
old_text: >
  Exact LaTeX source here.
```

The `>` form can fold line breaks and therefore change the string being matched.

Implementations must use a safe YAML parser, such as:

```python
yaml.safe_load(...)
```

## Complete Structure

A complete replacement mutation has this structure:

```yaml
schema: 1
id: abstract_claim_direction_001

entrypoint: main.tex

description: >
  修改摘要中的主要 claim，使其与实验章节中的 evidence 矛盾。

label: claim_evidence_mismatch

change:
  type: text.replace
  file: main.tex

  before_context: |-
    Our experimental results demonstrate that

  old_text: |-
    the proposed method significantly improves classification accuracy

  new_text: |-
    the proposed method significantly reduces classification accuracy

  after_context: |-
    on all benchmark datasets.
```

The top-level fields defined by schema 1 are `schema`, `id`, `entrypoint`, `description`,
`label`, and `change`.

Schema 1 deliberately has no `rendered_text` field. After compilation, FaultTeX derives
the visible replacement text or deletion anchors conservatively from the existing raw
LaTeX fields and combines them with SyncTeX. If that mapping is unsupported or ambiguous,
annotation fails explicitly. A future schema version may add `rendered_text` and rendered
before/after contexts for macro-heavy source without changing schema 1 matching semantics.

## Top-Level Fields

### `schema`

```yaml
schema: 1
```

This identifies FaultTeX mutation schema 1. The v0.1 runner accepts only the integer
value `1`; any other value is a schema validation failure.

### `id`

```yaml
id: abstract_claim_direction_001
```

`id` is the stable identity of one mutation within the clean LaTeX project it targets.
It must be unique among mutations executed together for that project. Moving or renaming
the YAML file does not change the mutation ID.

Schema 1 IDs contain 1 to 64 lowercase ASCII letters, digits, underscores, or hyphens,
and begin with a letter or digit. This makes an ID safe to use as a batch artifact
directory name. The runner does not derive an ID from the filename, `label`, mutation
content, or batch position.

### `entrypoint`

```yaml
entrypoint: main.tex
```

`entrypoint` is the main `.tex` file that the runner compiles after applying the change.
It is required so that a LaTeX project and one mutation spec fully define a mutation
run. The path is relative to the project root, must remain inside the project, and must
refer to an existing file.

`entrypoint` is a top-level field rather than part of `change`: it describes how to
compile the mutated project, while `change.file` identifies the source file to edit.

### `description`

```yaml
description: >
  修改摘要中的主要 claim，使其与实验章节中的 evidence 矛盾。
```

`description` is a natural-language explanation for people and agents. It should
describe the target, the reason for the change, its intended defect, and how the
claim--evidence relationship changes. It does not participate in execution.

### `label`

```yaml
label: claim_evidence_mismatch
```

`label` is a short machine-readable semantic category. Schema 1 does not enforce a
fixed label enumeration, but lowercase `snake_case` is recommended. Examples include:

```text
claim_evidence_mismatch
claim_contradiction
evidence_corruption
claim_omission
evidence_omission
number_corruption
entity_substitution
direction_flip
abstract_body_mismatch
conclusion_result_mismatch
```

The label describes the effect of a mutation, while `change.type` describes how the
runner edits the source. For example, `label: number_corruption` can be implemented with
`type: text.replace`.

### `change`

`change` describes the mutation's only source modification. Schema 1 supports:

```text
text.replace
text.delete
```

## `text.replace`

### Format

```yaml
change:
  type: text.replace
  file: sections/experiments.tex

  before_context: |-
    On the primary evaluation dataset,

  old_text: |-
    our model achieves an accuracy of $94.2\%$

  new_text: |-
    our model achieves an accuracy of $84.2\%$

  after_context: |-
    and outperforms the strongest baseline by $4.8\%$.
```

### Fields

`file` is the target path relative to the LaTeX project root. The runner does not search
the whole project for `old_text`; the author must identify the file explicitly. Path
safety is specified in [runner.md](runner.md).

`before_context` is exact source immediately to the left of the target. It is used for
location and is not modified.

`old_text` is the exact source to replace and must be nonempty.

`new_text` is the exact replacement source and must be nonempty for `text.replace`. Use
`text.delete` to remove text.

`after_context` is exact source immediately to the right of the target. It is used for
location and is not modified.

### Matching and Replacement

The runner constructs:

```python
needle = before_context + old_text + after_context
```

The mutation is valid for application only when `needle` occurs exactly once in the
target file:

```text
count == 1  → apply
count == 0  → fail
count > 1   → fail
```

It then constructs:

```python
replacement = before_context + new_text + after_context
```

and performs one replacement:

```python
mutated_source = source.replace(needle, replacement, 1)
```

Only `old_text` changes. The before and after context remain intact.

`old_text` is required even though the surrounding context might sometimes identify a
region by itself. Without it, unexpectedly large or changed content between two anchors
could be replaced silently. The target text is both location information and a safety
check.

For example, given:

```latex
Results show that
the proposed model improves accuracy.
This effect is statistically significant.
The improvement is consistent
on all datasets.
```

using only `Results show that` and `on all datasets.` as anchors could replace several
unexpected sentences. Requiring the exact `old_text` makes the intended content an
explicit part of validation.

## `text.delete`

### Format

```yaml
schema: 1
id: delete_abstract_claim_001

entrypoint: main.tex

description: >
  删除摘要中报告主要实验结果的 claim。

label: claim_omission

change:
  type: text.delete
  file: main.tex

  before_context: |-
    We evaluate the proposed approach on three benchmark datasets.

  text: |-
    Our method outperforms all previous baselines.

  after_context: |-
    We additionally conduct extensive ablation experiments.
```

### Fields and Algorithm

`text.delete` uses `file`, `before_context`, `text`, and `after_context`. The `text` field
is the exact nonempty source to remove.

The runner constructs:

```python
needle = before_context + text + after_context
```

The complete `needle` must occur exactly once. The replacement is:

```python
replacement = before_context + after_context
```

and the runner applies:

```python
mutated_source = source.replace(needle, replacement, 1)
```

FaultTeX v0.1 does not clean up double spaces, extra blank lines, indentation, punctuation,
or paragraph joins created by deletion. The author must choose the `text` boundary so
that the remaining LaTeX is appropriate. A newline that must disappear should be part of
`text`.

## Exact Context Matching

### Purpose of Context

`before_context` and `after_context` ensure that a mutation applies at its intended
location. A phrase such as:

```latex
our method significantly improves performance
```

may occur many times, while this complete combination may be unique:

```text
Compared with the strongest baseline,
+
our method significantly improves performance
+
on the biomedical relation extraction benchmark.
```

### Context Length

FaultTeX does not prescribe a character, word, or sentence count for context. The only
criterion is that the concatenation of before context, target text, and after context
occurs exactly once in the specified file.

### LaTeX in Context

Context can contain arbitrary raw LaTeX, including:

```latex
Section~\ref{sec:experiments}
\textbf{Main results.}
Table~\ref{tab:results}
$94.2\%$
```

FaultTeX does not parse these constructs.

### Whitespace Is Significant

These strings are different under exact matching:

```latex
our method improves accuracy
```

```latex
our  method improves accuracy
```

```latex
our method
improves accuracy
```

Authors must copy source directly and preserve spaces, line breaks, indentation, and
LaTeX escape characters. FaultTeX v0.1 performs no whitespace normalization.

## Authoring Mutations

FaultTeX treats an agent as a producer of mutation specs, not as part of the runner. An
agent may receive a LaTeX project, a natural-language mutation goal, and a requested
mutation count. For example:

> Read the paper's LaTeX source, find ten claim--evidence pairs, and modify only one side
> of each pair so that they conflict or no longer match. Produce one FaultTeX mutation
> YAML file for each mutation.

The expected output is a set of independent YAML files. Every file declares its own
project-scoped `id`. Filenames and directories are chosen by the caller and carry no
identity or execution semantics.

An agent should:

1. Read the main file and files introduced through `\input` and `\include`.
2. Assign an ID that is unique within the clean paper project.
3. Set `entrypoint` to the project-relative main `.tex` file.
4. Identify candidate claims and their evidence.
5. Decide whether to modify the claim or the evidence.
6. Produce semantically plausible and syntactically valid replacement LaTeX.
7. Copy exact before, target, and after source from the target file.
8. Verify that the complete `needle` occurs exactly once in that file.
9. Generate one mutation per YAML file.

An agent must not:

- Substitute text extracted from a PDF for LaTeX source.
- Modify the original project directly.
- Emit line numbers, offsets, or occurrence indexes as target locations.
- Omit the target file.
- Use ellipses to represent skipped source.
- Transcribe LaTeX approximately.

For example, this is invalid unless the literal characters `...` appear in the source:

```yaml
old_text: |-
  Our method ... improves performance.
```

The author must provide complete source that the runner can match exactly. The proposed
`faulttex check` command provides a fast validation path without modifying or compiling
the project; see [cli-and-results.md](cli-and-results.md).

## Examples

### Reverse a Claim's Direction

```yaml
schema: 1
id: reverse_abstract_claim_001

entrypoint: main.tex

description: >
  将摘要中的性能提升 claim 修改为性能下降，
  使其与实验结果中的 evidence 矛盾。

label: claim_evidence_mismatch

change:
  type: text.replace
  file: main.tex

  before_context: |-
    Extensive experiments demonstrate that

  old_text: |-
    our approach consistently outperforms existing methods

  new_text: |-
    our approach consistently underperforms existing methods

  after_context: |-
    across all evaluated benchmarks.
```

### Corrupt a Number in Evidence

```yaml
schema: 1
id: corrupt_results_accuracy_001

entrypoint: main.tex

description: >
  保留摘要中的性能提升 claim，但降低结果章节中的实验数值，
  使 evidence 不再支持原 claim。

label: evidence_corruption

change:
  type: text.replace
  file: sections/experiments.tex

  before_context: |-
    As reported in Table~\ref{tab:main-results},

  old_text: |-
    FaultTeX achieves an average accuracy of $94.2\%$

  new_text: |-
    FaultTeX achieves an average accuracy of $74.2\%$

  after_context: |-
    across the three evaluation datasets.
```

### Change Statistical Significance

```yaml
schema: 1
id: change_significance_001

entrypoint: main.tex

description: >
  将具有统计显著性的结果修改为不具有统计显著性，
  但保留正文中的正面结论。

label: statistical_evidence_corruption

change:
  type: text.replace
  file: sections/results.tex

  before_context: |-
    The improvement over the baseline is

  old_text: |-
    statistically significant with $p < 0.01$

  new_text: |-
    not statistically significant with $p > 0.05$

  after_context: |-
    under the paired bootstrap test.
```

### Delete a Main Abstract Result

```yaml
schema: 1
id: delete_abstract_result_001

entrypoint: main.tex

description: >
  删除摘要中报告主要实验结果的句子。

label: claim_omission

change:
  type: text.delete
  file: main.tex

  before_context: |-
    We evaluate the proposed framework on three public benchmarks.

  text: |-
    The proposed framework outperforms all previous approaches.

  after_context: |-
    We release our implementation and evaluation data.
```

### Delete Supporting Evidence

```yaml
schema: 1
id: delete_supporting_evidence_001

entrypoint: main.tex

description: >
  删除结果章节中直接支持摘要 claim 的 evidence，
  使该 claim 在论文中缺少明确支持。

label: evidence_omission

change:
  type: text.delete
  file: sections/results.tex

  before_context: |-
    The full results are shown in Table~\ref{tab:results}.

  text: |-
    Our model improves F1 score by $6.3$ points over the strongest baseline.

  after_context: |-
    We next investigate the contribution of individual components.
```
