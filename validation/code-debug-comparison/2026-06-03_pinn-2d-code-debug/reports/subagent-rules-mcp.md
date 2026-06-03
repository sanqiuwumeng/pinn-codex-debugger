# Rules-MCP Code Debug Subagent

## Raw Result

Scheme: `rules-mcp`

Diagnosis: the structured retrieval weakness was `underspecified`, but the case evidence identified early over-melting at `t=5.0`. The agent investigated a smaller logical code point: the hard-constraint lifting profile, where `eta**2` may pre-fill the top heating too deeply.

Files changed:

- `workspaces/rules-mcp/pinn_model.py`
- Backup: `workspaces/rules-mcp/pinn_model.py_backup_2026-06-03`

Commands:

```powershell
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag rules_mcp_before
Copy-Item -LiteralPath '...\pinn_model.py' -Destination '...\pinn_model.py_backup_2026-06-03'
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag rules_mcp_after
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag rules_mcp_after_v2
conda run -n pytorch2.3.1 python run_benchmark.py --mode smoke --output-tag rules_mcp_after_v3
```

Comparable smoke before:

- full-field relative L2: `1.0135341851`
- `t=5.0` relative L2: `0.8041827856`
- `t=5.0` melted-area relative error: `0.3333333333`
- `t=5.0` liquid-mask IoU: `0.75`
- `t=40.0` relative L2: `1.4099441764`

Final smoke after:

- full-field relative L2: `1.0123643005`
- `t=5.0` relative L2: `0.5437261331`
- `t=5.0` melted-area relative error: `0.0`
- `t=5.0` liquid-mask IoU: `1.0`
- `t=40.0` relative L2: `1.5450008641`

Patch summary:

```python
eta_profile = eta**4
base = initial + delta * ramp * shape * eta_profile
correction = delta * tau * (1.0 - eta_profile) * raw
```

Assessment:

- Improved smoke early-interface metrics.
- Regressed late-time smoke relative L2 and full-field max error.
- Not directly comparable to full-training results from the other two schemes.
