## ADDED Requirements

### Requirement: Existing release records are backed up before revision
The implementation MUST create a backup of each existing file before modifying it, using the filename format `original_filename_backup_YYYY-MM-DD`.

#### Scenario: Baseline result record is revised
- **WHEN** the existing baseline result record is updated with installation or blind-test information
- **THEN** a dated backup of the original record exists before the update is applied

### Requirement: Installed baseline state is recorded accurately
The baseline release record SHALL state whether the personal Skill is installed, whether its files match the repo-owned Skill, and whether isolated auto-trigger testing has been performed.

#### Scenario: Installed Skill matches the repository
- **WHEN** the personal Skill and repo-owned Skill produce matching per-file hashes
- **THEN** the release record reports the installation and the verified match

### Requirement: Handbook provenance remains unchanged
The source handbook and packaged handbook copy MUST remain byte-identical to the recorded baseline source hash.

#### Scenario: Baseline release validation runs
- **WHEN** provenance validation is executed
- **THEN** the source and packaged handbook copies match the recorded SHA256 and no handbook content is modified

### Requirement: Blind-test evidence is archived outside the portable Skill
The baseline release SHALL copy existing blind-test evidence into `validation/blind-tests/<YYYY-MM-DD>_<suite-name>/` and MUST NOT delete the original external evidence.

#### Scenario: Existing blind-test evidence is archived
- **WHEN** the boundary-focused blind-test run is incorporated into the baseline branch
- **THEN** exact prompts, thread IDs, responses, and summary records are present under `validation/blind-tests/` while the external source files remain intact

### Requirement: Baseline closeout is validated and committed intentionally
The baseline closeout SHALL run structural validation, provenance checks, evaluation-fixture parsing, and Git scope review before an intentional commit is created.

#### Scenario: Baseline closeout is ready to commit
- **WHEN** all baseline release checks pass
- **THEN** the commit contains only reviewed `skill-only` artifacts and records the validated baseline state
