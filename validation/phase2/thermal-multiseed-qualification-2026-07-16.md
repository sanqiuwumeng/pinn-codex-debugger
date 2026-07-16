# Thermal Focused-Collocation Multi-Seed Qualification

Date: 2026-07-16  
Status: `PASS_WITH_ONE_SCIENTIFIC_REJECTION_RETAINED`

## Frozen design

- Seeds were fixed in advance as `7`, `42`, and `2026`.
- Seed 42 reuses the immutable governed full-run evidence. Seeds 7 and 2026
  were independently trained for 3000 epochs with 20000 collocation points.
- Only the reproducibility seed varied across focused-candidate runs. The
  physical model, SI unit contract, network, optimizer, schedule, FEM test
  reference, evaluation grid and 12.5% focused-collocation intervention stayed
  fixed.
- The case-specific user-confirmed decision policy stayed lexicographic
  `max_abs -> RMSE`; MAE could regress by no more than both 1.0 K and 10%.
- Each candidate was compared with the same immutable uniform seed-42
  baseline. This quantifies focused-candidate seed uncertainty; it is not a
  paired uniform-baseline seed study and must not be reported as one.

## Per-seed evidence

| Seed | max_abs (K) | RMSE (K) | MAE (K) | MAE regression | Maximum location `(t,x,y)` | Decision |
|---:|---:|---:|---:|---:|---|---|
| 7 | 112.5024 | 20.9374 | 13.1987 | 0.9690 K / 7.92% | `(5.0, 0.0, 0.0941667)` | ACCEPT |
| 42 | 122.4856 | 21.4118 | 13.2208 | 0.9912 K / 8.10% | `(5.0, 0.0, 0.0941667)` | ACCEPT |
| 2026 | 116.0018 | 21.3209 | 13.3850 | 1.1553 K / 9.45% | `(5.0, 0.0008333, 0.0941667)` | REJECT |

Seed 2026 improved the first primary (`max_abs`) by 163.4633 K and RMSE by
3.8231 K against the common baseline, but violated the absolute MAE guardrail
by 0.1553 K. It was therefore rejected even though its relative MAE regression
remained below 10%. No seed was omitted or rerun based on its scientific
result.

## Localization and uncertainty

All candidate maxima remain at `t=5.0` near the top center (`y=0.0941667` and
`|x| <= 0.0008333`). The comparison service did not flag maximum-error
migration for any seed. The intervention's effect is therefore consistently
localized in this case, but its global MAE trade-off is seed-sensitive.

Across all three focused candidates:

| Metric | Mean | Sample std | Min | Max |
|---|---:|---:|---:|---:|
| max_abs (K) | 116.9966 | 5.0654 | 112.5024 | 122.4856 |
| RMSE (K) | 21.2234 | 0.2518 | 20.9374 | 21.4118 |
| MAE (K) | 13.2682 | 0.1017 | 13.1987 | 13.3850 |

The acceptance rate is 2/3 under the frozen contract. The defensible
conclusion is not that focused collocation is universally superior, but that
it robustly reduced the localized maximum for these three seeds while one seed
crossed the independently governed MAE absolute guardrail.

## Execution, replay and failure modes

- Every scientific seed process completed, produced the complete artifact set,
  preserved the source-case hashes and passed manifest-first zero-relaunch
  replay.
- Seed 7 attempt 1 stopped before process launch because the adapter had not
  provisioned its backend directory. The failed pre-launch evidence was
  preserved. Attempt 2 changed only that adapter initialization defect and is
  the explicitly referenced seed-7 run.
- Seed 2026 is a scientific rejection, not an execution failure. Its complete
  artifacts, local maximum and guardrail reason remain in the aggregate.
- The training environment was Python 3.11.11, PyTorch 2.3.1, NumPy 2.2.5,
  SciPy 1.15.3 and Matplotlib 3.10.1, with CPU execution.

## Governed evidence

Large artifacts remain in the ignored artifact area and are addressed by
SHA-256:

- Aggregate: `validation/phase2/results/thermal-multiseed-20260716/thermal-multiseed-aggregate.json`  
  `a8ce657e6efb3e2f4e958c461acc369bb3d8dead1d9d107e9c2c1f30330ae4fd`
- Seed 7 qualified attempt: `validation/phase2/results/thermal-multiseed-20260716/seed-7-attempt2/seed-execution-report.json`  
  `e45aa9be8273bf6942537b2d2441bb0858618807688e82e25236d34db009609f`
- Seed 42 prior full evidence: `validation/full/results/pinn2d-focused-full-repro-20260716/full-execution-report.json`  
  `02c3455ca31410808a5705fe3298b422067fc7ffef674ddb155ddf10ffe474a0`
- Seed 2026: `validation/phase2/results/thermal-multiseed-20260716/seed-2026-attempt1/seed-execution-report.json`  
  `e716a1099fea253e877bdb2342ee952748903bf7db7e3411f94b70da65988111`
