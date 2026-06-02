# PINN Debugging Assistant Nine-Family Blind Baseline

## Metadata

- Date: `2026-06-02`
- Branch: `exp/skill-only`
- Skill installation: personal Skill installed and matched to the repo-owned Skill before thread creation
- Method: create nine isolated projectless Codex App threads
- Prompt policy: send only the user-style symptom prompt; do not name the Skill, expected module, handbook anchor, or acceptance criteria

## Files

- `prompts.jsonl`: frozen blind prompts and hidden scoring family metadata
- `rubric.md`: frozen scoring rubric reused across branches
- `result-template.md`: required per-case archive fields
- `cases/`: exact prompt, thread ID, raw response, and scoring notes for each run
- `summary.md`: aggregate results and comparison metrics
