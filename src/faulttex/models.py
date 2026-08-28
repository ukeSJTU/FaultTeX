from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(min_length=1)]


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)


class TextReplaceChange(StrictModel):
    type: Literal["text.replace"]
    file: NonEmptyString
    before_context: str
    old_text: NonEmptyString
    new_text: NonEmptyString
    after_context: str


class TextDeleteChange(StrictModel):
    type: Literal["text.delete"]
    file: NonEmptyString
    before_context: str
    text: NonEmptyString
    after_context: str


Change = Annotated[TextReplaceChange | TextDeleteChange, Field(discriminator="type")]


class MutationSpec(StrictModel):
    schema_version: Literal[1] = Field(alias="schema")
    entrypoint: NonEmptyString
    description: NonEmptyString
    label: NonEmptyString
    change: Change


class ArtifactPaths(StrictModel):
    pdf: str | None = None
    log: str | None = None
    source: str | None = None


class SuccessfulMutationResult(StrictModel):
    schema_version: Literal[1] = Field(default=1, alias="schema")
    status: Literal["success"] = "success"
    artifacts: ArtifactPaths


class FailedMutationResult(StrictModel):
    schema_version: Literal[1] = Field(default=1, alias="schema")
    status: Literal["failed"] = "failed"
    stage: Literal["schema", "file", "match", "apply", "compile", "output"]
    error: str
    artifacts: ArtifactPaths


MutationResult = SuccessfulMutationResult | FailedMutationResult


class BatchRunResult(StrictModel):
    id: str
    mutation: str
    result: str
    status: Literal["success", "failed"]


class BatchResult(StrictModel):
    schema_version: Literal[1] = Field(default=1, alias="schema")
    status: Literal["success", "partial_failure"]
    total: int
    succeeded: int
    failed: int
    runs: list[BatchRunResult]
