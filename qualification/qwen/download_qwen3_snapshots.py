"""Download the approved immutable Qwen3 retrieval model snapshots.

The benchmark runner is deliberately offline-only. This separate downloader
materializes exactly the approved Hugging Face revisions into one cache and
writes a compact manifest for the experiment evidence bundle.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download


def locked_models() -> tuple[dict[str, str], ...]:
    """Return the only model revisions authorized for this benchmark."""
    return (
        {
            "role": "embedding",
            "repo_id": "Qwen/Qwen3-Embedding-8B",
            "revision": "1d8ad4ca9b3dd8059ad90a75d4983776a23d44af",
        },
        {
            "role": "reranker",
            "repo_id": "Qwen/Qwen3-Reranker-4B",
            "revision": "22e683669bc0f0bd69640a1354a6d0aebcfeede5",
        },
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot_inventory(snapshot: Path) -> dict[str, Any]:
    files = tuple(path for path in snapshot.rglob("*") if path.is_file())
    return {
        "snapshot": str(snapshot.resolve()),
        "file_count": len(files),
        "logical_bytes": sum(path.stat().st_size for path in files),
    }


def disk_inventory(path: Path) -> dict[str, int]:
    usage = shutil.disk_usage(path)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def download_locked_snapshots(cache_root: Path, max_workers: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for model in locked_models():
        print(
            json.dumps(
                {
                    "event": "download_started",
                    "time_utc": utc_now(),
                    **model,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        snapshot = Path(
            snapshot_download(
                repo_id=model["repo_id"],
                revision=model["revision"],
                cache_dir=cache_root,
                max_workers=max_workers,
            )
        )
        if snapshot.name != model["revision"]:
            raise RuntimeError(
                f"resolved snapshot {snapshot.name!r} does not match locked revision "
                f"{model['revision']!r}"
            )
        record = {
            **model,
            **snapshot_inventory(snapshot),
            "completed_at_utc": utc_now(),
            "disk": disk_inventory(cache_root),
        }
        records.append(record)
        print(
            json.dumps({"event": "download_completed", **record}, sort_keys=True),
            flush=True,
        )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_workers < 1:
        raise ValueError("max-workers must be positive")
    if args.manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite {args.manifest_path}")

    args.cache_root.mkdir(parents=True, exist_ok=True)
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "cache_root": str(args.cache_root.resolve()),
        "models": download_locked_snapshots(args.cache_root, args.max_workers),
    }
    args.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "event": "manifest_written",
                "manifest_path": str(args.manifest_path.resolve()),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
