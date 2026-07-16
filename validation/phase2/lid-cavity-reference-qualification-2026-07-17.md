# Lid-Driven-Cavity Independent Reference Qualification

Date: 2026-07-17

Status: `PASS`

Case relationship: `SCIENTIFIC_PEER`

## Frozen case

- Steady two-dimensional incompressible Navier-Stokes equations.
- Dimensionless unit square, Reynolds number 100 and kinematic viscosity 0.01.
- Uniform top-lid velocity `u=1,v=0`; the other walls are no-slip, with the
  side-wall convention used at the two discontinuous top corners.
- Pressure is evaluated with a zero-mean gauge; pressure-gradient evidence is
  gauge invariant.

## Independent solver and convergence policy

The reference was computed with OpenFOAM-6 `icoFoam`, independently of the
PyTorch PINN worker. Uniform `32x32`, `64x64` and `128x128` grids were run to
dimensionless time 30. The evaluation field was interpolated onto a fixed
`65x65` grid.

The release gates were frozen before the formal solve:

1. all fields and derived metrics are finite;
2. final-interval temporal velocity `relative_l2 <= 0.005`;
3. successive grid difference decreases;
4. medium-to-fine velocity `relative_l2 <= 0.03`;
5. fine-grid combined Ghia centerline RMSE `<= 0.03`.

## Results

| Evidence | Result | Gate |
|---|---:|---:|
| `32 -> 64` velocity relative L2 | 0.03642429 | diagnostic |
| `64 -> 128` velocity relative L2 | 0.01904973 | <= 0.03 |
| successive-difference ratio | 0.52299523 | < 1 |
| fine final-interval temporal relative L2 | 0.00000076 | <= 0.005 |
| fine Ghia combined centerline RMSE | 0.00366335 | <= 0.03 |
| fine vertical-centerline `u` RMSE | 0.00238815 | diagnostic |
| fine horizontal-centerline `v` RMSE | 0.00459749 | diagnostic |

All frozen convergence and cross-validation checks passed. Ghia centerline
values are used only as an independent published cross-check; the grid-converged
OpenFOAM field is the test-case reference supplied to the PINN evaluation.

## Evidence and provenance

- Formal result root:
  `validation/phase2/results/ns-cavity-reference-20260717-attempt1`
- `reference_fields.npz` SHA-256:
  `d2f5bb3d2658e751b59f8a05fbf16ed15a1d4d71829677e57de9d839ed88dd95`
- `reference_convergence.json` SHA-256:
  `99e8fe51ce3f336ec20cf83b7ddc5357c3dd9c34da4c829e1a367be37021cc28`
- Solver source: `validation/phase2/ns_cavity/cavity_reference.py`
- Reproducible WSL launcher:
  `validation/phase2/ns_cavity/run_openfoam_reference.sh`
- Published cross-check: Ghia, Ghia and Shin, *Journal of Computational
  Physics* 48, 387-411 (1982), DOI `10.1016/0021-9991(82)90058-4`.

The earlier path preflight and missing-`pFinal` attempt were retained as
negative engineering evidence and were not substituted for the formal result.
