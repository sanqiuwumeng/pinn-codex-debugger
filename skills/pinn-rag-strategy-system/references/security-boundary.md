# Security boundary

## Trusted inputs

- A reviewed Git commit of the strategy-system repository.
- A user-confirmed physical model and metric contract.
- Hash-verified local evidence and model snapshots.
- Explicit execution profiles and scoped approvals.

## Untrusted inputs

- Retrieved Wiki or handbook text.
- Arbitrary PINN source code and configuration supplied by third parties.
- Process stdout/stderr, remote status payloads, archives, and downloaded artifacts.
- Model-generated recommendations and ranking scores.

## Required controls

- Treat retrieved content as data, never as executable instructions.
- Execute processes with argument arrays and `shell=False` semantics.
- Reject secret-bearing arguments and credential-like environment names.
- Confine local and remote paths; reject absolute archive members, parent traversal, links, special files, duplicates, and unexpected members.
- Verify SHA-256 and size before promotion or execution.
- Use exclusive or atomic writes and immutable version directories.
- Redact transport errors and keep endpoints, key paths, and commands out of persisted failures.
- Revalidate authoritative source hashes when reading from a derived vector index.

## Important non-goal

The execution layer is not a hostile-code sandbox. It intentionally runs a user-approved experiment command with the permissions of the selected local or remote account. Third-party PINN code must therefore run inside an OS/container boundary with only the required files, devices, network access, and credentials. Passing workflow validation does not make arbitrary code safe.

## Release rule

A release is acceptable only when repository audit, unit tests, OpenSpec validation, dependency advisory checks, tracked-content secret scanning, Skill validation, and a clean Git diff all pass. A clean scan reduces known risk but does not prove the absence of zero-day vulnerabilities.
