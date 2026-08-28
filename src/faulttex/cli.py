import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, NoReturn

import structlog
import typer

from .core import inspect_mutation, load_mutation
from .errors import FaultTexError
from .models import BatchResult, BatchRunResult, FailedMutationResult
from .runner import RESULT_NAME, run_mutation, write_json_model

app = typer.Typer(
    name="faulttex",
    help="Controlled fault injection for scientific papers written in LaTeX.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)
logger = structlog.get_logger("faulttex")


@dataclass(frozen=True, slots=True)
class CliState:
    verbose: bool
    quiet: bool


def _package_version() -> str:
    try:
        return version("faulttex")
    except PackageNotFoundError:
        return "0+unknown"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_package_version())
        raise typer.Exit()


def _configure_logging(verbose: bool) -> None:
    minimum_level = logging.DEBUG if verbose else logging.CRITICAL
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.KeyValueRenderer(key_order=["event", "level"]),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(minimum_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


@app.callback()
def root(
    ctx: typer.Context,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show additional execution detail."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress progress and success summaries."),
    ] = False,
    version_option: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the FaultTeX version and exit.",
        ),
    ] = False,
) -> None:
    del version_option
    if verbose and quiet:
        raise typer.BadParameter("--verbose and --quiet are mutually exclusive")
    _configure_logging(verbose)
    ctx.obj = CliState(verbose=verbose, quiet=quiet)


def _state(ctx: typer.Context) -> CliState:
    if isinstance(ctx.obj, CliState):
        return ctx.obj
    return CliState(verbose=False, quiet=False)


def _emit_internal_error(exc: Exception) -> NoReturn:
    typer.echo(f"Internal error: {exc}", err=True)
    raise typer.Exit(code=3) from exc


def _emit_domain_error(exc: FaultTexError) -> NoReturn:
    typer.echo(f"{exc.stage}: {exc}", err=True)
    raise typer.Exit(code=1) from exc


@app.command("check")
def check_command(
    ctx: typer.Context,
    project: Annotated[Path, typer.Argument(help="Clean LaTeX project root.")],
    mutation: Annotated[Path, typer.Argument(help="Mutation YAML file.")],
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Write a machine-readable result to stdout."),
    ] = False,
) -> None:
    """Validate a mutation and its unique target without modifying or compiling."""
    state = _state(ctx)
    logger.debug("check_started", project=str(project), mutation=str(mutation))
    try:
        spec = load_mutation(mutation)
        inspection = inspect_mutation(project, spec)
    except FaultTexError as exc:
        if as_json:
            typer.echo(
                json.dumps(
                    {"status": "failed", "stage": exc.stage, "error": str(exc)},
                    ensure_ascii=False,
                )
            )
            raise typer.Exit(code=1) from exc
        _emit_domain_error(exc)
    except Exception as exc:
        _emit_internal_error(exc)

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "status": "success",
                    "file": inspection.target_relative.as_posix(),
                    "occurrences": inspection.occurrences,
                },
                ensure_ascii=False,
            )
        )
    elif not state.quiet:
        typer.echo(f"OK: target occurs exactly once in {inspection.target_relative.as_posix()}")
    logger.debug("check_finished", status="success")


