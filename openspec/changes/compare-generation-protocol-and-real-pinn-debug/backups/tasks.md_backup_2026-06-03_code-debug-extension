## 1. Preconditions

- [x] 1.1 Confirm the target worktree is `exp/hybrid-rag`, review `git status`, and do not create new worktrees.
- [x] 1.2 Ask whether to create a conda sandbox before any implementation modifications or runner scripts are added.
- [x] 1.3 Confirm that `skill_test\PINN-2D` is read-only for this comparison unless the user later explicitly requests modifications.
- [x] 1.4 Back up every existing file before revision using the required date-suffixed backup format.

## 2. Round 1: Uniform Blind Answer Protocol

- [x] 2.1 Define the shared answer-generation protocol, prompt template, input schema, output schema, and scoring sheet.
- [x] 2.2 Build adapters that feed `skill-only`, `rules-mcp`, and `hybrid-rag` into the same generator contract without changing the frozen prompts.
- [x] 2.3 Run all nine frozen blind prompts for each scheme in isolated threads or reproducible records.
- [x] 2.4 Archive exact prompts, thread IDs, retrieval records, generated answers, and scoring notes.
- [x] 2.5 Report comparable `score / 90` results and explain remaining uncertainty.

## 3. Round 2: Real PINN-2D Controlled Debugging

- [x] 3.1 Build a read-only case packet from `skill_test\PINN-2D` summaries, metrics, logs, figures inventory, and relevant source inventory.
- [x] 3.2 Freeze one shared subagent prompt and output contract before starting any agent.
- [x] 3.3 Spawn three isolated subagents: `skill-only`, `rules-mcp`, and `hybrid-rag`, each with the same case packet and budget.
- [x] 3.4 Prevent cross-agent leakage by withholding other agents' outputs until all three reports are frozen.
- [x] 3.5 Score each real-case report with the fixed 10-point rubric and archive raw evidence.

## 4. Mixed Comparison Report

- [x] 4.1 Produce one report that keeps Round 1 and Round 2 metrics separate but comparable.
- [x] 4.2 Identify whether either structured scheme beats `skill-only` on end-to-end answer quality, real-case usefulness, or both.
- [x] 4.3 Record failure modes, prompt leakage checks, response concision, evidence traceability, and next-step discipline.
- [x] 4.4 Validate OpenSpec, review Git scope, and commit the proposal or implementation artifacts intentionally.
