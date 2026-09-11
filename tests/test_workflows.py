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
