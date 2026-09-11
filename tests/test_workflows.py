from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_pr_smoke_builds_and_self_tests_exe():
    workflow = (ROOT / ".github" / "workflows" / "windows-ci.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: windows-latest" in workflow
    assert "python -m pytest" in workflow
    assert "python -m PyInstaller" in workflow
    assert "GET-Passes.exe' -ArgumentList '--self-test'" in workflow
    assert "permissions:\n  contents: read" in workflow


def test_release_signing_prefers_azure_when_both_methods_are_configured():
    workflow = (ROOT / ".github" / "workflows" / "build-exe.yml").read_text(
        encoding="utf-8"
    )
    assert "if: ${{ env.HAS_AZURE_SIGNING_SECRETS == 'true' }}" in workflow
    assert (
        "if: ${{ env.HAS_WINDOWS_SIGNING_SECRETS == 'true' && "
        "env.HAS_AZURE_SIGNING_SECRETS != 'true' }}"
    ) in workflow


def test_inno_setup_contract_matches_project_version():
    installer = (ROOT / "installer" / "GET-Passes.iss").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'version = "1.1.0"' in project
    assert '#define MyAppVersion "1.1.0"' in installer
    assert "DefaultDirName={autopf}\\GET-Passes" in installer
    assert "PrivilegesRequired=admin" in installer
    assert "UninstallDisplayIcon={app}\\GET-Passes.exe" in installer
    assert "Filename: {app}\\GET-Passes.exe" in installer


def test_windows_pr_smoke_installs_runs_and_uninstalls_setup():
    workflow = (ROOT / ".github" / "workflows" / "windows-ci.yml").read_text(
        encoding="utf-8"
    )

    assert "choco install innosetup" in workflow
    assert "ISCC.exe" in workflow
    assert "GET-Passes-Setup.exe" in workflow
    assert "--self-test" in workflow
    assert "/VERYSILENT" in workflow
    assert "unins000.exe" in workflow


def test_release_build_publishes_portable_and_installer_and_verifies_signatures():
    workflow = (ROOT / ".github" / "workflows" / "build-exe.yml").read_text(
        encoding="utf-8"
    )

    assert "choco install innosetup" in workflow
    assert "GET-Passes-Setup.exe" in workflow
    assert "Get-AuthenticodeSignature" in workflow
    assert "GET-Passes-windows.zip" in workflow
    assert "files: |" in workflow
    assert "GET-Passes-Setup.exe" in workflow.split("files: |", 1)[1]


def test_stable_release_workflow_requires_matching_v_tag_and_builds_installer():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "tags:" in workflow
    assert "v*" in workflow
    assert "pyproject.toml" in workflow
    assert "github.ref_name" in workflow
    assert "GET-Passes-Setup.exe" in workflow
    assert "softprops/action-gh-release" in workflow
    assert "prerelease: false" in workflow
