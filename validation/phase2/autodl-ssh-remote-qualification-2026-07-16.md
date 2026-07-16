# Phase 2 AutoDL SSH Remote Qualification

- Date: 2026-07-16
- OpenSpec tasks: 4.5-4.6
- Outcome: PASS
- Instance label: `autodl-a`
- Authentication: approved existing key through strict system OpenSSH
- Connection details: intentionally omitted
- Remote workload: three-second Python fixture; no PINN training and no GPU use

## Read-only preflight

| Check | Observation |
| --- | --- |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB total |
| GPU state | 0 MiB used, 0% utilization, no compute process |
| Root disk | 30 GiB total, approximately 29.2 GiB free |
| Base Python | `/root/miniconda3/bin/python`, Python 3.10.8 |
| Base PyTorch | not installed; not required for backend qualification |
| Isolated retrieval environment | existing path detected under `/root/autodl-tmp`; not accessed or modified |
| Existing service processes | three Python-matching service processes, none using GPU |
| Planned remote root before work | absent |

The key-derived public fingerprint matched the approved public key. The existing known-hosts entry passed strict validation. Only secondary SHA-256 fingerprint records were persisted by the qualification profile.

## Bounded end-to-end result

The successful run ID was `autodl-backend-qualification-20260716-v4`. The sequence deliberately exercised failure recovery:

1. Prepare uploaded the content-addressed worker, staging tar and request and verified their remote SHA-256 values.
2. Launch created the durable remote wrapper exactly once.
3. The client intentionally discarded the successful launch response, causing registry state `RUNNING_UNKNOWN`.
4. An exact duplicate submission returned the existing reservation and did not call launch.
5. The first status request simulated a transport disconnect and preserved `RUNNING_UNKNOWN`.
6. A fresh transport/backend instance reconnected, reconciled the same PID/start-tick identity and observed completion.
7. Remote collection created the source manifest and archive before a single successful download.
8. Local quarantine, tar membership, source manifest, file size and SHA-256 gates passed before promotion.
9. Repeating the same collection verified the existing governed destination without overwrite.

All ten qualification checks in the local structured report passed. The observed remote launch count was exactly one.

## Remote completion evidence

| Evidence | Result |
| --- | --- |
| Final phase / exit code | `COMPLETED` / `0` |
| Status events | 3 |
| Heartbeats | 6 |
| stdout | 47 bytes; bounded success marker present |
| stderr | 0 bytes |
| Launcher / target liveness | both stopped after completion |
| Collection archives | 1 |
| GPU after completion | 0 MiB used, 0% utilization |
| Remote evidence tree | 30 files, 89,241 bytes |

Artifact correspondence:

| Artifact | Bytes | Remote/local SHA-256 |
| --- | ---: | --- |
| `metrics.json` | 24 | `dd525d24320815496d974c34330fd23c37fb119d0cb60c99fc10635efb371b64` |
| `run_status.json` | 23 | `9e644bfbd7b95295fb3deb0bcaed1a54e63c63764ce9f8925d536032eb488628` |

The local result tree contains 19 files and 55,621 bytes. It remains under the ignored runtime-results boundary and is referenced by this tracked evidence report rather than committed.

## Credential and endpoint audit

- The tracked implementation and qualification script contain no real endpoint, port, password, private key or direct SSH command.
- The local successful evidence tree passed scans for the transient endpoint, direct SSH form, private-key markers and credential assignments.
- All remote files below the governed root up to 5 MiB passed byte scans for the transient endpoint, direct connection form, private-key marker and serialized password field.
- Persisted connection profile JSON contains only alias, transport and host/key fingerprint SHA-256 records.
- `SshTransportError` output remained sanitized during all three debug failures.

## Preserved non-authoritative attempts

No failure evidence was deleted or overwritten:

- v1 stopped locally before remote write because the explicit Windows OpenSSH environment lacked `PROGRAMDATA`.
- v2 connected, created the root and uploaded a temporary worker, then stopped before prepare because the remote Python 3.10 runtime rejected `datetime.UTC`.
- v3 installed content and completed remote prepare, then stopped before launch because the client attempted to parse only the final line of multi-line JSON.
- v4 used a new run ID and content hashes and passed without mutating the prepared v3 evidence.

## Debug -> First-Principles Refactoring -> Simplification

### Debug

The live environment exposed two assumptions hidden by local tests: Windows OpenSSH needs `PROGRAMDATA` in a deliberately minimal environment, and the remote base Python is 3.10.8. It also proved that canonical worker JSON is multi-line. Each issue failed before an unsafe relaunch; evidence was preserved and the next attempt used a new local result root and, after remote prepare existed, a new remote run ID.

### First-principles refactoring

The remote worker now uses `timezone.utc`, which expresses the required timezone without tying the dependency-free worker to Python 3.11. The transport parses the complete controlled stdout JSON document. Neither change introduces a compatibility branch.

### Simplification

Qualification uses the same production backend and worker as future experiments. Disconnect simulation is a thin injected transport decorator; there is no alternate remote launch implementation or test-only remote shell path.
