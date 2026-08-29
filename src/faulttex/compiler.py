import subprocess
from pathlib import Path
from typing import Protocol

from .errors import FaultTexError


class Compiler(Protocol):
    def compile(self, project: Path, entrypoint: Path, log_path: Path) -> Path: ...


class LatexmkCompiler:
    def compile(self, project: Path, entrypoint: Path, log_path: Path) -> Path:
        command = [
            "latexmk",
            "-pdf",
            "-synctex=1",
            "-interaction=nonstopmode",
            "-halt-on-error",
            entrypoint.as_posix(),
        ]
        try:
            with log_path.open("wb") as log_file:
                completed = subprocess.run(
                    command,
                    cwd=project,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
        except OSError as exc:
            raise FaultTexError("compile", f"Could not run latexmk: {exc}") from exc

        if completed.returncode != 0:
            raise FaultTexError(
                "compile",
                f"LaTeX compilation returned exit code {completed.returncode}.",
            )

        expected_pdf = project / entrypoint.with_suffix(".pdf")
        if not expected_pdf.is_file():
            raise FaultTexError(
                "compile",
                f"LaTeX compilation did not produce {entrypoint.with_suffix('.pdf')}.",
            )
        return expected_pdf
