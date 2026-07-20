# Portable operations

## Runtime separation

Use three explicit environments when the workload requires them:

1. Orchestration: Python 3.11 with the pinned dependencies from `orchestrator/pyproject.toml`.
2. Training: the PINN project's own PyTorch or framework environment. Do not install orchestration packages into it merely for convenience.
3. Retrieval: the GPU environment that hosts the approved local Qwen3 snapshots and `retrieval-runtime/qwen3_jsonl_gateway.py`.

Pass interpreter paths in profiles and manifests. Never rely on an activated shell, ambient current directory, or inherited secret-bearing environment.

## Install the Skill on another machine

Copy the complete `skills/pinn-rag-strategy-system` directory into the target Codex skills directory. Keep `SKILL.md`, `agents/openai.yaml`, `references/`, and `scripts/` together. Do not copy repository-local backups, experiment results, model caches, credentials, or runtime databases.

After copying, run the skill validator from the target Codex installation. Then run:

```text
python scripts/audit_repository.py --repo-root <cloned-system-repository>
python scripts/run_release_gates.py --repo-root <cloned-system-repository> --python <orchestration-python>
```

## Adapt a PINN project

Use the repository CLI with absolute paths. The exact project manifest and case are project-specific; do not copy Poisson or thermal physics into another PDE merely to satisfy a schema.

```text
pinn-strategy adapt --runtime-root <runtime> --manifest <project-manifest.json> --output <operator-case.json> --json
pinn-strategy audit --runtime-root <runtime> --case <operator-case.json> --json
pinn-strategy plan --runtime-root <runtime> --case <operator-case.json> --json
```

Resolve every returned input gate before launching. Keep the authoritative project source read-only during adaptation and audit.

## Remote execution and transfer

- Stage one exact Git commit and record the source archive SHA-256.
- Verify the remote Python interpreters and run a real GPU kernel smoke before a long GPU job.
- Acquire authentication material at runtime using the method explicitly approved by the user. Never put it in the Skill, repository, shell scripts, command arguments, logs, or result manifests.
- Use a versioned remote root and a new result directory. Do not overwrite a prior run.
- Monitor durable process identity, heartbeat, status events, logs, and expected artifacts.
- On cancellation, require scoped approval and preserve partial evidence.
- Download only after the remote terminal marker and completion manifest exist.
- Verify the downloaded bundle with `verify_completion_bundle.py` before accepting it.

## Qwen retrieval runtime

The repository records approved Qwen3 model IDs and immutable revisions. Download is a separate, explicit network operation. Runtime loading must use the local snapshot, confirm that the snapshot directory matches the approved revision, and keep remote model code disabled unless the repository contract is deliberately revised and approved.

Do not bundle model weights in the Skill or Git repository.
