param(
    [string]$OutputDir = ".\tm5-pki",
    [int]$RootYears = 10,
    [int]$SigningYears = 2
)

$ErrorActionPreference = "Stop"

if ($RootYears -lt 2) { throw "RootYears must be at least 2." }
if ($SigningYears -lt 1 -or $SigningYears -ge $RootYears) {
    throw "SigningYears must be at least 1 and less than RootYears."
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null

$rootPassword = Read-Host "Password for OFFLINE TM5 Root CA backup PFX" -AsSecureString
$signingPassword = Read-Host "Password for TM5 Code Signing PFX" -AsSecureString

$root = $null
$signing = $null
try {
    $root = New-SelfSignedCertificate `
        -Type Custom `
        -Subject "CN=TM5 Root CA,O=TM5" `
        -FriendlyName "TM5 Root CA" `
        -KeyAlgorithm RSA `
        -KeyLength 4096 `
        -HashAlgorithm SHA256 `
        -KeyExportPolicy Exportable `
        -KeyUsage CertSign, CRLSign, DigitalSignature `
        -TextExtension @("2.5.29.19={critical}{text}ca=1&pathlength=0") `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears($RootYears)

    $signing = New-SelfSignedCertificate `
        -Type Custom `
        -Subject "CN=TM5,O=TM5" `
        -FriendlyName "TM5 Code Signing" `
        -Signer $root `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -HashAlgorithm SHA256 `
        -KeyExportPolicy Exportable `
        -KeyUsage DigitalSignature `
        -TextExtension @("2.5.29.19={critical}{text}ca=0", "2.5.29.37={text}1.3.6.1.5.5.7.3.3") `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears($SigningYears)

    $rootCer = Join-Path $resolvedOutput "TM5-Root-CA.cer"
    $rootPfx = Join-Path $resolvedOutput "TM5-Root-CA-Backup.pfx"
    $signingCer = Join-Path $resolvedOutput "TM5-CodeSigning.cer"
    $signingPfx = Join-Path $resolvedOutput "TM5-CodeSigning.pfx"

    Export-Certificate -Cert $root -FilePath $rootCer -Force | Out-Null
    Export-PfxCertificate -Cert $root -FilePath $rootPfx -Password $rootPassword -ChainOption EndEntityCertOnly -Force | Out-Null
    Export-Certificate -Cert $signing -FilePath $signingCer -Force | Out-Null
    Export-PfxCertificate -Cert $signing -FilePath $signingPfx -Password $signingPassword -ChainOption BuildChain -Force | Out-Null

    Write-Host ""
    Write-Host "TM5 Private PKI created."
    Write-Host "Publisher subject: CN=TM5, O=TM5"
    Write-Host "Root certificate:   $rootCer"
    Write-Host "Signing PFX:        $signingPfx"
    Write-Host "Root backup PFX:    $rootPfx"
    Write-Host ""
    Write-Host "Keep TM5-Root-CA-Backup.pfx offline and never upload it to GitHub or CI."
    Write-Host "Distribute only TM5-Root-CA.cer to trusted workstations."
    Write-Host "If you regenerate this PKI, replace certs/TM5-Root-CA.cer and redeploy trust to clients."
    Write-Host ""
    Write-Host "To prepare the signing PFX for GitHub secret TM5_SIGN_CERT_BASE64:"
    Write-Host '[Convert]::ToBase64String([IO.File]::ReadAllBytes("TM5-CodeSigning.pfx")) | Set-Clipboard'
}
finally {
    if ($signing) { Remove-Item -LiteralPath $signing.PSPath -Force -ErrorAction SilentlyContinue }
    if ($root) { Remove-Item -LiteralPath $root.PSPath -Force -ErrorAction SilentlyContinue }
}
