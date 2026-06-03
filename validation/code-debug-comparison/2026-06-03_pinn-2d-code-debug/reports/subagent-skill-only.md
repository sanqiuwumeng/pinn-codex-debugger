# Skill-Only Code Debug Subagent

## Raw Result

Scheme: `skill-only`

Diagnosis: early phase-interface over-melting at `t=5.0`; hard constraints and zero-latent checks already passed. The agent chose one minimal sampling change rather than changing physics, model architecture, or loss formulation.

Files changed:

- `workspaces/skill-only/pinn_model.py`
- Backup: `workspaces/skill-only/pinn_model.py_backup_2026-06-03`

Commands:

```powershell
conda run -n pytorch2.3.1 python --version
conda run -n pytorch2.3.1 python -c "import torch; print(torch.__version__)"
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag skill_only_before_smoke
conda run -n pytorch2.3.1 python -m py_compile pinn_model.py run_benchmark.py
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag skill_only_after_smoke
conda run -n pytorch2.3.1 python run_benchmark.py --mode full --output-tag skill_only_after_full
```

Before full baseline:

- full-field relative L2: `0.0582468338`
- full-field MAE: `12.2296817 K`
- full-field max error: `279.4650854 K`
- `t=5.0` relative L2: `0.1186936363`
- `t=5.0` melted-area relative error: `0.4666666667`
- `t=5.0` liquid-mask IoU: `0.6818181818`

After full result:

- full-field relative L2: `0.0668905144`
- full-field MAE: `17.9911514 K`
- full-field max error: `154.3966707 K`
- `t=5.0` relative L2: `0.1202698572`
- `t=5.0` melted-area relative error: `0.2000000000`
- `t=5.0` liquid-mask IoU: `0.8333333333`

Patch summary:

- Changed `sample_fixed_collocation` from fully uniform sampling to `2/3` uniform plus `1/3` focused samples near top-center early melt region.

Assessment:

- Strongly improved interface geometry and max error.
- Regressed full-field L2, full-field MAE, and `t=5.0` relative L2.
