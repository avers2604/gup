# PySide6 Phase 4 Journals and Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PySide6 `journals` and `operations` migration placeholders with real Qt workflows while preserving existing SQLite data, journal semantics, durable issuance recovery and the Tkinter production fallback.

**Architecture:** Add UI-independent journal and recovery orchestration in `getpass_app`, then expose it through focused MVVM-lite ViewModels and Qt model/view tables. Reuse the existing `Journal`, `PASS_JOURNAL`, `BADGE_JOURNAL` and `issuance` APIs; do not change schema, renderer, issuance state transitions or production entry point. Qt owns dialogs, confirmations, file pickers and table presentation; application services own filtering, sorting, pagination, history, updates/revocation/export and pending-operation actions.

**Tech Stack:** Python 3.13/3.14, PySide6 6.11.x, existing `getpass_core`, SQLite, pytest, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Keep `pass_generator.py` as the production Tkinter entry point during this Phase 4 slice.
- Do not modify `getpass_core/render.py`, `getpass_core/blank.py`, `getpass_core/fonts.py`, assets, fonts or printed-document coordinates.
- Do not change SQLite schema or migrations.
- `getpass_core` and `getpass_app` must remain free of PySide6 imports.
- Use `QAbstractTableModel` / `QTableView`; do not reproduce Tkinter-style direct row manipulation.
- Preserve journal states: `active`, `expired`, `revoked`, `unknown` and the existing status labels.
- Preserve search, status/date filters, schema-specific filters, sorting, pagination, editing, history, revocation and XLSX export.
- Preserve optimistic edit protection by passing the previously read record as `expected` to `Journal.update_record()`.
- Preserve durable issuance recovery: only `prepared` jobs are listed; confirm and cancel continue to call `issuance.confirm()` / `issuance.cancel()`.
- Preserve the current document-status distinction: direct print, existing file, missing file.
- No blacklist-management page, batch printing, backup/restore, diagnostics or production cutover in this PR. Revocation may still offer the existing one-shot “add revoked records to blacklist” behavior through the core blacklist API.
- Use existing GET semantic theme tokens; no new ad-hoc color constants.

---

## File Map

**Create**
- `getpass_app/models/journal.py` — immutable query/snapshot/history data objects and pure state/filter/sort helpers.
- `getpass_app/services/journal_service.py` — adapters over vehicle/badge `Journal`, history, update/revoke, optional blacklist add and XLSX export.
- `getpass_app/models/operation.py` — immutable pending-operation projection.
- `getpass_app/services/operations_service.py` — pending/confirm/cancel/document-state orchestration across both journals.
- `getpass_qt/models/journal_table_model.py` — `QAbstractTableModel` for journal rows.
- `getpass_qt/models/operations_table_model.py` — `QAbstractTableModel` for pending issuance rows.
- `getpass_qt/viewmodels/journal_viewmodel.py` — journal route/filter/page/sort/action state.
- `getpass_qt/viewmodels/operations_viewmodel.py` — recovery list/action state.
- `getpass_qt/views/journals.py` — journals page plus edit/history dialogs.
- `getpass_qt/views/operations.py` — unfinished-operations page.
- `tests/test_journal_application.py`
- `tests/test_operations_application.py`
- `tests/test_qt_journal_viewmodel.py`
- `tests/test_qt_journal_table_model.py`
- `tests/test_qt_journals_page.py`
- `tests/test_qt_operations_viewmodel.py`
- `tests/test_qt_operations_table_model.py`
- `tests/test_qt_operations_page.py`

**Modify**
- `getpass_qt/main_window.py` — inject and install real `journals` / `operations` pages.
- `getpass_qt/app.py` — construct services/ViewModels and extend safe `--self-test`.
- `getpass_qt/theme/stylesheet.py` — semantic table/filter/action styling.
- `tests/test_qt_navigation.py`, `tests/test_qt_entrypoint.py`, `tests/test_qt_theme.py` — Phase 4 contracts.
- `README.md` — document the expanded Qt preview scope.

---

### Task 1: Journal application model and service

**Files:**
- Create: `getpass_app/models/journal.py`
- Create: `getpass_app/services/journal_service.py`
- Test: `tests/test_journal_application.py`

