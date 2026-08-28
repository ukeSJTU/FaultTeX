from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def latex_project(tmp_path: Path) -> Path:
    project = tmp_path / "paper"
    project.mkdir()
    (project / "main.tex").write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "The score is 10.\n"
        "A removable claim.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    return project


@pytest.fixture
def mutation_data() -> Callable[..., dict[str, Any]]:
    def make_mutation(
        *,
        change_type: str = "text.replace",
        old_text: str = "10",
        new_text: str = "20",
        file: str = "main.tex",
        entrypoint: str = "main.tex",
    ) -> dict[str, Any]:
        change: dict[str, Any]
        if change_type == "text.replace":
            change = {
                "type": change_type,
                "file": file,
                "before_context": "The score is ",
                "old_text": old_text,
                "new_text": new_text,
                "after_context": ".",
            }
        else:
            change = {
                "type": change_type,
                "file": file,
                "before_context": "The score is 10.\n",
                "text": "A removable claim.\n",
                "after_context": "\\end{document}",
            }
        return {
            "schema": 1,
            "entrypoint": entrypoint,
            "description": "A test mutation.",
            "label": "test_mutation",
            "change": change,
        }

    return make_mutation
