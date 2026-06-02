# PINN Debugging Assistant Blind Test

## Metadata

- Date: `2026-06-02`
- Skill under test: `pinn-debugging-assistant`
- Method: create three isolated Codex App threads without naming the Skill or exposing the acceptance criteria
- Expected behavior: automatically trigger the Skill, ask to inspect boundary expressions, boundary points, and loss weights first, then propose one next experiment instead of stacking modules

## Cases

| Case | Scenario | Thread ID | Auto-triggered | Single next experiment | Result |
| --- | --- | --- | --- | --- | --- |
| 01 | 1D Poisson endpoint error | `019e876e-89de-7fa2-b224-de1c627d93ac` | Yes | Yes | Pass with minor deviation |
| 02 | Heat equation initial/boundary error | `019e876e-8ff0-78e0-b506-ef7c17ee485b` | Yes | Yes | Pass with minor deviation |
| 03 | 2D rectangle edge/corner error | `019e876e-9580-7231-bb1e-46b1b35091a7` | Yes | Yes | Pass with minor deviation |

## Summary

The Skill auto-triggered in `3/3` isolated threads. All responses prioritized boundary conditions, boundary sampling points, and component losses or gradient weights. They also avoided recommending an immediate network architecture change and proposed only one first experiment.

The first response could still be tightened:

- Use a fixed initial request for the user's boundary expression, boundary-point generation code or scatter plot, and loss-weight configuration.
- Keep later candidate modules out of the first response unless needed to explain why they are deferred.
- Shorten the initial checklist before proposing the single experiment.

## Files

- `cases/01-poisson.md`
- `cases/02-heat-equation.md`
- `cases/03-rectangle-2d.md`

