"""Governed hybrid retrieval over deterministic and derived indexes."""

from .hybrid import HybridRetriever
from .models import (
    EvidenceClaim,
    EvidenceConflict,
    HybridEvidence,
    HybridRetrievalResponse,
    IndexedKnowledgeDocument,
    RetrievalScope,
    VectorHit,
)
from .provenance import ProvenanceError, ProvenanceValidator
from .source import FilesystemKnowledgeSource
from .vector_index import EmbeddingProvider, LocalQdrantIndex

__all__ = [
    "EvidenceClaim",
    "EvidenceConflict",
    "EmbeddingProvider",
    "FilesystemKnowledgeSource",
    "HybridEvidence",
    "HybridRetrievalResponse",
    "HybridRetriever",
    "IndexedKnowledgeDocument",
    "LocalQdrantIndex",
    "ProvenanceError",
    "ProvenanceValidator",
    "RetrievalScope",
    "VectorHit",
]
