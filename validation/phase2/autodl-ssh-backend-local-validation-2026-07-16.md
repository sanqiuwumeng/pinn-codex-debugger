# Phase 2 AutoDL SSH Backend Local Validation

- Date: 2026-07-16
- OpenSpec tasks: 4.1-4.4
- Outcome: PASS locally; remote qualification remains task 4.5
- Execution scope: fake transport and bounded local archives only; no AutoDL connection
- Environment: existing `pinn_strategy_orchestrator`; no package added

## Isolated connection boundary

`SshConnectionProfile` persists only:

- a conversation-level profile alias;
- SHA-256 of the approved host-key fingerprint;
- SHA-256 of the approved identity-key fingerprint;
- the fixed transport identifier `system-openssh`.

Username, hostname, port, identity-file path and known-hosts path exist only in the in-memory `SystemOpenSshRuntime`. Its representation and all `SshTransportError` messages are redacted and never include the command array, endpoint, stderr or key path.

## Staging and execution boundary

`SystemOpenSshTransport` uses explicit absolute `ssh.exe`/`scp.exe` paths, key and known-hosts files, `BatchMode=yes`, `PasswordAuthentication=no`, `IdentitiesOnly=yes` and strict host-key checking. Every local subprocess receives an explicit working directory and environment.

Content is installed by SHA-256. A new upload uses a unique temporary remote path; existing matching content is reused. Existing differing content is copied to a timestamped parent and a filename ending in `_backup_YYYY-MM-DD` before replacement. Remote run, workspace, output, staging, request and collection paths are confined below the configured run root.

The dependency-free Linux worker provides:

- atomic append-only status and heartbeat JSON;
- durable detached launch independent of SSH session lifetime;
- target and launcher PID plus Linux `/proc` start-tick identity;
- explicit target environment and absolute interpreter/working paths;
- stdout/stderr files, exit code and required-artifact evidence;
- exact descendant-tree cancellation after scoped approval;
- source SHA-256 manifest and tar creation for the exact declared artifact set.

## Disconnect and transfer semantics

- A lost launch response moves the registry to `RUNNING_UNKNOWN`; retry returns the existing reservation and reconciliation performs zero relaunches.
- A transport failure during reconciliation returns sanitized `RUNNING_UNKNOWN` rather than inventing a process outcome.
- Cancellation persists the exact request locally and remotely before signaling PID/start-tick-matched processes.
- Collection invokes the remote manifest operation before download.
- Downloads enter a uniquely named `.partial.tar` quarantine path. Transfer, tar membership, remote source manifest, size and SHA-256 checks must all pass before no-overwrite promotion.
- Interrupted or invalid transfers remain non-authoritative and are preserved for diagnosis.

## Verification

| Gate | Result |
| --- | --- |
| AutoDL backend tests | PASS, 5 tests |
| Connection-profile contract test | PASS |
| Full orchestrator regression | PASS, 118 tests |
| Compile and import checks | PASS |
| Architecture-boundary suite | PASS as part of orchestrator regression |
| `git diff --check` | PASS |

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The first transport redaction test found that a second validation layer rejected newline characters inside the backend-owned inline Python bootstrap template. External arguments remain control-character-validated; the redundant validation of trusted fixed templates was removed.

### First-principles refactoring

SSH connectivity is transport evidence, not run truth. The backend persists a deterministic reference before launch, and remote status combines process start identity, heartbeat, append-only status, exit code, logs and declared artifacts. A transport disconnect therefore changes observability, not the remote run identity.

### Simplification

The implementation is physically split into three roles: credential-transient system transport, lifecycle backend and dependency-free remote worker. No Python SSH dependency, shell-session singleton or endpoint-bearing workflow object was introduced.

## Remaining boundary

Task 4.5 still requires an AutoDL read-only preflight and bounded end-to-end launch/disconnect/reconcile/collect qualification. Task 4.6 remains open until the resulting local and remote evidence is scanned for endpoint and credential leakage.
