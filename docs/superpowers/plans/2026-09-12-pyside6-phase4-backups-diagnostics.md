# PySide6 Phase 4 Backups and Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate manual backup/restore and operator diagnostics into real PySide6 workflows without changing the existing backup format, restore safety guarantees, SQLite schema, production Tkinter entrypoint, or release pipeline.

**Architecture:** Keep `getpass_core.backup` as the single implementation of archive creation, inspection, checksum/integrity validation and rollback. Add UI-independent application projections/services, then thin Qt ViewModels/pages that run archive and SQLite integrity work through the reusable `TaskWorker`/`QThreadPool` introduced by the batch slice. Restore remains explicitly inspect → confirm → restore; diagnostics is a read-only snapshot.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.2, SQLite, existing `getpass_core.backup`, MVVM-lite, `QThreadPool`/`QRunnable`, pytest/pytest-qt.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Preserve `getpass_core` Qt independence.
- Do not change backup archive formats, checksum rules, restore allow-list, SQLite integrity validation or rollback semantics.
- `.gupbak` remains password-protected; `.zip` remains unencrypted and must be clearly labeled as containing personal data.
- Archive creation, inspection, restore and SQLite integrity checks must not run on the GUI thread.
- Production entrypoint remains `pass_generator.py`/Tkinter until Phase 5.
- No SQLite schema/migration, renderer, blank, font, asset, production installer or release-pipeline changes.
- Qt self-test must not create, inspect or restore real user backups and must not mutate production data.

---

### Task 1: Application backup and diagnostics boundaries

**Files:**
- Create: `getpass_app/models/backup.py`
- Create: `getpass_app/models/diagnostics.py`
- Create: `getpass_app/services/backup_service.py`
- Create: `getpass_app/services/diagnostics_service.py`
- Test: `tests/test_backup_application.py`
- Test: `tests/test_diagnostics_application.py`

**Interfaces:**
- `BackupInspection(path: str, accepted: tuple[str, ...], skipped: tuple[str, ...], encrypted: bool)`
- `BackupCreated(path: str, file_count: int, byte_count: int, encrypted: bool)`
- `BackupRestored(path: str, restored_count: int, skipped: tuple[str, ...])`
- `BackupService.create(path: str, password: str | None) -> BackupCreated`
- `BackupService.inspect(path: str, password: str | None) -> BackupInspection`
- `BackupService.restore(path: str, password: str | None) -> BackupRestored`
- `DiagnosticsSnapshot` contains Python version, data/database/backup paths, DB size text/value, SQLite integrity result and up to ten recent automatic backup names.
- `DiagnosticsService.snapshot() -> DiagnosticsSnapshot`

- [ ] **Step 1: Write RED tests for application projections and service delegation.** Verify `.gupbak` password forwarding, ZIP/no-password behavior, accepted/skipped preservation, restore result projection, missing DB handling, SQLite integrity success/error and newest-first backup listing limited to ten.
- [ ] **Step 2: Run the new application tests and verify failure is caused by missing application modules/APIs.**
- [ ] **Step 3: Implement minimal immutable models and injectable services around existing core APIs and filesystem/SQLite reads.**
- [ ] **Step 4: Run strict lint/C901 and the full suite; require GREEN before adding Qt state.**
- [ ] **Step 5: Commit the application boundary.**

### Task 2: Qt ViewModels with background work

**Files:**
- Create: `getpass_qt/viewmodels/backups_viewmodel.py`
- Create: `getpass_qt/viewmodels/diagnostics_viewmodel.py`
- Reuse: `getpass_qt/workers/task_worker.py`
- Test: `tests/test_qt_backups_viewmodel.py`
- Test: `tests/test_qt_diagnostics_viewmodel.py`

**Interfaces:**
- `BackupsViewModel.inspect(path, password) -> bool` dispatches a worker and emits `inspection_ready`.
- `BackupsViewModel.create(path, password) -> bool` dispatches a worker and emits `backup_created`.
- `BackupsViewModel.restore(path, password) -> bool` is allowed only for the currently inspected path/password pair and emits `backup_restored`.
- `BackupsViewModel` exposes `busy_changed`, `operation_failed` and `cancel()`; restore never proceeds merely because a file was selected.
- `DiagnosticsViewModel.refresh() -> bool` dispatches `DiagnosticsService.snapshot()` and emits `snapshot_changed`/`operation_failed`.

- [ ] **Step 1: Write RED tests proving create/inspect/restore/diagnostics use the injected thread pool and never execute eagerly in the caller.**
- [ ] **Step 2: Verify RED is caused by missing ViewModel APIs.**
- [ ] **Step 3: Implement minimal ViewModels using `TaskWorker`; invalidate a prior inspection whenever path/password changes or an operation fails.**
- [ ] **Step 4: Run full suite + lint/C901 and require GREEN.**
- [ ] **Step 5: Commit Qt state/orchestration.**

### Task 3: Real Backups and Diagnostics pages/routes

**Files:**
- Create: `getpass_qt/views/backups.py`
- Create: `getpass_qt/views/diagnostics.py`
- Modify: `getpass_qt/main_window.py`
- Modify: `getpass_qt/app.py`
- Test: `tests/test_qt_backups_page.py`
- Test: `tests/test_qt_diagnostics_page.py`
- Modify: `tests/test_qt_navigation.py`
- Modify: `tests/test_qt_entrypoint.py`

**Interfaces:**
- Backups page offers protected `.gupbak` creation, explicit unencrypted ZIP creation, archive selection/inspection, accepted/skipped summary, destructive restore confirmation and restart-required success copy.
- Diagnostics page renders the immutable snapshot and has a refresh action; no direct SQLite/filesystem logic in widgets.
- `backups` and `diagnostics` become real routes; `settings` remains a migration placeholder.
- Self-test uses fake application services and visits both routes without touching user files or SQLite.

- [ ] **Step 1: Write RED widget/navigation/self-test contracts using injected dialog callbacks so tests never open native dialogs.**
- [ ] **Step 2: Verify RED is caused by missing pages/routes/wiring.**
- [ ] **Step 3: Implement the pages, route wiring and safe self-test services.**
- [ ] **Step 4: Run full Linux matrix checks and require GREEN.**
- [ ] **Step 5: Commit the real routes.**

### Task 4: Documentation and final verification

**Files:**
- Modify: `README.md`
- Update PR description after CI.

- [ ] **Step 1: Update only migration/status text: real routes become vehicle, employee, batch, journals, unfinished operations, backups and diagnostics; settings remains pending.**
- [ ] **Step 2: Audit isolated diff against the batch head to ensure no `getpass_core`, schema, renderer, production entrypoint or workflow changes were introduced.**
- [ ] **Step 3: Run/verify Python 3.13 + 3.14 strict lint/C901/full pytest/coverage/pip-audit/Bandit, Security (gitleaks + CodeQL), and Windows PR smoke including source/packaged Qt self-test and installer install/self-test/uninstall.**
- [ ] **Step 4: Check PR reviews/threads/comments; fix Important/Critical findings before declaring review-ready.**
- [ ] **Step 5: Keep the PR draft while it is stacked on unmerged predecessors; do not merge without an explicit user decision.**
