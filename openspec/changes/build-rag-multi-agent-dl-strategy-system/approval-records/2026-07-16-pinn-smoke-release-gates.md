# PINN Smoke Release-Gate Approval

- Date: 2026-07-16
- User response: `Yes`
- Workflow: `universal-pinn-smoke-20260716`
- Scope: OpenSpec tasks 8.4 through 8.6

## Approved scope

This approval authorizes one smoke-only PINN validation case, deterministic
process monitoring, localized metric analysis, rollback evaluation, persisted
state replay, idempotency verification and an evidence-backed MVP report.

The case compares the original uniform collocation sampler with one isolated
intervention: 12.5 percent deterministic focused collocation near the early
top-center error region. Physics, network architecture, optimizer, epoch count,
FEM settings, seed and metric contract remain unchanged.

## Execution boundary

- Use the existing Python 3.11.11 / PyTorch 2.3.1 training environment.
- Use the separate `pinn_strategy_orchestrator` environment for orchestration.
- Preserve the source PINN case as read-only and stage isolated copies.
- Do not start a full run.
- Do not promote a rejected candidate.
- Preserve failed or partial smoke evidence and keep the baseline active.

## Remote boundary

The available AutoDL instance may be probed read-only. This approval does not
require creating a replacement remote PyTorch 2.3.1 environment when the exact
local smoke environment is sufficient. Credentials remain transient and must
not be written to repository artifacts.
