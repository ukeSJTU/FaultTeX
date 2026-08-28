from typing import Literal

FailureStage = Literal["schema", "file", "match", "apply", "compile", "output"]


class FaultTexError(Exception):
    """An expected FaultTeX failure with a stable result stage."""

    stage: FailureStage

    def __init__(self, stage: FailureStage, message: str) -> None:
        super().__init__(message)
        self.stage = stage
