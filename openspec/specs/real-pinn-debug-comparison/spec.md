# real-pinn-debug-comparison Specification

## Purpose
TBD - created by archiving change compare-generation-protocol-and-real-pinn-debug. Update Purpose after archive.
## Requirements
### Requirement: Real PINN case is evaluated read-only
The real-case comparison SHALL inspect `skill_test\PINN-2D` without modifying model code, weights, generated outputs, logs, figures, or data files.

#### Scenario: Case packet is built
- **WHEN** the evaluator prepares the real PINN debugging packet
- **THEN** it copies or summarizes existing evidence into validation artifacts without changing the source case directory

### Requirement: Three scheme agents are isolated
The real-case comparison SHALL run separate agents for `skill-only`, `rules-mcp`, and `hybrid-rag` with no cross-agent leakage before reports are frozen.

#### Scenario: Subagents are launched
- **WHEN** the controller starts the three debugging agents
- **THEN** each agent receives the same case packet, same output contract, and no other agent's conclusions

### Requirement: Real-case variables are controlled
The real-case comparison SHALL keep prompt content, evidence packet, time or token budget, allowed actions, and output schema aligned across the three agents.

#### Scenario: Agent reports are compared
- **WHEN** the evaluator reviews the three reports
- **THEN** differences can be attributed primarily to scheme context rather than different evidence or instructions

### Requirement: Real-case scoring uses evidence discipline
The real-case comparison SHALL score each scheme by evidence use, diagnostic prioritization, one-step recommendation, expected metric, rollback condition, handbook traceability, and read-only discipline.

#### Scenario: A real-case report is scored
- **WHEN** an agent submits its PINN-2D diagnosis
- **THEN** the score explains how the report handled validated constraints, dominant error metrics, next-step discipline, and source evidence

### Requirement: Mixed report separates both rounds
The final comparison SHALL mix Round 1 and Round 2 results in one report while keeping their meanings separate.

#### Scenario: Final report is produced
- **WHEN** both rounds finish
- **THEN** the report distinguishes blind answer quality from practical real-case debugging usefulness
