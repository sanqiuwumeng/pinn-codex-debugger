# Remote Wiki + Qwen RAG + Poisson qualification

This directory contains credential-free, reproducible entry points for an
operator-approved remote end-to-end qualification.

1. `build_remote_inputs.py` reads the governed knowledge candidate and explicit
   Wiki, metric-priority and experiment approvals; it verifies every referenced
   artifact, copies only those evidence files, and rewrites their URIs for the
   declared remote input root.
2. `run_remote_full_chain.py` validates the source archive and input manifests,
   executes a real CUDA kernel, calls MCP diagnosis and project adaptation,
   formally publishes the Wiki, rebuilds and queries Qdrant through the pinned
   Qwen3 providers, runs an independent Poisson qualification, verifies replay,
   scans results for credential markers, and emits `completion-manifest.json`
   plus `FULL_CHAIN_PASS`.

The main runner is designed for a detached one-shot `nohup` launch with an
external log, PID file and status file. It contains no endpoint, username,
password, key path or persistent SSH configuration. Formal results must not be
transferred until the external status is zero and both completion files exist.
