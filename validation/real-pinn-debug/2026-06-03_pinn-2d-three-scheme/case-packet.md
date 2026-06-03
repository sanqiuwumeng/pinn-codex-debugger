# PINN-2D Read-Only Debug Case Packet

## Source Directory

- Path: `E:\vibe coding\pinn-codex-debugger.worktrees\skill_test\PINN-2D`
- Read-only rule: do not modify source, logs, outputs, figures, model weights, or data.

## User-Style Debug Prompt

PINN-2D phase-change benchmark: hard top/initial/Neumann constraints pass; full-field relative L2 is 5.824683e-02, mean absolute error is 12.2297 K, max absolute error is 279.465 K. Time-slice relative L2 is largest at t=5.0 with melted-area relative error 0.4667 and liquid-mask IoU 0.6818. Diagnose the dominant next debugging step without modifying or retraining the model.

## Benchmark Summary

# PINN-2D Ti-6Al-4V Phase-Change Benchmark

## Scenario

A 0.10 m x 0.10 m Ti-6Al-4V plate starts at 300 K. The top boundary receives a smooth central temperature distribution with a 2200 K peak; the left, right, and bottom boundaries are adiabatic.

## Material Model

The PINN and FEM share the same simplified phase-change model: constant density, heat capacity, and conductivity with a piecewise-linear liquid fraction between 1878 K and 1928 K. Latent heat is 286000 J/kg.

## Metrics

- Full-field relative L2: 5.824683e-02
- Full-field mean absolute error: 1.222968e+01 K
- Full-field max absolute error: 2.794651e+02 K
- PINN training time: 359.093 s
- PINN inference time: 0.052 s

## Validation

- FEM grid convergence passed: True
- Zero-latent PINN reduction max difference: 0.000000e+00
- Zero-latent FEM capacity reduction passed: True
- top_temperature_max_abs_error: 0.000000e+00
- initial_temperature_max_abs_error: 0.000000e+00
- bottom_neumann_max_abs_error: 0.000000e+00
- left_neumann_max_abs_error: 0.000000e+00
- right_neumann_max_abs_error: 1.541811e-16

## Notes

This run used `full` mode. Use `python run_benchmark.py --mode full` for the planned 3000-epoch, 20000-point benchmark. The smoke run is a closed-loop implementation check, not an accuracy claim.

## Field Metrics

```json
{
  "full_field_max_abs_error": 279.46508541759533,
  "full_field_mean_abs_error": 12.229681731893299,
  "full_field_relative_l2": 0.058246833812194816
}
```

## Closed-Loop Validation

```json
{
  "fem_grid_convergence_passed": true,
  "hard_constraints": {
    "bottom_neumann_max_abs_error": 0.0,
    "initial_temperature_max_abs_error": 0.0,
    "left_neumann_max_abs_error": 0.0,
    "right_neumann_max_abs_error": 1.5418106634484561e-16,
    "top_temperature_max_abs_error": 0.0
  },
  "zero_latent_fem": {
    "field_shape": [
      81,
      41,
      41
    ],
    "level": "coarse",
    "max_abs_capacity_error": 0.0,
    "passed": true,
    "solver_run_passed": true,
    "temperature_max": 2199.999996083808,
    "temperature_min": 299.99999999999983
  },
  "zero_latent_pinn_max_abs_difference": 0.0
}
```

## Worst Time Slice By Relative L2

```json
{
  "interface_hausdorff_distance": "0.0008333333333333248",
  "interface_mean_distance": "0.0003417333439698515",
  "liquid_mask_iou": "0.6818181818181818",
  "max_abs_error": "279.46508541759533",
  "mean_abs_error": "22.802570553301944",
  "melted_area_relative_error": "0.46666666666666673",
  "prediction_liquid_fraction_area_ratio": "0.0015026296018031556",
  "reference_liquid_fraction_area_ratio": "0.001024520183047606",
  "relative_l2": "0.11869363632087802",
  "time": "5.0"
}
```

## Time Slice Metrics

| time | relative_l2 | mean_abs_error | max_abs_error | melted_area_relative_error | liquid_mask_iou | interface_mean_distance | interface_hausdorff_distance | prediction_liquid_fraction_area_ratio | reference_liquid_fraction_area_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 5.0 | 0.11869363632087802 | 22.802570553301944 | 279.46508541759533 | 0.46666666666666673 | 0.6818181818181818 | 0.0003417333439698515 | 0.0008333333333333248 | 0.0015026296018031556 | 0.001024520183047606 |
| 10.0 | 0.05470627140102716 | 15.990255745632862 | 128.78315647435602 | 0.13953488372093015 | 0.8775510204081632 | 0.00021075392360327578 | 0.0008333333333333248 | 0.003346765931288846 | 0.002936957858069804 |
| 20.0 | 0.03266397837891329 | 11.228198371109581 | 63.13592946697918 | 0.19999999999999996 | 0.8333333333333334 | 0.00033952467613420484 | 0.0008333333333333387 | 0.004507888805409466 | 0.003756574004507889 |
| 40.0 | 0.03224425615130815 | 11.12738398942211 | 80.94946701844628 | 0.19696969696969707 | 0.8354430379746836 | 0.0003920447784129166 | 0.0008333333333333387 | 0.005395806297384059 | 0.004507888805409466 |

## Figure Inventory

- `outputs\full\figures\centerline_comparison_t000.0.png`
- `outputs\full\figures\centerline_comparison_t005.0.png`
- `outputs\full\figures\centerline_comparison_t010.0.png`
- `outputs\full\figures\centerline_comparison_t020.0.png`
- `outputs\full\figures\centerline_comparison_t040.0.png`
- `outputs\full\figures\fem_grid_convergence.png`
- `outputs\full\figures\melted_area_ratio.png`
- `outputs\full\figures\phase_comparison_t000.0.png`
- `outputs\full\figures\phase_comparison_t005.0.png`
- `outputs\full\figures\phase_comparison_t010.0.png`
- `outputs\full\figures\phase_comparison_t020.0.png`
- `outputs\full\figures\phase_comparison_t040.0.png`
- `outputs\full\figures\pinn_loss_stability.png`
- `outputs\full\figures\temperature_comparison_t000.0.png`
- `outputs\full\figures\temperature_comparison_t005.0.png`
- `outputs\full\figures\temperature_comparison_t010.0.png`
- `outputs\full\figures\temperature_comparison_t020.0.png`
- `outputs\full\figures\temperature_comparison_t040.0.png`
- `outputs\full\figures\top_boundary_heating_schematic.png`

## Source Inventory

- `config.py`
- `fem_solver.py`
- `metrics.py`
- `physics.py`
- `pinn_model.py`
- `run_benchmark.py`
- `visualization.py`
