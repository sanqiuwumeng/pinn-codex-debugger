"""Versioned contracts and JSONL transports for isolated retrieval models."""

from __future__ import annotations

import json
import math
import queue
import subprocess
import threading
from pathlib import Path
from typing import Literal, Protocol, TypeVar

from pydantic import Field, ValidationError, model_validator

from pinn_strategy_system.contracts import VersionedModel


class ModelProvenance(VersionedModel):
    model_id: str = Field(min_length=1, max_length=512)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_id: str = Field(min_length=1, max_length=256)
    runtime_version: str = Field(min_length=1, max_length=256)
    precision: str = Field(min_length=1, max_length=64)


class EmbeddingRequest(VersionedModel):
    operation: Literal["embed"] = "embed"
    request_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=512)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    input_type: Literal["document", "query"]
    texts: tuple[str, ...] = Field(min_length=1, max_length=4096)
    output_dimension: int = Field(ge=1, le=4096)


class EmbeddingResponse(VersionedModel):
    operation: Literal["embed"] = "embed"
    request_id: str = Field(min_length=1, max_length=256)
    provenance: ModelProvenance
    output_dimension: int = Field(ge=1, le=4096)
    vectors: tuple[tuple[float, ...], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def vectors_match_declared_dimension(self):
        if any(len(vector) != self.output_dimension for vector in self.vectors):
            raise ValueError("embedding vector does not match output_dimension")
        if any(
            not math.isfinite(float(value))
            for vector in self.vectors
            for value in vector
        ):
            raise ValueError("embedding response contains a non-finite value")
        return self


class RerankDocument(VersionedModel):
    document_id: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=100_000)