**Interfaces:**
- `JournalFilters(search="", status="active", date_from="", date_to="", extra=())`.
- `JournalSnapshot(journal_key, journal_name, schema, rows, total_records, filtered_records, page, page_size, page_count)`.
- `JournalHistoryEvent(occurred_at, actor, action, changes)`.
- `record_state(record, today) -> Literal["active", "expired", "revoked", "unknown"]`.
- `JournalService.snapshot(journal_key, filters, *, sort_key=None, sort_reverse=False, page=0, page_size=100)`.
- `JournalService.update_record(journal_key, record_id, values, expected)`.
- `JournalService.revoke(journal_key, ids, reason)`.
- `JournalService.history(journal_key, record_id)`.
- `JournalService.distinct(journal_key, key)`.
- `JournalService.export(journal_key, records, path)`.
- `JournalService.add_revoked_to_blacklist(journal_key, ids, reason)`.

- [ ] **Step 1: Write failing tests** proving state calculation, search/status/date/extra filtering, deterministic sorting, pagination, optimistic edit delegation, revocation, immutable history projection and export of exactly the supplied rows.
- [ ] **Step 2: Run RED**: `pytest tests/test_journal_application.py -v`; expect import/collection failure because the new modules do not exist.
- [ ] **Step 3: Implement minimal UI-independent model/service** using only existing core APIs. History reads `journal_events` with a short-lived connection and closes it in `finally`.
- [ ] **Step 4: Run GREEN**: `pytest tests/test_journal_application.py tests/test_storage.py tests/test_journal_window.py -v`.
- [ ] **Step 5: Commit**: `feat: add journal application service`.

---

### Task 2: Journal Qt models and ViewModel

**Files:**
- Create: `getpass_qt/models/journal_table_model.py`
- Create: `getpass_qt/viewmodels/journal_viewmodel.py`
- Test: `tests/test_qt_journal_table_model.py`
- Test: `tests/test_qt_journal_viewmodel.py`

**Interfaces:**
- `JournalTableModel(QAbstractTableModel)` consumes a `JournalSnapshot`; `Qt.UserRole` returns record id and `Qt.UserRole + 1` returns computed state.
- `JournalViewModel(QObject)` exposes `snapshot_changed`, `busy_changed`, `operation_succeeded`, `operation_failed`.
- Commands: `select_journal`, `set_search`, `set_status`, `set_date_range`, `set_extra_filter`, `sort_by`, `set_page`, `refresh`, `update_record`, `revoke`, `history`, `export`.

- [ ] **Step 1: Write failing tests** for headers/display values, row identity/state roles, default pass journal, filter reset to page zero, sort toggling, page clamping and service-error propagation.
- [ ] **Step 2: Run RED**: `pytest tests/test_qt_journal_table_model.py tests/test_qt_journal_viewmodel.py -v`.
- [ ] **Step 3: Implement minimal table model and ViewModel**; ViewModel stores plain filter state and never opens dialogs/files.
- [ ] **Step 4: Run GREEN** with the two test modules.
- [ ] **Step 5: Commit**: `feat: add Qt journal model and viewmodel`.

---

### Task 3: Journals page and dialogs

**Files:**
- Create: `getpass_qt/views/journals.py`
- Modify: `getpass_qt/theme/stylesheet.py`
- Test: `tests/test_qt_journals_page.py`
- Test: `tests/test_qt_theme.py`

**Interfaces:**
- `JournalsPage(QWidget)` contains journal selector, search, status/date filters, schema-specific filters, `QTableView`, page controls and Refresh/Edit/History/Revoke/Export actions.
- `EditJournalRecordDialog(QDialog)` edits non-protected schema fields and returns a values dict.
- `JournalHistoryDialog(QDialog)` shows immutable events and field changes.

- [ ] **Step 1: Write failing widget tests** for real `QTableView`, dynamic filters for vehicle/badge schemas, selection-to-edit/revoke commands, pagination controls and non-color-only state text.
- [ ] **Step 2: Run RED**: `pytest tests/test_qt_journals_page.py tests/test_qt_theme.py -v`.
- [ ] **Step 3: Implement page/dialogs**. Use Qt confirmations/file dialogs in the view; on revoke, optionally call the existing blacklist helper only after successful revocation.
- [ ] **Step 4: Run GREEN** with page/theme tests.
- [ ] **Step 5: Commit**: `feat: add PySide6 journals workflow`.

