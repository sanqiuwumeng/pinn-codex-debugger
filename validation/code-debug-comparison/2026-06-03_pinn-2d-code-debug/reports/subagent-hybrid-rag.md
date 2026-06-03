# Hybrid-RAG Code Debug Subagent

## Raw Result

Scheme: `hybrid-rag`

Diagnosis: the boundary section was retrieval-biased because the case packet says hard constraints pass. The agent re-ranked by case facts and chose a minimal collocation sampling change for early phase-interface/local coverage.

Files changed:

- `workspaces/hybrid-rag/pinn_model.py`
- Backup: `workspaces/hybrid-rag/pinn_model.py_backup_2026-06-03`

Commands:

```powershell
conda run -n pytorch2.3.1 python -c "import sys, torch; print(sys.executable); print(torch.__version__); print(torch.cuda.is_available())"
conda run -n pytorch2.3.1 python .\run_benchmark.py --mode smoke --output-tag hybrid_before_smoke
Copy-Item -LiteralPath '.\pinn_model.py' -Destination '.\pinn_model.py_backup_2026-06-03' -Force
conda run -n pytorch2.3.1 python -m py_compile .\config.py .\physics.py .\pinn_model.py .\metrics.py .\fem_solver.py .\visualization.py .\run_benchmark.py
conda run -n pytorch2.3.1 python .\run_benchmark.py --mode smoke --output-tag hybrid_after_smoke
conda run -n pytorch2.3.1 python .\run_benchmark.py --mode full --output-tag hybrid_after_full
conda run -n pytorch2.3.1 python .\run_benchmark.py --mode full --output-tag hybrid_after_full_focus25
conda run -n pytorch2.3.1 python .\run_benchmark.py --mode full --output-tag hybrid_after_full_focus12
```

Before full baseline:

- full-field relative L2: `0.0582468338`
- full-field MAE: `12.2296817 K`
- full-field max error: `279.4650854 K`
- `t=5.0` relative L2: `0.1186936363`
- `t=5.0` melted-area relative error: `0.4666666667`
- `t=5.0` liquid-mask IoU: `0.6818181818`

Final full result, `hybrid_after_full_focus12`:

- full-field relative L2: `0.0496008712`
- full-field MAE: `13.2208330 K`
- full-field max error: `122.4855631 K`
- `t=5.0` relative L2: `0.0887409617`
- `t=5.0` melted-area relative error: `0.0`
- `t=5.0` liquid-mask IoU: `1.0`
- `t=5.0` interface mean distance: `0.0`
- `t=5.0` interface Hausdorff distance: `0.0`

Patch summary:

- Changed `sample_fixed_collocation` from fully uniform sampling to deterministic stratified sampling.
- `7/8` points remain uniform.
- `1/8` points focus near early heating: center `x`, top-biased `y`, triangular `t` around `5 s` within `0-10 s`.

Assessment:

- Best overall full-training result.
- Improved target relative L2, melted-area error, liquid-mask IoU, interface distance, full-field L2, and full-field max error.
- Regressed full-field MAE and `t=5.0` MAE slightly.
