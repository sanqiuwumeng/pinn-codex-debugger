# PINN Codex Debugger

PINN Codex Debugger is a local experiment repository for building and evaluating
assistant-side debugging support for Physics-Informed Neural Networks (PINNs).

The current branch, `exp/hybrid-rag`, contains three stages of work:

- `skill-only`: a handbook-backed Codex skill baseline.
- `rules-mcp`: a local stdio MCP server with deterministic symptom records and
  handbook evidence extraction.
- `hybrid-rag`: a deterministic hybrid retrieval layer that combines rules
  anchors, concept lexicons, token overlap, and character 3-gram ranking.

The repository is designed for traceable diagnosis rather than black-box
generation. Each retrieval result keeps source hashes, handbook headings, line
ranges, score parts, matched concepts, matched terms, and matched anchors.

## Status

As of 2026-06-03, `hybrid-rag` has passed the project validation gates and has
practical value as a PINN debugging assistant and candidate patch generator.

It should not yet be treated as an automatically deployable final fixer. The
best real-code experiment improved full-field L2 and interface metrics, but
left a small MAE regression that should be checked with repeat runs before
promoting the candidate patch into production code.

## Main Results

| Evaluation | `skill-only` | `rules-mcp` | `hybrid-rag` |
| --- | ---: | ---: | ---: |
| Frozen nine-family blind suite | `86 / 90` | `90 / 90` through protocol adapter | `90 / 90` through protocol adapter |
| Frozen family routing | n/a | `9 / 9` | `9 / 9` |
| Paraphrase retrieval | n/a | n/a | `9 / 9` family and `9 / 9` expected top heading |
| Real PINN-2D read-only diagnosis | `10 / 10` | `10 / 10` | `10 / 10` |
| Real PINN-2D code-debug round | Full run, over-focused | Smoke-only, useful but incomplete | Best comparable full run |

Best `hybrid-rag` code-debug result on the copied PINN-2D workspace:

| Metric | Baseline | `hybrid-rag` |
| --- | ---: | ---: |
| Full L2 | `0.05825` | `0.04960` |
| Full MAE K | `12.23` | `13.22` |
| Full max K | `279.47` | `122.49` |
| `t=5` L2 | `0.11869` | `0.08874` |
| `t=5` melted-area error | `0.4667` | `0.0000` |
| `t=5` IoU | `0.6818` | `1.0000` |

## Repository Layout

```text
.
|-- PINN报错诊断与模块选择手册.md
|-- mcp-server/
|   |-- rules_mcp/
|   |-- hybrid_rag/
|   |-- scripts/
|   `-- tests/
|-- openspec/
|   |-- specs/
|   `-- changes/archive/
|-- skills/
`-- validation/
    |-- blind-tests/
    |-- generation-comparison/
    |-- hybrid-rag/
    |-- real-pinn-debug/
    |-- code-debug-comparison/
    `-- mixed-comparison/
```

## Runtime

- Host: Windows 11
- Shell: PowerShell
- Python environment used during development: `pytorch2.3.1`
- Resolved Python path:
  `C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe`
- External package installation for the MCP and hybrid retrieval stages: none
- MCP transport: stdio JSON-RPC

## Run The MCP Server

```powershell
$env:PYTHONUTF8='1'
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\hybrid-rag\mcp-server'
& 'C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe' -m rules_mcp
```

The client must send `initialize`, then `notifications/initialized`, before
invoking tools. Each request and response is one UTF-8 JSON-RPC object per line.

Available tools:

- `diagnose_pinn_symptom`: classify an observable PINN symptom and return
  evidence gaps, required checks, candidate anchors, and traceable handbook
  matches.
- `search_pinn_handbook`: retrieve handbook sections with source hash and line
  ranges.

## Reproduce Key Checks

Run unit tests:

```powershell
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\hybrid-rag'
& 'C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe' -m unittest discover -s mcp-server\tests -t mcp-server
```

Run the hybrid retrieval replay:

```powershell
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\hybrid-rag'
& 'C:\Users\Mli\.conda\envs\pytorch2.3.1\python.exe' mcp-server\scripts\replay_hybrid_benchmark.py
```

Validate archived OpenSpec state:

```powershell
Set-Location 'E:\vibe coding\pinn-codex-debugger.worktrees\hybrid-rag'
openspec validate --all --strict
```

## Important Evidence Files

- `validation/hybrid-rag/2026-06-03_frozen-plus-paraphrase/summary.md`
- `validation/mixed-comparison/2026-06-03_generation-and-real-pinn-report.md`
- `validation/code-debug-comparison/2026-06-03_pinn-2d-code-debug/reports/summary.md`
- `openspec/specs/hybrid-rag-retrieval/spec.md`
- `openspec/specs/pinn-debug-generation-comparison/spec.md`
- `openspec/specs/real-pinn-debug-comparison/spec.md`

## Current Interpretation

`hybrid-rag` is the strongest scheme in this repository because it keeps the
deterministic traceability of `rules-mcp`, adds paraphrase-resilient retrieval,
and performed best in the full real-code PINN-2D debugging comparison.

The next engineering step is to promote the `hybrid-rag` 12.5% stratified
focused-sampling patch into a clean review branch only after a separate
apply/review step and at least one repeat run to check whether the observed MAE
regression is stable or seed-specific.
