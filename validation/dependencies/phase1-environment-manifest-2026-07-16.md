# Phase 1 Orchestration Environment Manifest

- Date: 2026-07-16
- Environment: `pinn_strategy_orchestrator`
- Interpreter: `C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator\python.exe`
- Python: `3.11.15` (conda-forge, 64-bit)
- Platform: `Windows-10-10.0.26200-SP0`
- Machine: `AMD64`
- Training environment boundary: `C:\Users\Mli\.conda\envs\pytorch2.3.1` remains separate and was not targeted by installation

## Approved Phase 1 top-level pins

| Package | Installed version |
| --- | ---: |
| `mlflow` | `3.14.0` |
| `qdrant-client` | `1.18.0` |
| `fastembed` | `0.8.0` |
| `psutil` | `7.2.2` |

## Preserved Phase 0 pins

| Package | Installed version |
| --- | ---: |
| `langgraph` | `1.2.9` |
| `langgraph-checkpoint-sqlite` | `3.1.0` |
| `pydantic` | `2.13.4` |
| `pint` | `0.25.3` |
| `numpy` | `2.4.6` |
| `scipy` | `1.17.1` |

## Verification

- Resolver-only dry run: passed; report `phase1-pip-dry-run-2026-07-16.json`.
- Exact package installation: passed; log `phase1-pip-install-2026-07-16.log`.
- `python -m pip check`: passed with no broken requirements.
- Import smoke: all ten approved Phase 0 and Phase 1 packages imported successfully.
- Orchestrator regression: 82 tests passed.
- Legacy MCP regression: 20 tests passed using
  `python -m unittest discover -s mcp-server/tests -t mcp-server -v`.
- OpenSpec strict validation: passed.
- Complete installed set: `phase1-pip-freeze-2026-07-16.txt`.

No FastEmbed model object was instantiated, no Qwen3 weights were downloaded,
and no MLflow server, Qdrant server, training process or smoke experiment was
started.

FastEmbed 0.8.0 catalog inspection returned zero Qwen entries for both dense
embedding and cross-encoder reranking. This package installation therefore
does not establish Qwen3 runtime compatibility.
