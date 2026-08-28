#!/usr/bin/env python3
"""Validate one or more mutation specs with the installed FaultTeX CLI."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Validate FaultTeX mutation specs without modifying or compiling the project.")
    )
    parser.add_argument("project", type=Path, help="Clean LaTeX project root.")
    parser.add_argument(
        "mutations",
        type=Path,
        help="One mutation YAML file or a directory containing mutation specs.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Discover YAML files recursively when MUTATIONS is a directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Write one machine-readable validation summary to stdout.",
    )
    return parser.parse_args()


def discover_mutations(path: Path, recursive: bool) -> tuple[Path, list[Path]]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"Mutation path does not exist: {path}") from exc

    if resolved.is_file():
        if resolved.suffix.lower() not in {".yaml", ".yml"}:
            raise ValueError(f"Mutation file must end in .yaml or .yml: {path}")
        return resolved.parent, [resolved]
    if not resolved.is_dir():
        raise ValueError(f"Mutation path is not a file or directory: {path}")

    candidates = resolved.rglob("*") if recursive else resolved.iterdir()
    mutations = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.is_file() and candidate.suffix.lower() in {".yaml", ".yml"}
        ),
        key=lambda candidate: candidate.relative_to(resolved).as_posix(),
    )
    if not mutations:
        raise ValueError(f"No mutation YAML files found in {path}")
    return resolved, mutations


def run_check(faulttex: str, project: Path, mutation: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [faulttex, "--quiet", "check", str(project), str(mutation), "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "stage": "tool",
            "error": "faulttex check exceeded the 30-second validation timeout.",
        }

    try:
        result: Any = json.loads(completed.stdout)
    except json.JSONDecodeError:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        return {
            "status": "failed",
            "stage": "tool",
            "error": f"faulttex check returned invalid JSON: {detail}",
        }

    if not isinstance(result, dict) or result.get("status") not in {"success", "failed"}:
        return {
            "status": "failed",
            "stage": "tool",
            "error": "faulttex check returned an unexpected JSON result.",
        }
    if completed.returncode not in {0, 1}:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        return {
            "status": "failed",
            "stage": "tool",
            "error": f"faulttex check failed unexpectedly: {detail}",
        }
    return result


def emit_human(summary: dict[str, Any]) -> None:
    for result in summary["mutations"]:
        if result["status"] == "success":
            print(f"OK    {result['mutation']}")
        else:
            print(
                f"FAIL  {result['mutation']} [{result.get('stage', 'unknown')}] "
                f"{result.get('error', 'validation failed')}"
            )
    print(
        f"Validated {summary['total']} mutation(s): "
        f"{summary['valid']} valid, {summary['invalid']} invalid"
    )


def main() -> int:
    args = parse_args()
    faulttex = shutil.which("faulttex")
    if faulttex is None:
        print(
            "faulttex is not available on PATH; install FaultTeX before validating specs.",
            file=sys.stderr,
        )
        return 3

    try:
        root, mutations = discover_mutations(args.mutations, args.recursive)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for mutation in mutations:
        result = run_check(faulttex, args.project, mutation)
        results.append(
            {
                "mutation": mutation.relative_to(root).as_posix(),
                **result,
            }
        )

    invalid = sum(result["status"] != "success" for result in results)
    summary: dict[str, Any] = {
        "status": "success" if invalid == 0 else "failed",
        "total": len(results),
        "valid": len(results) - invalid,
        "invalid": invalid,
        "mutations": results,
    }
    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        emit_human(summary)
    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
