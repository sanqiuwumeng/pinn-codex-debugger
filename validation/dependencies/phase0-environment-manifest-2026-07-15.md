# Phase 0 Orchestration Environment Manifest

- Date: 2026-07-15
- Environment: `pinn_strategy_orchestrator`
- Interpreter: `C:\Users\Mli\.conda\envs\pinn_strategy_orchestrator\python.exe`
- Python: `3.11.15` (conda-forge, 64-bit)
- Platform: `Windows-10-10.0.26200-SP0`
- Machine: `AMD64`
- Training environment boundary: `C:\Users\Mli\.conda\envs\pytorch2.3.1` remains separate and unchanged

## Approved top-level pins

| Package | Installed version |
| --- | ---: |
| `langgraph` | `1.2.9` |
| `langgraph-checkpoint-sqlite` | `3.1.0` |
| `pydantic` | `2.13.4` |
| `pint` | `0.25.3` |
| `numpy` | `2.4.6` |
| `scipy` | `1.17.1` |

## Verification

- `python -m pip check`: passed with no broken requirements.
- Import smoke: `langgraph`, `pydantic`, `pint`, `numpy`, `scipy`, and `aiosqlite` imported successfully.
- Legacy MCP regression: 20 tests passed from `mcp-server` using `python -m unittest discover -v`.
- Resolver report: `phase0-pip-dry-run-2026-07-15.json`.
- Complete installed set: `phase0-pip-freeze-2026-07-15.txt`.

`langsmith` is present only as a transitive `langchain-core` dependency. No hosted tracing service is configured or authorized.

The conda-provided `packaging` bootstrap entry contains a build-time local URL in `pip freeze`; it is recorded as observed evidence and is not a portable installation instruction.
