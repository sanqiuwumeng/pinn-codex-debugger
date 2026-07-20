# Universal PINN governed-loop example

This example is domain-neutral. Replace every `C:/ABSOLUTE/...` value and every
placeholder hash. Never copy its metric policy into a real case without user
confirmation.

## 1. Quick read-only diagnosis

Copy and edit the MCP runtime/environment examples, then run:

```powershell
conda activate pinn_strategy_orchestrator
pinn-strategy diagnose `
  --runtime-root 'C:/ABSOLUTE/RUNTIME' `
  --project-id 'my-pinn-project' `
  --query 'local maximum error remains near a boundary' `
  --mcp-profile 'C:/ABSOLUTE/mcp-runtime-profile.json' `
  --json
```

The MCP evidence is advisory and does not satisfy physical, metric or execution
approvals.

## 2. Generate and audit the governance case

Edit `project-adapter-manifest.example.json`. Its `include_files` are relative
to `project_root` and must resolve inside that root.

```powershell
pinn-strategy adapt --runtime-root 'C:/ABSOLUTE/RUNTIME' --manifest 'C:/ABSOLUTE/project-adapter-manifest.json' --output 'C:/ABSOLUTE/operator-case.json' --json
pinn-strategy audit --runtime-root 'C:/ABSOLUTE/RUNTIME' --case 'C:/ABSOLUTE/operator-case.json' --json
pinn-strategy plan  --runtime-root 'C:/ABSOLUTE/RUNTIME' --case 'C:/ABSOLUTE/operator-case.json' --json
```

Resolve every reported input in the generated case: confirm the physical model
and internally consistent units, ask the user for metric priority, attach
baseline localization, declare one intervention, and add scoped approvals.

## 3. Execute and collect

After the graph reaches `SMOKE_APPROVED`:

```powershell
pinn-strategy smoke   --runtime-root 'C:/ABSOLUTE/RUNTIME' --workflow 'universal-example-workflow' --json
pinn-strategy status  --runtime-root 'C:/ABSOLUTE/RUNTIME' --workflow 'universal-example-workflow' --json
pinn-strategy collect --runtime-root 'C:/ABSOLUTE/RUNTIME' --workflow 'universal-example-workflow' --destination 'C:/ABSOLUTE/COLLECTED' --json
```

The training script exports declared artifacts. Each evaluator NPZ descriptor
names the field values, every coordinate array, optional context fields and ROI
masks. Baseline, candidate and reference must share axes, coordinates, reference
identity, unit, coordinate system and normalization.

## 4. Analyze before deciding

Edit `post-run-evaluation.example.json` with collected hashes and the confirmed
metric contract:

```powershell
pinn-strategy evaluate --runtime-root 'C:/ABSOLUTE/RUNTIME' --contract 'C:/ABSOLUTE/post-run-evaluation.json' --json
```

The response exposes `max_abs_before_decision`. Coordinate mismatch produces
`RESULT_INVALID`. `DECISION_ACCEPTED` only means the metric policy passed; the
case adapter must still validate process exit, required artifacts, source/data/
environment identities and reproducibility before smoke is marked valid.

Qwen3 vector retrieval remains available through `rag rebuild` and `rag query`
when Qdrant and the isolated model profile are configured. Retrieval evidence
never replaces deterministic assurance gates.
