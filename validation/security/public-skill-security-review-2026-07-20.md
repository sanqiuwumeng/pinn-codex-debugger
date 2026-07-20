# Public Skill security review — 2026-07-20

## Decision

No critical or high-severity vulnerability was identified in the reviewed repository under the documented single-operator trust model. The repository may be packaged as a reusable Skill and prepared for public publication, subject to the residual boundaries below.

## Reviewed surfaces

- local and AutoDL process execution, cancellation, status reconciliation, and artifact collection;
- SSH command construction, host-key enforcement, error redaction, and credential persistence boundaries;
- staging and collection archive validation, extraction confinement, file-set validation, and hash checks;
- LangGraph approval gates, workflow persistence, metric authority, physical-unit audit, and architecture isolation;
- local MCP JSON-RPC server and deterministic handbook retrieval;
- Qwen3 local-snapshot loading, model/revision provenance, request/response bounds, and Qdrant local-mode index governance;
- formal Wiki publication, immutable versioning, evidence hashing, conflict behavior, and replay;
- remote full-chain input/result manifests and credential scans;
- tracked files, current Git history, dependency pins, and public-release state.

## Verification evidence

| Gate | Result |
| --- | --- |
| Orchestrator unit tests | 160 passed; 1 Windows-only skip for a Linux virtualenv symlink assertion |
| MCP tests | 20 passed |
| Retrieval benchmark contract tests | 7 passed |
| Cross-domain and Poisson contract tests | 4 passed |
| OpenSpec strict validation | 3 change sets passed |
| Python compilation | Passed |
| Git diff check before packaging | Passed |
| Installed dependency consistency | 144 installed packages checked; no broken requirements |
| OSV advisory query | 144 installed PyPI packages queried; zero vulnerable-package matches at review time |
| Dangerous-call scan | No `shell=True`, `eval`, `exec`, `os.system`, unsafe YAML/Pickle load, or pickle-enabled NumPy load |
| Credential scan | No tracked private key, assigned credential, direct SSH connection string, or AutoDL endpoint match |
| Direct-connection history scan | No matching commit in reachable Git history |

## Security properties confirmed

- Process launch uses explicit argument arrays rather than a shell.
- Local and remote commands require explicit interpreters, working directories, environments, output roots, and expected artifacts.
- Credential-like environment names and secret-bearing command arguments are rejected at governed execution boundaries.
- SSH transport uses strict host-key checking and sanitized failures.
- Remote and local cancellation act on recorded process identity rather than PID alone.
- Archive inputs reject traversal, links, special members, duplicates, unexpected members, and hash mismatch before promotion.
- Formal Wiki evidence is local-file-only, hash-verified, immutable, and idempotently replayed byte-for-byte.
- RAG retains source/model provenance and exposes claim conflicts instead of silently resolving them.
- The execution, orchestration, assurance, MCP, retrieval, and training modules remain physically separated by explicit contracts.

## Residual boundaries

1. The execution backend is intentionally not a hostile-code sandbox. A user-approved experiment command runs with the permissions of the chosen account. Untrusted third-party PINN code therefore requires a container or equivalent OS isolation.
2. The stdio MCP server has no explicit maximum input-line size. It is local-process-only and is not exposed as a network listener; this is a defense-in-depth hardening item, not a remote vulnerability in the reviewed deployment.
3. Qwen model downloads are pinned to repository revisions and runtime loading is local-only, but model files are not distributed by this repository. Snapshot acquisition remains an explicit supply-chain operation whose inventory must be recorded and verified.
4. OSV reports known advisories at a point in time and cannot prove the absence of unpublished or future vulnerabilities.
5. Public visibility does not itself define a software license. Repository reuse by third parties remains legally unspecified until the owner selects and adds a license.

## Publication controls

- Publish only the reviewed Git commit and its tracked files.
- Exclude result trees, model caches, runtime databases, backups, logs, credentials, SSH material, and environment-specific paths.
- Re-run the repository audit, release gates, Skill validator, staged-content credential scan, and `git diff --check` immediately before push.
- Verify the GitHub owner, repository name, target branch, and public visibility after the remote mutation.
