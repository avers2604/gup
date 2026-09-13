from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_tm5_private_pki_assets_and_scripts_exist():
    root_cert = ROOT / "certs" / "TM5-Root-CA.cer"
    assert root_cert.exists()
    assert "-----BEGIN CERTIFICATE-----" in root_cert.read_text(encoding="utf-8")

    create_script = (ROOT / "tools" / "create_tm5_private_pki.ps1").read_text(encoding="utf-8")
    assert 'CN=TM5 Root CA' in create_script
    assert 'CN=TM5' in create_script
    assert 'TM5 Code Signing' in create_script
    assert '1.3.6.1.5.5.7.3.3' in create_script
    assert 'Export-PfxCertificate' in create_script
    assert 'Export-Certificate' in create_script

    install_script = (ROOT / "tools" / "install_tm5_root.ps1").read_text(encoding="utf-8")
    assert 'Cert:\\LocalMachine\\Root' in install_script
    assert 'TM5-Root-CA.cer' in install_script


def test_private_key_files_are_ignored_by_git():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.pfx" in gitignore
    assert "*.p12" in gitignore
    assert "*.key" in gitignore


def test_release_workflows_support_tm5_private_signing():
    for name in ("build-exe.yml", "release.yml"):
        workflow = _workflow(name)
        assert "HAS_TM5_PRIVATE_SIGNING_SECRETS" in workflow
        assert "TM5_SIGN_CERT_BASE64" in workflow
        assert "TM5_SIGN_CERT_PASSWORD" in workflow
        assert "certs\\TM5-Root-CA.cer" in workflow
        assert "Import-Certificate" in workflow
        assert "Get-AuthenticodeSignature" in workflow


def test_signing_docs_explain_private_tm5_scope():
    docs = (ROOT / "docs" / "SIGNING.md").read_text(encoding="utf-8")
    assert "TM5 Private PKI" in docs
    assert "TM5 Root CA" in docs
    assert "TM5 Code Signing" in docs
    assert "GPO" in docs
    assert "не является публично доверенной" in docs
