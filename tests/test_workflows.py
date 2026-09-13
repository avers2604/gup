from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_windows_pr_smoke_builds_and_self_tests_production_and_rollback():
    workflow = _workflow("windows-ci.yml")

    assert "runs-on: windows-latest" in workflow
    assert "python -m pytest" in workflow
    assert "python pass_generator.py --self-test" in workflow
    assert "python legacy_pass_generator.py --self-test" in workflow
    assert "python -m PyInstaller" in workflow
    assert "pass_generator.py" in workflow
    assert "legacy_pass_generator.py" in workflow
    assert "GET-Passes.exe' -ArgumentList '--self-test'" in workflow
    assert "GET-Passes-Legacy.exe' -ArgumentList '--self-test'" in workflow
    assert "GET-Passes-Qt-Preview" not in workflow
    assert "permissions:\n  contents: read" in workflow


def test_release_signing_prefers_managed_artifact_signing_then_pfx_fallbacks():
    workflow = _workflow("build-exe.yml")
    assert "if: ${{ env.HAS_ARTIFACT_SIGNING_SECRETS == 'true' }}" in workflow
    assert (
        "if: ${{ env.HAS_AZURE_SIGNING_SECRETS == 'true' && "
        "env.HAS_ARTIFACT_SIGNING_SECRETS != 'true' }}"
    ) in workflow
    assert (
        "if: ${{ env.HAS_WINDOWS_SIGNING_SECRETS == 'true' && "
        "env.HAS_ARTIFACT_SIGNING_SECRETS != 'true' && "
        "env.HAS_AZURE_SIGNING_SECRETS != 'true' }}"
    ) in workflow


def test_inno_setup_contract_matches_phase5_version_and_installs_rollback():
    installer = (ROOT / "installer" / "GET-Passes.iss").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'version = "2.0.0"' in project
    assert '#define MyAppVersion "2.0.0"' in installer
    assert "VersionInfoVersion=2.0.0.0" in installer
    assert "DefaultDirName={autopf}\\GET-Passes" in installer
    assert "PrivilegesRequired=admin" in installer
    assert 'Source: "..\\dist\\GET-Passes.exe"' in installer
    assert 'Source: "..\\dist\\GET-Passes-Legacy.exe"' in installer
    assert "UninstallDisplayIcon={app}\\GET-Passes.exe" in installer
    assert 'Filename: "{app}\\GET-Passes.exe"' in installer
    assert 'Filename: "{app}\\GET-Passes-Legacy.exe"' not in installer.split("[Icons]", 1)[1]


def test_windows_pr_smoke_installs_tests_both_exes_and_uninstalls_setup():
    workflow = _workflow("windows-ci.yml")

    assert "choco install innosetup" in workflow
    assert "ISCC.exe" in workflow
    assert "GET-Passes-Setup.exe" in workflow
    assert "Join-Path $installDir 'GET-Passes.exe'" in workflow
    assert "Join-Path $installDir 'GET-Passes-Legacy.exe'" in workflow
    assert "/VERYSILENT" in workflow
    assert "unins000.exe" in workflow


def test_main_build_packages_production_and_rollback_and_verifies_signatures():
    workflow = _workflow("build-exe.yml")

    assert "pass_generator.py" in workflow
    assert "legacy_pass_generator.py" in workflow
    assert "GET-Passes-Legacy" in workflow
    assert "Get-AuthenticodeSignature 'dist\\GET-Passes.exe'" in workflow
    assert "Get-AuthenticodeSignature 'dist\\GET-Passes-Legacy.exe'" in workflow
    assert "GET-Passes-windows.zip" in workflow
    assert "Copy-Item 'dist\\GET-Passes-Legacy.exe'" in workflow
    assert "GET-Passes-Qt-Preview" not in workflow


def test_stable_release_keeps_signing_policy_and_packages_rollback():
    workflow = _workflow("release.yml")

    assert "tags:" in workflow
    assert "v*" in workflow
    assert "pyproject.toml" in workflow
    assert "github.ref_name" in workflow
    assert "Require trusted signing for stable release" in workflow
    assert "pass_generator.py" in workflow
    assert "legacy_pass_generator.py" in workflow
    assert "GET-Passes-Legacy" in workflow
    assert "GET-Passes-Setup.exe" in workflow
    assert "softprops/action-gh-release" in workflow
    assert "prerelease: false" in workflow
    assert "GET-Passes-Qt-Preview" not in workflow


def test_python_ci_lints_production_and_rollback_entrypoints():
    workflow = _workflow("python-app.yml")

    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "getpass_app" in workflow
    assert "getpass_design" in workflow
    assert "getpass_qt" in workflow
    assert "pass_generator.py legacy_pass_generator.py" in workflow


def test_phase5_production_workflows_build_qt_launcher_and_legacy_rollback():
    for name in ("windows-ci.yml", "build-exe.yml", "release.yml"):
        workflow = _workflow(name)
        assert "pass_generator.py" in workflow
        assert "legacy_pass_generator.py" in workflow
        assert "GET-Passes-Legacy" in workflow
        assert "GET-Passes-Qt-Preview" not in workflow
