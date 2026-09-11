# GET-Passes v1.1.0 Release and Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подготовить GET-Passes 1.1.0 к эксплуатации: signing-ready release pipeline, формальная приёмка, стабильный versioned release и Windows Setup.exe.

**Architecture:** Portable EXE остаётся базовым артефактом PyInstaller. Inno Setup упаковывает уже проверенный EXE в установщик; приложение хранит пользовательские данные вне Program Files через существующий fallback в `%LOCALAPPDATA%/GET-Passes`. Release pipeline публикует portable ZIP и Setup.exe, а цифровая подпись выполняется при наличии Azure/PFX signing secrets и затем проверяется Authenticode.

**Tech Stack:** Python 3.13/3.14, Tkinter, pytest, PyInstaller 6.22.2, GitHub Actions Windows runner, Inno Setup 6, SignTool/Authenticode.

**Spec:** запрос пользователя выполнить пункты 1–4: цифровая подпись, приёмочные испытания, стабильная версия и Windows-установщик.

## Global Constraints

- Не ослаблять strict flake8 или C901 gate.
- Сохранять portable ZIP для пользователей, которым не нужен установщик.
- Не считать self-signed сертификат эквивалентом доверенной подписи.
- Не заявлять прохождение физической печати без реального принтера.
- Установщик не должен хранить рабочую SQLite БД и настройки в Program Files.
- Stable release version: `v1.1.0`, поскольку `pyproject.toml` уже содержит `version = "1.1.0"`.

---

### Task 1: Signing gate and release documentation

**Files:**
- Modify: `.github/workflows/build-exe.yml`
- Create: `docs/SIGNING.md`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: existing Azure Key Vault and PFX secret contracts.
- Produces: reusable signing mode, Authenticode verification, explicit unsigned status.

- [ ] **Step 1: Add failing workflow assertions**
  Require signature verification for both application EXE and installer when signing is configured, and explicit unsigned release metadata otherwise.
- [ ] **Step 2: Verify RED in PR CI**
- [ ] **Step 3: Implement signing helpers/steps without weakening unsigned fallback**
- [ ] **Step 4: Document exact GitHub secrets and certificate requirements**
- [ ] **Step 5: Verify GREEN**

### Task 2: Acceptance checklist and automated acceptance gate

**Files:**
- Create: `docs/ACCEPTANCE.md`
- Modify: `.github/workflows/windows-ci.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `GET-Passes.exe --self-test`, pytest, Windows runner.
- Produces: automated Windows acceptance plus explicit physical-printer checklist.

- [ ] **Step 1: Define required acceptance scenarios**
  Cover startup without Python, create/save pass, badge flow, journal/recovery, backup/restore, installer lifecycle, and physical printer checks.
- [ ] **Step 2: Add workflow assertions for install/uninstall smoke**
- [ ] **Step 3: Extend Windows PR workflow with installer build/install/self-test/uninstall**
- [ ] **Step 4: Verify GREEN on Windows runner**

### Task 3: Windows installer

**Files:**
- Create: `installer/GET-Passes.iss`
- Modify: `.github/workflows/build-exe.yml`
- Modify: `.github/workflows/windows-ci.yml`
- Modify: `README.md`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: `dist/GET-Passes.exe`, `app_icon.ico`.
- Produces: `GET-Passes-Setup.exe`, desktop/Start Menu shortcuts, silent install/uninstall support.

- [ ] **Step 1: Add failing assertions for Inno Setup contract**
- [ ] **Step 2: Create installer script with AppId, version 1.1.0, per-machine installation and uninstall metadata**
- [ ] **Step 3: Build installer in PR Windows smoke and production release workflows**
- [ ] **Step 4: Run installed EXE self-test and silent uninstall in CI**
- [ ] **Step 5: Publish Setup.exe alongside portable ZIP**

### Task 4: Stable versioned release

**Files:**
- Create/Modify: `.github/workflows/release.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes: main branch at verified commit and version `1.1.0`.
- Produces: stable GitHub release `v1.1.0` with portable ZIP and Setup.exe.

- [ ] **Step 1: Add workflow contract tests for tag/version consistency**
- [ ] **Step 2: Implement manual/tag stable-release workflow with test, package and installer gates**
- [ ] **Step 3: Ensure stable release does not masquerade as signed when signing secrets are absent**
- [ ] **Step 4: Verify PR CI and merge to main**
- [ ] **Step 5: Run production build on main and create stable `v1.1.0` release only after automated gates pass**

### Task 5: Final verification

**Files:** none

- [ ] **Step 1: Run Python 3.13/3.14 CI, Security, Windows PR smoke**
- [ ] **Step 2: Verify installer build/install/self-test/uninstall**
- [ ] **Step 3: Verify main production build and release assets**
- [ ] **Step 4: Record physical-printer acceptance as external/manual until performed on target equipment**
