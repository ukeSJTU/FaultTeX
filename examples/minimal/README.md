# Minimal FaultTeX Example

This example contains a compact scientific paper and three independent mutation specs.
The paper uses multiple source files, equations, an experimental table, an ablation
study, and a BibTeX bibliography. Every mutation targets the same clean project;
mutations must never be applied cumulatively.

The specs demonstrate the operations supported by schema 1:

- `mutations/replace-number.yaml` corrupts an accuracy in the abstract while leaving
  the result table unchanged.
- `mutations/reverse-conclusion.yaml` reverses the direction of the conclusion.
- `mutations/delete-claim.yaml` removes a claim from the ablation study.

Run these commands from the repository root:

```bash
uv run faulttex check \
  examples/minimal/project \
  examples/minimal/mutations/replace-number.yaml

uv run faulttex apply \
  examples/minimal/project \
  examples/minimal/mutations/replace-number.yaml \
  --output tmp/examples/minimal/replace-number

uv run faulttex batch \
  examples/minimal/project \
  examples/minimal/mutations \
  --output tmp/examples/minimal/batch
```

The example writes generated artifacts under `tmp/`, which the repository ignores.
Running `apply` or `batch` must leave `project/main.tex` unchanged.
