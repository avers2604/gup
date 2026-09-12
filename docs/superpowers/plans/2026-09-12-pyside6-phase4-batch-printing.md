# PySide6 Phase 4 Batch Printing Implementation Plan

**Goal:** Replace the dashboard batch-printing placeholder with a real PySide6 workflow for vehicle passes and employee badges while preserving CSV compatibility, validation semantics, renderers, durable issuance and the Tkinter production fallback.

**Base:** stacked on `codex/pyside6-phase4-journals-operations` / PR #47 until that PR lands.

**Architecture:** Move CSV/template/import orchestration into a UI-independent `BatchService`; keep existing render/storage/importing/issuance APIs unchanged. Expose immutable import-review data through a ViewModel and Qt model/view page. Run PDF generation and durable issuance through a small `QThreadPool`/`QRunnable` worker so the GUI thread never performs large batch output.

**Constraints**
- Do not change SQLite schema, renderer geometry, `getpass_core` behavior or production Tkinter entry point.
- Preserve semicolon CSV format, UTF-8-SIG/CP1251/UTF-8 fallback and existing template columns/samples.
- Badge photo references must remain relative to the CSV directory; traversal/absolute paths remain rejected by `photo_in_folder`.
- Preserve validation errors/warnings from `getpass_core.importing.validate_items` and require explicit acceptance when only warnings remain.
- Preserve vehicle page packing: two passes per A4 page; badge packing: 3×3 / nine badges per A4 page.
- Preserve durable sequence: `issuance.prepare → save_pdf_pages → issuance.confirm`; cancel prepared operation on output failure/cancel.
- Update vehicle cache only after successful vehicle batch confirmation.
- Use `QThreadPool`/`QRunnable` for batch output; cancellation must be cooperative between pages.
- Use Qt model/view for import review; no Tk-style row manipulation.
- Keep batch as a separate `batch` route reachable from Dashboard and Sidebar.

## Task 1 — Application model and CSV/template service

Create:
- `getpass_app/models/batch.py`
- `getpass_app/services/batch_service.py`
- `tests/test_batch_application.py`

Contracts:
- `BatchKind`: `pass` / `badge`.
- immutable `BatchImport`, `BatchReviewRow`, `BatchReview` projections.
- template metadata for vehicle/badge headers, samples and filenames.
- `read_csv(path)` detects UTF-8-SIG, CP1251, UTF-8 and returns data rows excluding header.
- `parse_pass_rows(rows, common)` preserves legacy field mapping.
- `parse_badge_rows(rows, csv_dir, defaults)` preserves legacy field mapping and safe photo lookup.
- `review(kind, items)` delegates warnings/errors to `validate_items` and exposes row-level results.
- `export_template(kind, path)` writes semicolon UTF-8-SIG CSV.

TDD:
1. RED tests for encoding fallback, exact field mapping, safe badge photo handling, template output and review projection.
2. GREEN minimal implementation using existing core helpers.

## Task 2 — Batch output orchestration

Extend:
- `getpass_app/services/batch_service.py`
- `tests/test_batch_application.py`

Contracts:
- `generate_pdf(kind, items, path, *, cancelled, progress)`.
- pass page builder reuses `render_pass`, `build_pass_a4_sheet`, brand icons.
- badge page builder reuses `render_single_badge_image`, `build_badge_a4_grid`.
- builds journal records exactly as legacy batch does.
- `prepare`, streaming `save_pdf_pages`, then `confirm`.
- output exception/cancellation attempts `issuance.cancel` before raising a domain `BatchOutputError`/`BatchCancelled`.
- vehicle cache update only after confirm.

TDD:
1. RED tests for page counts, progress, cancellation between pages, prepare/confirm/cancel ordering and cache timing.
2. GREEN implementation without PySide6 imports.

## Task 3 — Qt worker, models and ViewModel

Create:
- `getpass_qt/workers/task_worker.py`
- `getpass_qt/models/batch_review_table_model.py`
- `getpass_qt/viewmodels/batch_viewmodel.py`
- `tests/test_qt_task_worker.py`
- `tests/test_qt_batch_review_model.py`
- `tests/test_qt_batch_viewmodel.py`

Contracts:
- reusable `TaskWorker(QRunnable)` emits result/error/progress/finished and receives a cancellation event.
- `BatchReviewTableModel` exposes row/number/person/result and a role for error/warning state.
- ViewModel owns selected kind, loaded source path/items/review, common pass defaults and badge defaults.
- imports/review are synchronous small operations; PDF generation is dispatched through worker pool.
- busy/progress/cancel state is signal-driven.

TDD:
1. RED worker/model/ViewModel tests.
2. GREEN implementation.

## Task 4 — Batch page and route

Create:
- `getpass_qt/views/batch.py`
- `tests/test_qt_batch_page.py`

Modify:
- `getpass_qt/viewmodels/main_viewmodel.py`
- `getpass_qt/widgets/sidebar.py`
- `getpass_qt/main_window.py`
- `getpass_qt/views/dashboard.py` only as needed for route wiring
- `getpass_qt/theme/stylesheet.py` only with semantic existing tokens
- `tests/test_qt_navigation.py`
- `tests/test_qt_theme.py`

UI:
- tabs/selector for vehicle vs employee batch;
- template export button;
- CSV select/import button;
- import review `QTableView` and summary counts;
- warning confirmation before generation;
- output PDF picker;
- progress bar + cancel button while worker runs;
- success/failure state text and optional open-file action.

## Task 5 — Safe self-test, docs and verification

Modify:
- `getpass_qt/app.py`
- `tests/test_qt_entrypoint.py`
- `README.md`

Self-test must use fake batch service/worker-safe data and never read production files/SQLite.

Final verification:
- strict flake8/C901;
- full pytest + coverage on Python 3.13/3.14;
- pip-audit + Bandit;
- Windows tests;
- Qt source self-test;
- production EXE/package smoke;
- Qt preview EXE smoke;
- Inno installer install/self-test/uninstall.
