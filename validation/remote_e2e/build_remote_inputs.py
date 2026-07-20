"""Build a hash-verified, relocatable input packet for remote Wiki publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import url2pathname

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_SRC = REPOSITORY_ROOT / "orchestrator" / "src"
sys.path.insert(0, str(ORCHESTRATOR_SRC))

from pinn_strategy_system.contracts import (  # noqa: E402
    ApprovalDecision,
    ApprovalKind,
    ApprovalRecord,
    ArtifactRef,
    WikiEntryCandidate,
    WikiPublicationSpec,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_time(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("approval and publication timestamps must include timezone")
    return timestamp


def _local_file(artifact: ArtifactRef) -> Path:
    parsed = urlparse(artifact.uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("candidate evidence must use local file URIs")
    path = Path(url2pathname(parsed.path)).resolve(strict=True)
    if not path.is_file():
        raise ValueError("candidate evidence must reference files")
    if _sha256(path) != artifact.sha256:
        raise ValueError(f"candidate evidence hash mismatch: {artifact.artifact_id}")
    if artifact.size_bytes is not None and path.stat().st_size != artifact.size_bytes:
        raise ValueError(f"candidate evidence size mismatch: {artifact.artifact_id}")
    return path


def _safe_name(artifact: ArtifactRef, source: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", artifact.artifact_id)
    if not stem or stem in {".", ".."}:
        raise ValueError("artifact identifier cannot form a safe evidence name")
    suffix = source.suffix if source.suffix else ".bin"
    return f"{stem}-{artifact.sha256[:16]}{suffix}"


def _candidate_refs(candidate: WikiEntryCandidate) -> tuple[ArtifactRef, ...]:
    return (
        candidate.source_snapshot_ref,
        *candidate.dataset_refs,
        candidate.environment_ref,
        candidate.metric_report_ref,
        candidate.physical_audit_ref,
        candidate.reproducibility_report_ref,
        candidate.validation_report_ref,
    )


def build(
    *,
    knowledge_candidates: Path,
    output_root: Path,
    remote_input_root: PurePosixPath,
    repo_commit: str,
    approval_at: datetime,
    published_at: datetime,
) -> Path:
    knowledge_candidates = knowledge_candidates.resolve(strict=True)
    if output_root.exists():
        raise FileExistsError("remote input output root already exists")
    if not remote_input_root.is_absolute():
        raise ValueError("remote input root must be absolute")
    if re.fullmatch(r"[0-9a-f]{40}", repo_commit) is None:
        raise ValueError("repo commit must be a full Git SHA-1")
    output_root.mkdir(parents=True)
    evidence_root = output_root / "evidence"
    evidence_root.mkdir()

    source_payload = json.loads(knowledge_candidates.read_text(encoding="utf-8"))
    candidate = WikiEntryCandidate.model_validate(source_payload["wiki_candidate"])
    copied: dict[tuple[str, str], ArtifactRef] = {}

    def remap(artifact: ArtifactRef) -> ArtifactRef:
        key = (artifact.artifact_id, artifact.sha256)
        existing = copied.get(key)
        if existing is not None:
            return existing
        source = _local_file(artifact)
        name = _safe_name(artifact, source)
        target = evidence_root / name
        if target.exists():
            raise FileExistsError("evidence packet target already exists")
        shutil.copyfile(source, target)
        if _sha256(target) != artifact.sha256:
            raise RuntimeError("copied evidence failed hash verification")
        remote_path = remote_input_root / "evidence" / name
        rewritten = artifact.model_copy(update={"uri": remote_path.as_uri()})
        copied[key] = rewritten
        return rewritten

    payload = candidate.model_dump(mode="python")
    payload.update(
        {
            "source_snapshot_ref": remap(candidate.source_snapshot_ref),
            "dataset_refs": tuple(remap(item) for item in candidate.dataset_refs),
            "environment_ref": remap(candidate.environment_ref),
            "metric_report_ref": remap(candidate.metric_report_ref),
            "physical_audit_ref": remap(candidate.physical_audit_ref),
            "reproducibility_report_ref": remap(
                candidate.reproducibility_report_ref
            ),
            "validation_report_ref": remap(candidate.validation_report_ref),
        }
    )
    remote_candidate = WikiEntryCandidate.model_validate(payload)
    approval = ApprovalRecord(
        approval_id="wiki-publication-user-approval-20260720",
        workflow_id="activate-experiment-wiki-remote-e2e",
        kind=ApprovalKind.KNOWLEDGE_PROMOTION,
        decision=ApprovalDecision.APPROVED,
        approved_by="user",
        approved_at=approval_at,
        scope=f"wiki:{remote_candidate.candidate_id}",
    )
    publication = WikiPublicationSpec(
        wiki_id="peer-pinn-localized-collocation",
        published_at=published_at,
        project_id="universal-pinn-strategy-system",
        repo_commit=repo_commit,
        model_family="PINN",
        pde_family="cross-domain",
        task_type="strategy-optimization",
        output_channels=(),
        dimensional_signatures=("case-local-units",),
        failure_signatures=("localized-max-abs",),
        framework="PyTorch",
        language="en",
        claims={
            "decision_authority": "user-approved case metric contract",
            "localized_sampling_scope": "case-and-seed-dependent",
        },
    )

    contracts = {
        "candidate.json": remote_candidate.model_dump(mode="json"),
        "approval.json": approval.model_dump(mode="json"),
        "publication.json": publication.model_dump(mode="json"),
    }
    for name, contract in contracts.items():
        (output_root / name).write_text(
            json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    files = tuple(sorted(path for path in output_root.rglob("*") if path.is_file()))
    manifest = {
        "schema_version": "1.0",
        "repo_commit": repo_commit,
        "remote_input_root": str(remote_input_root),
        "files": [
            {
                "relative_path": path.relative_to(output_root).as_posix(),
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    manifest_path = output_root / "input-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output_root": str(output_root.resolve()),
                "files": len(files) + 1,
                "evidence_files": len(copied),
                "manifest_sha256": _sha256(manifest_path),
            },
            sort_keys=True,
        )
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-candidates", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--remote-input-root", type=PurePosixPath, required=True)
    parser.add_argument("--repo-commit", required=True)
    parser.add_argument("--approval-at", required=True)
    parser.add_argument("--published-at", required=True)
    args = parser.parse_args()
    build(
        knowledge_candidates=args.knowledge_candidates,
        output_root=args.output_root.resolve(strict=False),
        remote_input_root=args.remote_input_root,
        repo_commit=args.repo_commit,
        approval_at=_parse_time(args.approval_at),
        published_at=_parse_time(args.published_at),
    )


if __name__ == "__main__":
    main()
