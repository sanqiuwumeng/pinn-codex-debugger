## 1. Skill Scaffold

- [x] 1.1 Initialize `skills/pinn-debugging-assistant/` with the standard Codex skill scaffold and UI metadata.
- [x] 1.2 Write a concise trigger description covering PINN code debugging, training failures, residual anomalies, boundary and initial-condition problems, loss imbalance, module selection, and experiment planning.
- [x] 1.3 Verify that the scaffold contains only the directories required by this baseline.

## 2. Handbook Packaging

- [x] 2.1 Copy the repository-root Markdown handbook into `skills/pinn-debugging-assistant/references/` without modifying the source file.
- [x] 2.2 Compute SHA256 for the source handbook and packaged handbook copy, verify they match, and record the verified hash in the implementation summary.
- [x] 2.3 Create `references/routing-index.md` with symptom families, mandatory basic-check order, useful `rg` search anchors, and the required diagnostic response format.

## 3. Skill Workflow

- [x] 3.1 Write `SKILL.md` so Codex reads the routing index first and searches the full handbook only for relevant details.
- [x] 3.2 Encode the symptom-first workflow: describe the symptom, inspect evidence, complete relevant basic checks, propose one logical intervention, define expected metric improvement, define rollback, and cite the handbook anchor.
- [x] 3.3 Add conservative handling for vague symptoms and missing evidence.
- [x] 3.4 Explicitly exclude MCP, databases, embeddings, external APIs, custom runtime scripts, and package installation from this baseline.

## 4. Evaluation Fixtures

- [x] 4.1 Create `evals/cases.jsonl` with representative symptom prompts for boundary failure, late-time divergence, local residual hotspots, high-frequency smoothing, inverse-parameter drift, conservation drift, high-order PDE instability, repeated parametric solves, and underspecified failure.
- [x] 4.2 Create `evals/rubric.md` scoring symptom classification, basic-check discipline, one-change discipline, metric and rollback quality, handbook traceability, and conservative handling of uncertainty.
- [x] 4.3 Verify that evaluation fixtures are generic enough to reuse unchanged in the `rules-mcp` and `hybrid-rag` branches.

## 5. Validation

- [x] 5.1 Run the Codex skill validator against `skills/pinn-debugging-assistant/`.
- [x] 5.2 Confirm that no conda environment, MCP configuration, personal Codex skill directory, or source handbook file was modified.
- [x] 5.3 Run a manual baseline pass over the evaluation fixtures and record observations without adding branch-specific retrieval enhancements.
- [x] 5.4 Review the implementation against the specification and summarize known retrieval misses for later branch comparison.

## 6. Installation Decision

- [x] 6.1 Present the validated repo-owned skill and baseline evaluation results for user review.
- [x] 6.2 Install or package the skill for Codex App only after explicit user approval.
