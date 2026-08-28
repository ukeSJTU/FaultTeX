from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from faulttex.core import load_mutation
from faulttex.errors import FaultTexError
from faulttex.models import MutationSpec, TextDeleteChange, TextReplaceChange


def test_mutation_spec_parses_replace_discriminated_union(
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    spec = MutationSpec.model_validate(mutation_data())

    assert spec.schema_version == 1
    assert isinstance(spec.change, TextReplaceChange)
    assert spec.change.old_text == "10"


def test_mutation_spec_parses_delete_discriminated_union(
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    spec = MutationSpec.model_validate(mutation_data(change_type="text.delete"))

    assert isinstance(spec.change, TextDeleteChange)
    assert spec.change.text == "A removable claim.\n"


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema", "1"), ("entrypoint", ""), ("description", ""), ("label", "")],
)
def test_mutation_spec_rejects_invalid_top_level_values(
    mutation_data: Callable[..., dict[str, Any]], field: str, value: object
) -> None:
    data = mutation_data()
    data[field] = value

    with pytest.raises(ValidationError):
        MutationSpec.model_validate(data)


def test_mutation_spec_rejects_unknown_fields(
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    data = mutation_data()
    data["unknown"] = True

    with pytest.raises(ValidationError):
        MutationSpec.model_validate(data)


def test_load_mutation_reports_invalid_yaml_as_schema_failure(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("change: [", encoding="utf-8")

    with pytest.raises(FaultTexError, match="Invalid mutation YAML") as caught:
        load_mutation(path)

    assert caught.value.stage == "schema"


def test_load_mutation_uses_safe_yaml_and_validates_model(
    tmp_path: Path, mutation_data: Callable[..., dict[str, Any]]
) -> None:
    path = tmp_path / "mutation.yaml"
    path.write_text(yaml.safe_dump(mutation_data(), sort_keys=False), encoding="utf-8")

    spec = load_mutation(path)

    assert spec.entrypoint == "main.tex"
