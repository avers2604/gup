# PySide6 Phase 5 Production Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PySide6 the default GET-Passes production application, retain a packaged Tkinter rollback executable, adapt Windows packaging/release contracts, and prepare the 2.0.0 build for physical printer/workstation acceptance.

**Architecture:** `pass_generator.py` becomes the stable production launcher around `getpass_qt.app.main`, preserving crash logging and single-instance protection. The current Tkinter launcher is preserved as `legacy_pass_generator.py` and packaged as `GET-Passes-Legacy.exe`. Existing core, SQLite, renderer and data locations remain unchanged.

**Tech Stack:** Python >=3.13,<3.15; PySide6 >=6.11,<6.12; Tkinter rollback; PyInstaller 6.22.2; Inno Setup 6; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-11-pyside6-v2-ui-design.md`

## Global Constraints

- Do not alter SQLite schema, migrations, journal formats, issuance semantics or user data locations.
- Do not alter printed vehicle/employee documents, renderer assets, typography or coordinates.
- Keep `getpass_core` and `getpass_app` free of Qt dependencies.
- Preserve single-instance protection for the production launcher.
- Preserve crash logging.
- Keep an explicit Tkinter rollback path until physical workstation/printer acceptance passes.
- Version `2.0.0` is the production-cutover version, but do not create a `v2.0.0` tag or stable release before physical acceptance and trusted-signing requirements are satisfied.

---

### Task 1: Production and rollback entry points

**Files:**
- Modify: `pass_generator.py`
- Create: `legacy_pass_generator.py`
- Test: `tests/test_production_entrypoint.py`

**Interfaces:**
- Production: `pass_generator.main(argv: list[str] | None = None) -> int` delegates to `getpass_qt.app.main(argv)` and keeps `single_instance(config.DATA_DIR)` for non-self-test runs.
- Rollback: `legacy_pass_generator.main() -> int` preserves the current Tkinter startup and self-test behavior.

- [ ] Write RED tests proving production imports/dispatches Qt rather than `getpass_ui`, `--self-test` reaches the Qt self-test without single-instance side effects, and rollback imports the Tkinter `App`.
- [ ] Run the focused tests and verify failure against the current Tkinter production launcher.
- [ ] Copy the current launcher behavior to `legacy_pass_generator.py` before changing production.
- [ ] Replace production startup with Qt delegation, preserving crash log installation and single-instance protection for normal runs.
- [ ] Run focused and full Python tests; require GREEN.

### Task 2: Version and package contracts

**Files:**
- Modify: `pyproject.toml`
- Modify: `installer/GET-Passes.iss`
- Modify: `.github/workflows/windows-ci.yml`
- Modify: `.github/workflows/build-exe.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Production binary remains `GET-Passes.exe` and is built from `pass_generator.py` (now Qt).
- Rollback binary is `GET-Passes-Legacy.exe` built from `legacy_pass_generator.py`.
- Installer and portable ZIP contain both binaries; shortcuts continue to target production `GET-Passes.exe`.

- [ ] Update workflow/installer tests first: require version `2.0.0`, no production `GET-Passes-Qt-Preview`, a packaged `GET-Passes-Legacy.exe`, source self-tests for both launchers, packaged self-tests for both executables, and installed self-tests for both executables.
- [ ] Run workflow tests and verify RED.
- [ ] Set project and installer version to `2.0.0`.
- [ ] Change Windows PR smoke to test Qt production from `pass_generator.py`, build/smoke `GET-Passes.exe`, build/smoke `GET-Passes-Legacy.exe`, install both, self-test both, then uninstall.
- [ ] Adapt main-branch `build-exe.yml` and tagged `release.yml` to package the rollback executable alongside production without changing stable-release signing policy.
- [ ] Update Inno Setup `[Files]` to include `GET-Passes-Legacy.exe`; do not add a default desktop/start-menu shortcut for rollback.
- [ ] Run workflow tests and full Python tests; require GREEN.

### Task 3: Documentation and physical acceptance gate

**Files:**
- Modify: `README.md`
- Create: `docs/PHYSICAL_ACCEPTANCE_2_0.md`

- [ ] Document that PySide6 is now the default production entry point and `legacy_pass_generator.py` / `GET-Passes-Legacy.exe` is temporary rollback only.
- [ ] Document that 2.0.0 must not be tagged/released until physical acceptance and trusted Authenticode policy pass.
- [ ] Add a concrete workstation checklist: existing DB opens; vehicle A4/A5; front/back duplex/manual flip; employee CR80/A4; batch PDF; printer selection; unfinished-operation recovery; backup/restore test; 100/125/150/200% DPI; rollback executable launch.
- [ ] Verify docs do not claim physical acceptance has already happened.

### Task 4: Final verification and review readiness

**Files:** none unless verification finds defects.

- [ ] Audit `main...HEAD` and prove no changes to renderer/assets/fonts/SQLite schema/migrations.
- [ ] Require Python 3.13 and 3.14 full suites, lint/C901, dependency audit and Bandit GREEN.
- [ ] Require gitleaks and CodeQL GREEN.
- [ ] Require Windows PR smoke GREEN including production Qt EXE, legacy rollback EXE, installer install/self-test/uninstall.
- [ ] Update PR body with the verified head and exact gates.
- [ ] Mark PR ready for review; do not create a v2.0.0 tag or stable release until the physical acceptance checklist is executed on a real workstation/printer.