class RerankRequest(VersionedModel):
    operation: Literal["rerank"] = "rerank"
    request_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=512)
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    query: str = Field(min_length=1, max_length=4096)
    documents: tuple[RerankDocument, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def document_ids_are_unique(self):
        identifiers = tuple(item.document_id for item in self.documents)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("rerank document_id values must be unique")
        return self


class RerankScore(VersionedModel):
    document_id: str = Field(min_length=1, max_length=256)
    score: float = Field(allow_inf_nan=False)


class RerankResponse(VersionedModel):
    operation: Literal["rerank"] = "rerank"
    request_id: str = Field(min_length=1, max_length=256)
    provenance: ModelProvenance
    scores: tuple[RerankScore, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def score_ids_are_unique(self):
        identifiers = tuple(item.document_id for item in self.scores)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("rerank response document_id values must be unique")
        return self


class ModelHealthRequest(VersionedModel):
    operation: Literal["health"] = "health"
    request_id: str = Field(min_length=1, max_length=256)
    model_role: Literal["embedding", "reranker"]


class ModelHealthResponse(VersionedModel):
    operation: Literal["health"] = "health"
    request_id: str = Field(min_length=1, max_length=256)
    status: Literal["ready", "loading", "unavailable"]
    provenance: ModelProvenance | None = None

    @model_validator(mode="after")
    def ready_requires_provenance(self):
        if self.status == "ready" and self.provenance is None:
            raise ValueError("ready model health requires provenance")
        return self


class ModelErrorResponse(VersionedModel):
    operation: Literal["error"] = "error"
    request_id: str = Field(min_length=1, max_length=256)
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    message: str = Field(min_length=1, max_length=512)
    retryable: bool


RequestModel = EmbeddingRequest | RerankRequest | ModelHealthRequest
ResponseModel = EmbeddingResponse | RerankResponse | ModelHealthResponse
ResponseT = TypeVar("ResponseT", bound=VersionedModel)


class ModelTransport(Protocol):
    def exchange(
        self,
        request: RequestModel,
        *,
        response_type: type[ResponseT],
    ) -> ResponseT: ...


class RemoteJsonlExchange(Protocol):
    def exchange_jsonl(self, request_line: str, timeout_seconds: float) -> str: ...


class ModelTransportError(RuntimeError):
    """Credential- and payload-safe model transport failure."""


class ModelServiceError(RuntimeError):
    def __init__(self, error: ModelErrorResponse) -> None:
        super().__init__(
            f"model service returned {error.error_code}; "
            f"retryable={str(error.retryable).lower()}"
        )
        self.error_code = error.error_code
        self.retryable = error.retryable


class SubprocessJsonlModelTransport:
    """Persistent, isolated JSONL subprocess with explicit process inputs."""

    def __init__(
        self,
        *,
        executable: Path,
        arguments: tuple[str, ...],
        working_directory: Path,
        environment: tuple[tuple[str, str], ...],
        timeout_seconds: float = 120.0,
        max_request_bytes: int = 8 * 1024 * 1024,
        max_response_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError("model executable must be an existing absolute file")
        if not working_directory.is_absolute() or not working_directory.is_dir():
            raise ValueError("model working directory must be an absolute directory")
        if timeout_seconds <= 0:
            raise ValueError("model timeout must be positive")
        if max_request_bytes < 1 or max_response_bytes < 1:
            raise ValueError("model JSONL size limits must be positive")
        names = tuple(name.casefold() for name, _ in environment)
        if len(names) != len(set(names)):
            raise ValueError("model environment names must be unique")
        if any("\x00" in value or "\n" in value for value in arguments):
            raise ValueError("model argument contains a forbidden control character")
        self._command = (str(executable), *arguments)
        self._working_directory = working_directory
        self._environment = dict(environment)
        self._timeout_seconds = timeout_seconds
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback) -> None:
        self.close()

    def exchange(
        self,
        request: RequestModel,
        *,
        response_type: type[ResponseT],
    ) -> ResponseT:
        with self._lock:
            process = self._ensure_started()
            request_line = request.model_dump_json()
            _validate_jsonl_request(request_line, self._max_request_bytes)
            try:
                assert process.stdin is not None
                process.stdin.write(request_line + "\n")
                process.stdin.flush()
                response_line = self._responses.get(timeout=self._timeout_seconds)
            except (BrokenPipeError, OSError, queue.Empty) as error:
                self._stop_process()
                raise ModelTransportError(
                    f"model subprocess exchange failed: {type(error).__name__}"
                ) from None
            if response_line is None:
                code = process.poll()
                self._stop_process()
                raise ModelTransportError(
                    f"model subprocess ended before response; exit_code={code}"
                )
            return _parse_response(
                response_line,
                request=request,
                response_type=response_type,
                max_response_bytes=self._max_response_bytes,
            )

    def close(self) -> None:
        with self._lock:
            self._stop_process()

    def _ensure_started(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        try:
            process = subprocess.Popen(
                self._command,
                cwd=self._working_directory,
                env=self._environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0
                ),
            )
        except OSError as error:
            raise ModelTransportError(
                f"model subprocess could not start: {type(error).__name__}"
            ) from None
        self._process = process
        self._responses = queue.Queue()
        assert process.stdout is not None
        threading.Thread(
            target=self._read_responses,
            args=(process.stdout,),
            daemon=True,
        ).start()
        return process

    def _read_responses(self, stream) -> None:
        for line in stream:
            self._responses.put(line.rstrip("\r\n"))
        self._responses.put(None)

    def _stop_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None:
            try:
                if process.stdin is not None:
                    process.stdin.close()
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            if stream is not None and not stream.closed:
                stream.close()


class RemoteJsonlModelTransport:
    """JSONL transport over an injected, credential-owning remote boundary."""

    def __init__(
        self,
        *,
        remote: RemoteJsonlExchange,
        timeout_seconds: float = 120.0,
        max_request_bytes: int = 8 * 1024 * 1024,
        max_response_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("remote model timeout must be positive")
        if max_request_bytes < 1 or max_response_bytes < 1:
            raise ValueError("remote model JSONL size limits must be positive")
        self._remote = remote
        self._timeout_seconds = timeout_seconds
        self._max_request_bytes = max_request_bytes
        self._max_response_bytes = max_response_bytes

    def exchange(
        self,
        request: RequestModel,
        *,
        response_type: type[ResponseT],
    ) -> ResponseT:
        request_line = request.model_dump_json()
        _validate_jsonl_request(request_line, self._max_request_bytes)
        try:
            response_line = self._remote.exchange_jsonl(
                request_line,
                self._timeout_seconds,
            )
        except Exception as error:
            raise ModelTransportError(
                f"remote model exchange failed: {type(error).__name__}"
            ) from None
        return _parse_response(
            response_line,
            request=request,
            response_type=response_type,
            max_response_bytes=self._max_response_bytes,
        )


def _validate_jsonl_request(value: str, maximum_bytes: int) -> None:
    if "\n" in value or "\r" in value:
        raise ModelTransportError("model request is not a single JSONL record")
    if len(value.encode("utf-8")) > maximum_bytes:
        raise ModelTransportError("model request exceeds the configured size limit")


def _parse_response(
    value: str,
    *,
    request: RequestModel,
    response_type: type[ResponseT],
    max_response_bytes: int,
) -> ResponseT:
    if not isinstance(value, str):
        raise ModelTransportError("model response must be text")
    if "\n" in value or "\r" in value:
        raise ModelTransportError("model response is not a single JSONL record")
    if len(value.encode("utf-8")) > max_response_bytes:
        raise ModelTransportError("model response exceeds the configured size limit")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        raise ModelTransportError("model response is invalid JSON") from None
    if not isinstance(payload, dict):
        raise ModelTransportError("model response must be a JSON object")
    if payload.get("operation") == "error":
        try:
            error = ModelErrorResponse.model_validate(payload)
        except ValidationError:
            raise ModelTransportError("model error response is invalid") from None
        if error.request_id != request.request_id:
            raise ModelTransportError("model error request_id mismatch")
        raise ModelServiceError(error)
    try:
        response = response_type.model_validate(payload)
    except ValidationError:
        raise ModelTransportError("model response contract validation failed") from None
    if getattr(response, "request_id", None) != request.request_id:
        raise ModelTransportError("model response request_id mismatch")
    return response
