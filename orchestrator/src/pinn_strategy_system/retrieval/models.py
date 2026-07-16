"""Serializable contracts for scoped retrieval and conflict evidence."""

from __future__ import annotations

from typing import Self

from pydantic import Field, JsonValue, model_validator

from pinn_strategy_system.contracts import KnowledgeChunk, SourceRef, VersionedModel


class EvidenceClaim(VersionedModel):
    key: str = Field(min_length=1, max_length=512)
    value: str = Field(min_length=1, max_length=4096)


class IndexedKnowledgeDocument(VersionedModel):
    chunk: KnowledgeChunk
    applicable_versions: tuple[str, ...] = ()
    claims: tuple[EvidenceClaim, ...] = ()


class RetrievalScope(VersionedModel):
    project_id: str = Field(min_length=1, max_length=256)
    document_types: tuple[str, ...] = ()
    validation_statuses: tuple[str, ...] = ()
    model_family: str | None = Field(default=None, max_length=256)
    pde_family: str | None = Field(default=None, max_length=256)
    task_type: str | None = Field(default=None, max_length=256)
    domain_provider_id: str | None = Field(default=None, max_length=256)
    output_channels: tuple[str, ...] = ()
    dimensional_signatures: tuple[str, ...] = ()
    failure_signatures: tuple[str, ...] = ()
    framework: str | None = Field(default=None, max_length=256)
    applicable_version: str | None = Field(default=None, max_length=256)
    languages: tuple[str, ...] = ()


class VectorHit(VersionedModel):
    document: IndexedKnowledgeDocument
    score: float = Field(allow_inf_nan=False)


class HybridEvidence(VersionedModel):
    evidence_id: str = Field(min_length=1, max_length=256)
    source_ref: SourceRef
    artifact_range: str | None = Field(default=None, max_length=1024)
    excerpt: str = Field(min_length=1, max_length=4096)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    deterministic_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    fused_score: float = Field(allow_inf_nan=False, ge=0)
    claims: tuple[EvidenceClaim, ...] = ()
    conflict_keys: tuple[str, ...] = ()
    provenance_validated: bool

    @model_validator(mode="after")
    def has_a_source_range(self) -> Self:
        if self.source_ref.line_start is None and self.artifact_range is None:
            raise ValueError("hybrid evidence requires a source or artifact range")
        return self


class EvidenceConflict(VersionedModel):
    claim_key: str = Field(min_length=1, max_length=512)
    claim_values: tuple[str, ...] = Field(min_length=2)
    evidence_ids: tuple[str, ...] = Field(min_length=2)


class HybridRetrievalResponse(VersionedModel):
    request_id: str = Field(min_length=1, max_length=256)
    backend: str = Field(min_length=1, max_length=512)
    evidence: tuple[HybridEvidence, ...] = ()
    conflicts: tuple[EvidenceConflict, ...] = ()
    decision_safe: bool
    read_only: bool = True

    @model_validator(mode="after")
    def conflicts_block_decisions(self) -> Self:
        if self.conflicts and self.decision_safe:
            raise ValueError("unresolved evidence conflicts must block decisions")
        if not self.read_only:
            raise ValueError("retrieval responses must remain read-only")
        return self