---

### Task 4: Pending-operations application service and Qt workflow

**Files:**
- Create: `getpass_app/models/operation.py`
- Create: `getpass_app/services/operations_service.py`
- Create: `getpass_qt/models/operations_table_model.py`
- Create: `getpass_qt/viewmodels/operations_viewmodel.py`
- Create: `getpass_qt/views/operations.py`
- Test: `tests/test_operations_application.py`
- Test: `tests/test_qt_operations_table_model.py`
- Test: `tests/test_qt_operations_viewmodel.py`
- Test: `tests/test_qt_operations_page.py`

**Interfaces:**
- `PendingOperation(id, journal_key, journal_name, created_at, destination, document_status, document_path)`.
- `OperationsService.pending() -> tuple[PendingOperation, ...]` combines both journals in created order.
- `OperationsService.confirm(ids)` and `.cancel(ids)` resolve each id back to its owning journal and delegate to issuance.
- Document status values are exact Russian UI labels: `Прямая печать`, `Файл готов`, `Файл не найден`.
- `OperationsTableModel(QAbstractTableModel)` exposes created/journal/destination/document columns and operation id in `Qt.UserRole`.
- `OperationsViewModel(QObject)` exposes `operations_changed`, `operation_succeeded`, `operation_failed`, plus `refresh`, `confirm`, `cancel`.
- `OperationsPage(QWidget)` offers Refresh/Open document/Cancel/Confirm with explicit confirmations for state-changing actions.

- [ ] **Step 1: Write failing application and Qt tests** for combined ordering, status classification, multi-id confirm/cancel, missing/direct-print handling, table roles and page button enablement.
- [ ] **Step 2: Run RED** for the four new operation test modules.
- [ ] **Step 3: Implement minimal service/model/ViewModel/page**; use `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` only for an existing document path.
- [ ] **Step 4: Run GREEN** plus `tests/test_issuance_recovery.py tests/test_reliability.py tests/test_reliability_regressions.py`.
- [ ] **Step 5: Commit**: `feat: add PySide6 unfinished operations workflow`.

---

### Task 5: Shell integration, self-test and documentation

**Files:**
- Modify: `getpass_qt/main_window.py`
- Modify: `getpass_qt/app.py`
- Modify: `tests/test_qt_navigation.py`
- Modify: `tests/test_qt_entrypoint.py`
- Modify: `README.md`

**Interfaces:**
- `MainWindow` receives `journal_viewmodel` and `operations_viewmodel` in addition to vehicle/employee ViewModels.
- `journals` and `operations` are removed from migration placeholders and installed as real pages.
- `--self-test` uses in-memory/fake services and exercises route switching/table construction without reading or mutating production SQLite.

- [ ] **Step 1: Write failing integration tests** asserting `JournalsPage` and `OperationsPage` occupy the two routes and the safe Qt self-test reaches both.
- [ ] **Step 2: Run RED** for navigation/entrypoint tests.
- [ ] **Step 3: Wire services/ViewModels/pages and update README**. Leave `batch`, `backup`, `diagnostics`, `settings` migration placeholders unchanged.
- [ ] **Step 4: Run focused GREEN**: `pytest tests/test_qt_navigation.py tests/test_qt_entrypoint.py tests/test_qt_journals_page.py tests/test_qt_operations_page.py -v`.
- [ ] **Step 5: Run full verification**: strict flake8, strict C901, full pytest with coverage, dependency audit/security checks supported by CI, Qt `--self-test`, renderer-contract suite and Windows smoke through GitHub Actions.
- [ ] **Step 6: Commit**: `docs: describe PySide6 phase 4 journals and operations`.

## Plan Self-Review

- Scope intentionally excludes the other independent Phase 4 subsystems (blacklist management, batch, backup/restore, diagnostics); they will get separate plans/PRs.
- Every new production layer has a test-first task.
- No schema, renderer or production-entry-point changes are required.
- Qt model/view requirement from the approved design is explicit and testable.
- Recovery semantics remain delegated to the already-tested core issuance module.
