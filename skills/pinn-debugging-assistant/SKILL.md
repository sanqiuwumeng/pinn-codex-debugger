---
name: pinn-debugging-assistant
description: Diagnose Physics-Informed Neural Network (PINN) code and training failures with handbook-grounded checks. Use when Codex needs to investigate PINN loss curves, PDE residuals, boundary or initial-condition errors, scaling, sampling, optimization instability, late-time divergence, inverse-parameter drift, conservation errors, architecture choices, module selection, ablation plans, or a request to improve a PINN implementation.
---

# PINN Debugging Assistant

Use a symptom-first workflow. Do not recommend a new module before checking whether the current evidence supports it.

## Retrieve Guidance

1. Read [routing-index.md](references/routing-index.md).
2. Identify the closest symptom family and the required basic checks.
3. Search [PINN报错诊断与模块选择手册.md](references/PINN报错诊断与模块选择手册.md) with `rg -n` for the relevant heading, symptom, metric, and module.
4. Read only the matching handbook sections. Do not load the full handbook unless the request genuinely spans many symptom families.

Useful command pattern:

```powershell
rg -n "边界|BC loss|硬约束|距离函数" "references/PINN报错诊断与模块选择手册.md"
```

## Diagnose

Follow this sequence:

1. State the observable symptom in one sentence.
2. List the evidence already available and the smallest missing evidence needed.
3. Run the relevant basic checks before discussing enhancement modules:
   - equation signs, variables, dimensions, and automatic differentiation;
   - boundary and initial-condition expressions, masks, points, and normals;
   - normalization, nondimensionalization, and residual scales;
   - sampling coverage and per-term losses;
   - optimizer, learning rate, numerical precision, seeds, and logs.
4. Recommend at most one logical change for the next experiment unless the user explicitly requests a comparison plan.
5. Name the metric expected to improve.
6. State a rollback condition and preserve a baseline.
7. Cite the handbook reference file and heading or search anchor.

Use this response shape:

```text
Symptom:
Evidence:
Basic checks:
Next single change:
Expected metric:
Rollback:
Handbook anchor:
```

## Handle Uncertainty

- If the user only reports that the result is bad, request concrete evidence such as per-term losses, residual heatmaps, boundary errors, time-slice errors, physical-quantity curves, seed, and configuration.
- If evidence conflicts, say that the diagnosis is provisional and identify the next observation needed.
- Do not treat a low total loss or low sampled residual as proof that the physical solution is correct.
- Do not stack modules in one experiment unless the user explicitly requests a staged comparison.

## Keep This Baseline Lightweight

Do not add or require MCP servers, databases, embeddings, external APIs, custom runtime scripts, background services, or package installation while using this baseline skill. Normal Codex file reading, `rg`, and shell inspection are sufficient.

## References

- Read [routing-index.md](references/routing-index.md) first for navigation and search anchors.
- Search [PINN报错诊断与模块选择手册.md](references/PINN报错诊断与模块选择手册.md) for detailed justification.
