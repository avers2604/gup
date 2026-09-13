param(
    [string]$CertificatePath = (Join-Path $PSScriptRoot "..\certs\TM5-Root-CA.cer")
)

$ErrorActionPreference = "Stop"
$ExpectedSha256 = "86742AE7A08246595855655EB5961417BE75A553521947CD8A26933C0B55C95C"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated PowerShell session."
}

$resolved = (Resolve-Path -LiteralPath $CertificatePath).Path
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($resolved)
if ($certificate.Subject -notmatch "CN=TM5 Root CA") {
    throw "Unexpected certificate subject: $($certificate.Subject)"
}

$sha256 = $certificate.GetCertHashString([System.Security.Cryptography.HashAlgorithmName]::SHA256)
if ($sha256 -ne $ExpectedSha256) {
    throw "TM5 Root CA fingerprint mismatch. Expected $ExpectedSha256, got $sha256."
}

$installed = Import-Certificate `
    -FilePath $resolved `
    -CertStoreLocation "Cert:\LocalMachine\Root"

if (-not $installed) {
    throw "TM5 Root CA was not installed."
}

Write-Host "TM5 Root CA installed into Cert:\LocalMachine\Root."
Write-Host "SHA-256 fingerprint: $sha256"
Write-Host "Publisher certificates issued by this root are trusted on this workstation."