@app.command("apply")
def apply_command(
    ctx: typer.Context,
    project: Annotated[Path, typer.Argument(help="Clean LaTeX project root.")],
    mutation: Annotated[Path, typer.Argument(help="Mutation YAML file.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Artifact directory for this run."),
    ],
    keep_source: Annotated[
        bool,
        typer.Option("--keep-source", help="Retain the mutated project copy."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace existing FaultTeX artifacts."),
    ] = False,
) -> None:
    """Apply one mutation, compile the project, and write result artifacts."""
    state = _state(ctx)
    logger.debug(
        "apply_started",
        project=str(project),
        mutation=str(mutation),
        output=str(output),
    )
    try:
        result = run_mutation(
            project,
            mutation,
            output,
            keep_source=keep_source,
            overwrite=overwrite,
        )
    except FaultTexError as exc:
        _emit_domain_error(exc)
    except Exception as exc:
        _emit_internal_error(exc)

    if isinstance(result, FailedMutationResult):
        logger.debug("apply_finished", status="failed", stage=result.stage)
        typer.echo(f"{result.stage}: {result.error}", err=True)
        raise typer.Exit(code=1)
    logger.debug("apply_finished", status="success", pdf=result.artifacts.pdf)
    if not state.quiet:
        typer.echo(f"success: {output / (result.artifacts.pdf or '')}")


def discover_mutations(directory: Path, recursive: bool) -> list[Path]:
    try:
        root = directory.resolve(strict=True)
    except OSError as exc:
        raise FaultTexError("file", f"Mutation directory does not exist: {directory}") from exc
    if not root.is_dir():
        raise FaultTexError("file", f"Mutation path is not a directory: {directory}")

    candidates = root.rglob("*") if recursive else root.iterdir()
    mutations = [
        path for path in candidates if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
    ]
    mutations.sort(key=lambda path: path.relative_to(root).as_posix())
    if not mutations:
        raise FaultTexError("file", f"No mutation YAML files found in {directory}")
    return mutations


def _prepare_batch_output(output: Path, overwrite: bool) -> Path:
    resolved = output.resolve()
    try:
        if resolved.exists() and not resolved.is_dir():
            raise FaultTexError("output", f"Batch output is not a directory: {output}")
        if resolved.exists() and any(resolved.iterdir()) and not overwrite:
            raise FaultTexError("output", f"Batch output is not empty; use --overwrite: {output}")
        resolved.mkdir(parents=True, exist_ok=True)
        if overwrite:
            aggregate = resolved / "batch-result.json"
            aggregate.unlink(missing_ok=True)
            for child in resolved.iterdir():
                if child.is_dir() and re.fullmatch(r"\d{6}", child.name):
                    shutil.rmtree(child)
    except FaultTexError:
        raise
    except OSError as exc:
        raise FaultTexError("output", f"Could not prepare batch output {output}: {exc}") from exc
    return resolved


@app.command("batch")
def batch_command(
    ctx: typer.Context,
    project: Annotated[Path, typer.Argument(help="Clean LaTeX project root.")],
    mutations_dir: Annotated[Path, typer.Argument(help="Directory of mutation YAML files.")],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Root directory for batch artifacts."),
    ],
    recursive: Annotated[
        bool,
        typer.Option("--recursive", help="Discover mutation YAML recursively."),
    ] = False,
    keep_source: Annotated[
        bool,
        typer.Option("--keep-source", help="Retain every mutated project copy."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace existing FaultTeX batch artifacts."),
    ] = False,
) -> None:
    """Apply every discovered mutation independently to the same clean project."""
    state = _state(ctx)
    try:
        mutation_root = mutations_dir.resolve(strict=True)
        mutations = discover_mutations(mutation_root, recursive)
        output_root = _prepare_batch_output(output, overwrite)
    except FaultTexError as exc:
        _emit_domain_error(exc)
    except Exception as exc:
        _emit_internal_error(exc)

    runs: list[BatchRunResult] = []
    succeeded = 0
    failed = 0

    def process(index: int, mutation: Path) -> None:
        nonlocal succeeded, failed
        run_id = f"{index:06d}"
        relative_mutation = mutation.relative_to(mutation_root).as_posix()
        if state.verbose:
            logger.debug("batch_item_started", run_id=run_id, mutation=relative_mutation)
        result = run_mutation(
            project,
            mutation,
            output_root / run_id,
            keep_source=keep_source,
            overwrite=False,
        )
        if isinstance(result, FailedMutationResult):
            failed += 1
            status = "failed"
        else:
            succeeded += 1
            status = "success"
        runs.append(
            BatchRunResult(
                id=run_id,
                mutation=relative_mutation,
                result=f"{run_id}/{RESULT_NAME}",
                status=status,
            )
        )
        if state.verbose:
            logger.debug("batch_item_finished", run_id=run_id, status=status)

    try:
        if state.quiet:
            for index, mutation in enumerate(mutations, start=1):
                process(index, mutation)
        else:
            with typer.progressbar(
                mutations,
                label="FaultTeX success=0 failed=0",
                show_pos=True,
                show_eta=True,
                item_show_func=(
                    lambda item: (
                        item.relative_to(mutation_root).as_posix() if item is not None else ""
                    )
                ),
                file=sys.stderr,
            ) as progress:
                for index, mutation in enumerate(progress, start=1):
                    process(index, mutation)
                    progress.label = f"FaultTeX success={succeeded} failed={failed}"
    except FaultTexError as exc:
        _emit_domain_error(exc)
    except Exception as exc:
        _emit_internal_error(exc)

    aggregate = BatchResult(
        status="success" if failed == 0 else "partial_failure",
        total=len(runs),
        succeeded=succeeded,
        failed=failed,
        runs=runs,
    )
    try:
        write_json_model(output_root / "batch-result.json", aggregate)
    except FaultTexError as exc:
        _emit_domain_error(exc)

    if not state.quiet:
        typer.echo(
            f"completed: total={len(runs)} success={succeeded} failed={failed}",
            err=True,
        )
    if failed:
        raise typer.Exit(code=1)


def main() -> None:
    app(prog_name="faulttex")
