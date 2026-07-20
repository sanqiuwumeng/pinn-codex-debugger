"""Artifact-driven post-run analysis, decision and evidence persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Self

import numpy as np
from pydantic import Field, JsonValue, model_validator

from pinn_strategy_system.assurance import MetricDecisionService
from pinn_strategy_system.contracts import (
    ArtifactRef,
    DecisionRecord,
    DecisionStatus,
    MetricContract,
    MetricValueSet,
    PredictionAnalysisReport,
    PredictionComparisonReport,
    ResultStatus,
    VersionedModel,
)
from pinn_strategy_system.domain_metrics import DomainProviderRegistry
from pinn_strategy_system.execution import FieldData, PredictionAnalyzer
from pinn_strategy_system.storage import LocalArtifactStore

from .contracts import ApplicationResult, OperationOutcome


class FieldArtifactDescriptor(VersionedModel):
    artifact_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    values_key: str = Field(min_length=1, max_length=256)
    axes: tuple[str, ...] = Field(min_length=1)
    coordinate_keys: dict[str, str]
    context_field_keys: dict[str, str] = Field(default_factory=dict)
    roi_mask_keys: dict[str, str] = Field(default_factory=dict)
    reference_identity: str = Field(min_length=1, max_length=512)
    unit: str = Field(min_length=1, max_length=128)
    coordinate_system: str = Field(min_length=1, max_length=256)
    normalization: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def path_and_axes_are_explicit(self) -> Self:
        if not self.path.is_absolute():
            raise ValueError("field artifact path must be absolute")
        if self.path.suffix.casefold() != ".npz":
            raise ValueError("field artifacts must use the NPZ contract")
        if len(set(self.axes)) != len(self.axes):
            raise ValueError("field axes must be unique")
        if set(self.coordinate_keys) != set(self.axes):
            raise ValueError("coordinate_keys must identify every axis exactly")
        return self


class PostRunEvaluationContract(VersionedModel):
    evaluation_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    )
    workflow_id: str = Field(min_length=1, max_length=256)
    run_id: str = Field(min_length=1, max_length=256)
    observed_failure_mechanism: str = Field(min_length=1, max_length=4096)
    baseline: FieldArtifactDescriptor
    candidate: FieldArtifactDescriptor
    reference: FieldArtifactDescriptor
    metric_contract: MetricContract
    domain_provider_ids: tuple[str, ...] = ()
    top_k: int = Field(default=10, ge=1, le=100)
    percentiles: tuple[float, ...] = (50.0, 90.0, 95.0, 99.0)
    connected_percentile: float = Field(default=95.0, ge=0, le=100)

    @model_validator(mode="after")
    def artifact_roles_are_distinct(self) -> Self:
        ids = (
            self.baseline.artifact_id,
            self.candidate.artifact_id,
            self.reference.artifact_id,
        )
        if len(set(ids)) != len(ids):
            raise ValueError("baseline, candidate and reference artifact ids must differ")
        if len(set(self.domain_provider_ids)) != len(self.domain_provider_ids):
            raise ValueError("domain provider ids must be unique")
        return self


class EvaluationEvidenceCandidate(VersionedModel):
    candidate_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
    )
    workflow_id: str = Field(min_length=1, max_length=256)
    run_id: str = Field(min_length=1, max_length=256)
    comparison_ref: ArtifactRef
    decision_ref: ArtifactRef
    comparison_status: ResultStatus
    decision_status: DecisionStatus
    baseline_max_abs: dict[str, JsonValue] | None = None
    candidate_max_abs: dict[str, JsonValue] | None = None
    ready_for_run_validation: bool = False
    knowledge_promotion_allowed: bool = False
    human_approval_required: bool = True

    @model_validator(mode="after")
    def cannot_publish_directly(self) -> Self:
        if self.knowledge_promotion_allowed:
            raise ValueError("post-run evidence cannot directly authorize promotion")
        if not self.human_approval_required:
            raise ValueError("post-run evidence always requires human review")
        return self


class PostRunEvaluationService:
    def __init__(
        self,
        *,
        artifact_root: Path,
        provider_registry: DomainProviderRegistry,
    ) -> None:
        if not artifact_root.is_absolute():
            raise ValueError("evaluation artifact root must be absolute")
        artifact_root.mkdir(parents=True, exist_ok=True)
        self._artifacts = LocalArtifactStore(artifact_root)
        self._providers = provider_registry
        self._analyzer = PredictionAnalyzer()
        self._decisions = MetricDecisionService()

    def evaluate(self, contract: PostRunEvaluationContract) -> ApplicationResult:
        baseline, _ = _load_field(contract.baseline)
        candidate, _ = _load_field(contract.candidate)
        reference, roi_masks = _load_field(contract.reference)
        providers = self._providers.select(contract.domain_provider_ids)
        comparison = self._analyzer.compare(
            report_id=f"comparison-{contract.evaluation_id}",
            baseline=baseline,
            candidate=candidate,
            reference=reference,
            top_k=contract.top_k,
            percentiles=contract.percentiles,
            connected_percentile=contract.connected_percentile,
            roi_masks=roi_masks,
            domain_metric_providers=providers,
        )
        decision = self._decisions.compare(
            decision_id=f"decision-{contract.evaluation_id}",
            contract=contract.metric_contract,
            baseline=MetricValueSet(
                subject_id=contract.baseline.artifact_id,
                values=_metric_values(comparison.baseline_report),
            ),
            candidate=MetricValueSet(
                subject_id=contract.candidate.artifact_id,
                values=_metric_values(comparison.candidate_report),
            ),
            observed_failure_mechanism=contract.observed_failure_mechanism,
        )
        comparison_ref = self._artifacts.put_json(
            f"{contract.evaluation_id}-comparison",
            comparison.model_dump(mode="json"),
        )
        decision_ref = self._artifacts.put_json(
            f"{contract.evaluation_id}-decision",
            decision.model_dump(mode="json"),
        )
        evidence = EvaluationEvidenceCandidate(
            candidate_id=f"{contract.evaluation_id}-evidence",
            workflow_id=contract.workflow_id,
            run_id=contract.run_id,
            comparison_ref=comparison_ref,
            decision_ref=decision_ref,
            comparison_status=comparison.status,
            decision_status=decision.status,
            baseline_max_abs=_localized_payload(comparison.baseline_report),
            candidate_max_abs=_localized_payload(comparison.candidate_report),
            ready_for_run_validation=(
                comparison.status is ResultStatus.VALID
                and decision.status is DecisionStatus.ACCEPT
            ),
        )
        evidence_ref = self._artifacts.put_json(
            f"{contract.evaluation_id}-evidence",
            evidence.model_dump(mode="json"),
        )
        outcome, code = _evaluation_outcome(comparison, decision)
        return ApplicationResult(
            command="evaluate",
            outcome=outcome,
            code=code,
            message=_evaluation_message(code),
            workflow_id=contract.workflow_id,
            data={
                "comparison": comparison.model_dump(mode="json"),
                "decision": decision.model_dump(mode="json"),
                "evidence_candidate": evidence.model_dump(mode="json"),
                "artifact_refs": {
                    "comparison": comparison_ref.model_dump(mode="json"),
                    "decision": decision_ref.model_dump(mode="json"),
                    "evidence": evidence_ref.model_dump(mode="json"),
                },
                "max_abs_before_decision": {
                    "baseline": evidence.baseline_max_abs,
                    "candidate": evidence.candidate_max_abs,
                },
            },
        )


def load_post_run_contract(path: Path) -> PostRunEvaluationContract:
    if not path.is_absolute() or not path.is_file():
        raise ValueError("evaluation contract must be an existing absolute file")
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("evaluation contract exceeds the 4 MiB limit")
    return PostRunEvaluationContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def _load_field(
    descriptor: FieldArtifactDescriptor,
) -> tuple[FieldData, dict[str, np.ndarray]]:
    path = descriptor.path.resolve(strict=True)
    if _file_sha256(path) != descriptor.sha256:
        raise RuntimeError("field artifact hash does not match its descriptor")
    with np.load(path, allow_pickle=False) as archive:
        requested = {
            descriptor.values_key,
            *descriptor.coordinate_keys.values(),
            *descriptor.context_field_keys.values(),
            *descriptor.roi_mask_keys.values(),
        }
        missing = tuple(sorted(requested - set(archive.files)))
        if missing:
            raise ValueError(
                f"field artifact is missing declared arrays: {', '.join(missing)}"
            )
        values = np.array(archive[descriptor.values_key], copy=True)
        coordinates = {
            axis: np.array(archive[key], copy=True)
            for axis, key in descriptor.coordinate_keys.items()
        }
        context_fields = {
            name: np.array(archive[key], copy=True)
            for name, key in descriptor.context_field_keys.items()
        }
        roi_masks = {
            name: np.array(archive[key], dtype=bool, copy=True)
            for name, key in descriptor.roi_mask_keys.items()
        }
    if values.ndim != len(descriptor.axes):
        raise ValueError("field values rank does not match declared axes")
    coordinate_checks = tuple(
        coordinates[axis].ndim == 1
        and len(coordinates[axis]) == values.shape[index]
        for index, axis in enumerate(descriptor.axes)
    )
    if not coordinate_checks or not all(coordinate_checks):
        raise ValueError("coordinate arrays do not match declared field axes")
    artifact_ref = ArtifactRef(
        artifact_id=descriptor.artifact_id,
        uri=path.as_uri(),
        sha256=descriptor.sha256,
        media_type="application/x-npz",
        size_bytes=path.stat().st_size,
    )
    return (
        FieldData(
            values=values,
            artifact_ref=artifact_ref,
            axes=descriptor.axes,
            coordinates=coordinates,
            reference_identity=descriptor.reference_identity,
            unit=descriptor.unit,
            coordinate_system=descriptor.coordinate_system,
            normalization=descriptor.normalization,
            context_fields=context_fields,
        ),
        roi_masks,
    )


def _metric_values(report: PredictionAnalysisReport) -> dict[str, float]:
    collisions = report.global_metrics.keys() & report.domain_metrics.keys()
    if collisions:
        raise ValueError(
            "domain metrics collide with global metrics: "
            + ", ".join(sorted(collisions))
        )
    return {**report.global_metrics, **report.domain_metrics}


def _localized_payload(
    report: PredictionAnalysisReport,
) -> dict[str, JsonValue] | None:
    return (
        report.max_abs.model_dump(mode="json")
        if report.max_abs is not None
        else None
    )


def _evaluation_outcome(
    comparison: PredictionComparisonReport,
    decision: DecisionRecord,
) -> tuple[OperationOutcome, str]:
    if comparison.status is ResultStatus.INVALID:
        return OperationOutcome.GATE_REJECTED, "RESULT_INVALID"
    return {
        DecisionStatus.ACCEPT: (
            OperationOutcome.SUCCESS,
            "DECISION_ACCEPTED",
        ),
        DecisionStatus.REJECT: (
            OperationOutcome.GATE_REJECTED,
            "DECISION_REJECTED",
        ),
        DecisionStatus.NEEDS_EVIDENCE: (
            OperationOutcome.NEEDS_INPUT,
            "NEEDS_METRIC_EVIDENCE",
        ),
    }[decision.status]


def _evaluation_message(code: str) -> str:
    return {
        "RESULT_INVALID": "Field evidence is invalid; no optimization decision was accepted.",
        "DECISION_ACCEPTED": "Candidate passed the confirmed metric decision contract.",
        "DECISION_REJECTED": "Candidate was rejected by the confirmed metric decision contract.",
        "NEEDS_METRIC_EVIDENCE": "Required metric evidence is missing.",
    }[code]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
