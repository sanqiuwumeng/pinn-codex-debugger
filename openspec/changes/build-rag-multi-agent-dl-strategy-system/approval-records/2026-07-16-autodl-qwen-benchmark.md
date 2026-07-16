# AutoDL Qwen Formal Benchmark Approval

- Date: 2026-07-16
- User response: `Yes`
- Conversation-local instance label: `autodl-a6000`
- Intended GPU: NVIDIA RTX A6000, subject to remote preflight verification
- Job: `qwen3_retrieval_benchmark`

## Approved scope

This approval authorizes connecting to the user-provided AutoDL instance,
performing a read-only instance preflight, creating an isolated remote model
runtime, downloading the two approved official Qwen repositories at their
locked revisions, and running the frozen BF16 retrieval-quality and resource
benchmark.

## Security boundary

No host, port, username, password, private key or other instance credential is
recorded here or elsewhere in the repository. Credentials are transient
conversation inputs only.

## Execution boundary

The approval does not authorize PINN training, source modification, smoke/full
scientific experiments, deletion of remote data, overwriting existing remote
files without dated backups, hosted APIs, or model substitution.
