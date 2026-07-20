"""Application boundary for explicit formal Wiki publication."""

from __future__ import annotations

from pathlib import Path

from pinn_strategy_system.assurance import KnowledgeGovernanceService
from pinn_strategy_system.contracts import (
    ApprovalRecord,
    WikiEntryCandidate,
    WikiPublicationSpec,
)
from pinn_strategy_system.storage import PublishedWikiStore

from .contracts import ApplicationResult, OperationOutcome


class WikiPublicationApplicationService:
    def __init__(
        self,
        *,
        runtime_root: Path,
        knowledge_root: Path,
    ) -> None:
        if not runtime_root.is_absolute() or not knowledge_root.is_absolute():
            raise ValueError("Wiki runtime and knowledge roots must be absolute")
        runtime = runtime_root.resolve(strict=False)
        knowledge = knowledge_root.resolve(strict=True)
        if _overlaps(runtime, knowledge):
            raise ValueError("Wiki runtime and authoritative knowledge must not overlap")
        runtime.mkdir(parents=True, exist_ok=True)
        self._governance = KnowledgeGovernanceService()
        self._store = PublishedWikiStore(knowledge)

    def publish(
        self,
        *,
        candidate: WikiEntryCandidate,
        approval: ApprovalRecord,
        publication: WikiPublicationSpec,
    ) -> ApplicationResult:
        entry = self._governance.publish_wiki(
            candidate=candidate,
            approval=approval,
            publication=publication,
        )
        receipt = self._store.publish(entry)
        replay = receipt.idempotent_replay
        return ApplicationResult(
            command="wiki publish",
            outcome=OperationOutcome.SUCCESS,
            code=("WIKI_VERIFIED" if replay else "WIKI_PUBLISHED"),
            message=(
                "Existing formal Wiki version matched every expected byte and hash."
                if replay
                else "Approved Wiki candidate was committed as an immutable version."
            ),
            data={
                "publication": entry.model_dump(mode="json"),
                "receipt": receipt.model_dump(mode="json"),
                "skill_published": False,
            },
        )


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents
