"""Deterministic operator CLI over application-service boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from enum import IntEnum
from pathlib import Path

from pydantic import ValidationError

from pinn_strategy_system.domain_metrics import DomainProviderRegistry

from pinn_strategy_system.application import (
    ApplicationResult,
    McpDiagnosisApplicationService,
    OperationOutcome,
    OperatorApplicationService,
    OperatorCase,
    ProjectAdapterManifest,
    ProjectAdapterService,
    PostRunEvaluationService,
    RagApplicationService,
    SubprocessModelTransportFactory,
    load_execution_backend,
    load_post_run_contract,
)


class ExitCode(IntEnum):
    SUCCESS = 0
    NEEDS_INPUT = 2
    GATE_REJECTED = 3
    RUN_FAILED = 4
    INTERNAL_ERROR = 5


class CliInputError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliInputError("command-line arguments are invalid")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="pinn-strategy")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("audit", "plan"):
        command = commands.add_parser(name)
        _common_arguments(command)
        command.add_argument("--case", required=True)
    adapt = commands.add_parser("adapt")
    _common_arguments(adapt)
    adapt.add_argument("--manifest", required=True)
    adapt.add_argument("--output", required=True)
    diagnose = commands.add_parser("diagnose")
    _common_arguments(diagnose)
    diagnose.add_argument("--project-id", required=True)
    diagnose.add_argument("--query", required=True)
    diagnose.add_argument("--mcp-profile", required=True)
    diagnose.add_argument("--evidence", action="append", default=[])
    diagnose.add_argument("--anchor", action="append", default=[])
    diagnose.add_argument("--max-sections", type=int, default=5)
    evaluate = commands.add_parser("evaluate")
    _common_arguments(evaluate)
    evaluate.add_argument("--contract", required=True)
    for name in ("smoke", "full", "status", "replay"):
        command = commands.add_parser(name)
        _common_arguments(command)
        command.add_argument("--workflow", required=True)
    collect = commands.add_parser("collect")
    _common_arguments(collect)
    collect.add_argument("--workflow", required=True)
    collect.add_argument("--destination", required=True)
    rag = commands.add_parser("rag")
    rag_commands = rag.add_subparsers(dest="rag_command", required=True)
    rebuild = rag_commands.add_parser("rebuild")
    _common_arguments(rebuild)
    rebuild.add_argument("--source", required=True)
    rebuild.add_argument("--case", required=True)
    rebuild.add_argument("--model-profile", required=True)
    query = rag_commands.add_parser("query")
    _common_arguments(query)
    query.add_argument("--case", required=True)
    query.add_argument("--model-profile", required=True)
    query.add_argument("--query", required=True)
    return parser


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--base-directory")
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    arguments: argparse.Namespace | None = None
    try:
        arguments = build_parser().parse_args(argv)
        runtime_root = _runtime_root(arguments.runtime_root)
        base_directory = _base_directory(arguments.base_directory)
        result = _dispatch(arguments, runtime_root, base_directory)
    except (CliInputError, ValidationError, json.JSONDecodeError) as error:
        result = _safe_error_result(
            command=_command_label(arguments),
            outcome=OperationOutcome.GATE_REJECTED,
            code="INPUT_INVALID",
            message="Operator input failed contract validation.",
            error=error,
        )
    except (OSError, ValueError, KeyError) as error:
        is_run = _command_label(arguments) in {
            "smoke",
            "full",
            "status",
            "replay",
            "collect",
            "diagnose",
            "evaluate",
            "rag rebuild",
            "rag query",
        }
        result = _safe_error_result(
            command=_command_label(arguments),
            outcome=(
                OperationOutcome.RUN_FAILED
                if is_run
                else OperationOutcome.GATE_REJECTED
            ),
            code="OPERATION_FAILED" if is_run else "INPUT_INVALID",
            message=(
                "The governed operation failed without exposing runtime details."
                if is_run
                else "Operator input could not be loaded."
            ),
            error=error,
        )
    except Exception as error:
        result = _safe_error_result(
            command=_command_label(arguments),
            outcome=OperationOutcome.INTERNAL_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred; sensitive details were suppressed.",
            error=error,
        )
    _render(result, json_output=bool(arguments and arguments.json))
    return int(_exit_code(result.outcome))


def _dispatch(
    arguments: argparse.Namespace,
    runtime_root: Path,
    base_directory: Path | None,
) -> ApplicationResult:
    if arguments.command in {"audit", "plan"}:
        case_path = _input_file(arguments.case, base_directory)
        case = _load_case(case_path)
        service = OperatorApplicationService(
            runtime_root=runtime_root,
            backend_factory=load_execution_backend,
        )
        operation = service.audit if arguments.command == "audit" else service.plan
        return operation(case=case, case_path=case_path)
    if arguments.command == "adapt":
        manifest_path = _input_file(arguments.manifest, base_directory)
        output_path = _output_file(arguments.output, base_directory)
        manifest = _load_project_manifest(manifest_path)
        report = ProjectAdapterService(
            artifact_root=runtime_root / "artifacts" / "project-adapter"
        ).adapt(manifest=manifest, output_path=output_path)
        has_unresolved = bool(report.unresolved)
        return ApplicationResult(
            command="adapt",
            outcome=(
                OperationOutcome.NEEDS_INPUT
                if has_unresolved
                else OperationOutcome.SUCCESS
            ),
            code=(
                "ADAPTED_WITH_UNRESOLVED" if has_unresolved else "ADAPTED"
            ),
            message=(
                "Project governance case was created with unresolved user inputs."
                if has_unresolved
                else "Project governance case was created."
            ),
            workflow_id=report.case.request.workflow_id,
            data={
                "case_path": str(report.output_path),
                "source_snapshot_ref": report.source_snapshot_ref.model_dump(
                    mode="json"
                ),
                "files": [item.model_dump(mode="json") for item in report.files],
                "unresolved": list(report.unresolved),
            },
        )
    if arguments.command == "diagnose":
        profile_path = _input_file(arguments.mcp_profile, base_directory)
        return McpDiagnosisApplicationService().diagnose(
            project_id=arguments.project_id,
            query=arguments.query,
            profile_path=profile_path,
            evidence=tuple(arguments.evidence),
            anchors=tuple(arguments.anchor),
            max_sections=arguments.max_sections,
        )
    if arguments.command == "evaluate":
        contract_path = _input_file(arguments.contract, base_directory)
        contract = load_post_run_contract(contract_path)
        return PostRunEvaluationService(
            artifact_root=runtime_root / "artifacts" / "evaluations",
            provider_registry=DomainProviderRegistry(()),
        ).evaluate(contract)
    if arguments.command in {"smoke", "full", "status", "replay"}:
        service = OperatorApplicationService(
            runtime_root=runtime_root,
            backend_factory=load_execution_backend,
        )
        operation = getattr(service, arguments.command)
        return operation(arguments.workflow)
    if arguments.command == "collect":
        service = OperatorApplicationService(
            runtime_root=runtime_root,
            backend_factory=load_execution_backend,
        )
        destination = _output_directory(
            arguments.destination,
            base_directory,
        )
        return service.collect(arguments.workflow, destination)
    if arguments.command == "rag":
        case_path = _input_file(arguments.case, base_directory)
        profile_path = _input_file(arguments.model_profile, base_directory)
        case = _load_case(case_path)
        service = RagApplicationService(
            runtime_root=runtime_root,
            transport_factory=SubprocessModelTransportFactory(profile_path),
        )
        if arguments.rag_command == "rebuild":
            source_root = _input_directory(arguments.source, base_directory)
            return service.rebuild(source_root=source_root, case=case)
        return service.query(case=case, query=arguments.query)
    raise CliInputError("unsupported command")


def _load_case(path: Path) -> OperatorCase:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise CliInputError("operator case exceeds the 4 MiB limit")
    try:
        return OperatorCase.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise CliInputError("operator case is invalid") from error


def _load_project_manifest(path: Path) -> ProjectAdapterManifest:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise CliInputError("project adapter manifest exceeds the 4 MiB limit")
    try:
        return ProjectAdapterManifest.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise CliInputError("project adapter manifest is invalid") from error


def _runtime_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise CliInputError("runtime root must be absolute")
    return path.resolve(strict=False)


def _base_directory(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise CliInputError("base directory must be an existing absolute directory")
    return path.resolve(strict=True)


def _input_file(value: str, base_directory: Path | None) -> Path:
    path = _explicit_path(value, base_directory)
    if not path.is_file():
        raise CliInputError("input file does not exist")
    return path.resolve(strict=True)


def _input_directory(value: str, base_directory: Path | None) -> Path:
    path = _explicit_path(value, base_directory)
    if not path.is_dir():
        raise CliInputError("input directory does not exist")
    return path.resolve(strict=True)


def _output_file(value: str, base_directory: Path | None) -> Path:
    path = _explicit_path(value, base_directory)
    if not path.is_absolute() or not path.parent.is_dir():
        raise CliInputError("output parent must be an existing absolute directory")
    return path.resolve(strict=False)


def _output_directory(value: str, base_directory: Path | None) -> Path:
    path = _explicit_path(value, base_directory)
    if not path.is_absolute() or not path.parent.is_dir():
        raise CliInputError(
            "output directory parent must be an existing absolute directory"
        )
    return path.resolve(strict=False)


def _explicit_path(value: str, base_directory: Path | None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if base_directory is None:
        raise CliInputError("relative input paths require --base-directory")
    return base_directory / path


def _command_label(arguments: argparse.Namespace | None) -> str:
    if arguments is None or not getattr(arguments, "command", None):
        return "cli"
    if arguments.command == "rag":
        subcommand = getattr(arguments, "rag_command", "unknown")
        return f"rag {subcommand}"
    return arguments.command


def _safe_error_result(
    *,
    command: str,
    outcome: OperationOutcome,
    code: str,
    message: str,
    error: Exception,
) -> ApplicationResult:
    return ApplicationResult(
        command=command,
        outcome=outcome,
        code=code,
        message=message,
        data={"error_type": type(error).__name__},
    )


def _render(result: ApplicationResult, *, json_output: bool) -> None:
    if json_output:
        print(result.model_dump_json())
        return
    location = ""
    if result.workflow_id is not None:
        location += f" workflow={result.workflow_id}"
    if result.stage is not None:
        location += f" stage={result.stage}"
    print(
        f"[{result.outcome.value}] {result.command}{location}: "
        f"{result.message}"
    )


def _exit_code(outcome: OperationOutcome) -> ExitCode:
    return {
        OperationOutcome.SUCCESS: ExitCode.SUCCESS,
        OperationOutcome.NEEDS_INPUT: ExitCode.NEEDS_INPUT,
        OperationOutcome.GATE_REJECTED: ExitCode.GATE_REJECTED,
        OperationOutcome.RUN_FAILED: ExitCode.RUN_FAILED,
        OperationOutcome.INTERNAL_ERROR: ExitCode.INTERNAL_ERROR,
    }[outcome]


if __name__ == "__main__":
    raise SystemExit(main())
