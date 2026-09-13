param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$IdentityValidationId,

    [string]$ResourceGroup = "rg-tm5-signing",
    [string]$Location = "WestEurope",
    [string]$AccountName = "",
    [string]$ProfileName = "TM5-CodeSign"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is required. Install it and run az login first."
}

if ([string]::IsNullOrWhiteSpace($AccountName)) {
    $compactSubscription = $SubscriptionId.Replace("-", "")
    if ($compactSubscription.Length -lt 12) {
        throw "SubscriptionId is not valid."
    }
    $AccountName = "tm5$($compactSubscription.Substring(0, 12))"
}

Write-Host "Using Artifact Signing account: $AccountName"
Write-Host "Using Public Trust certificate profile: $ProfileName"

az account set -s $SubscriptionId
if ($LASTEXITCODE -ne 0) {
    throw "Unable to select Azure subscription $SubscriptionId."
}

az provider register --namespace "Microsoft.CodeSigning"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to register Microsoft.CodeSigning."
}

$registrationState = ""
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $registrationState = az provider show `
        --namespace "Microsoft.CodeSigning" `
        --query registrationState `
        -o tsv
    if ($registrationState -eq "Registered") {
        break
    }
    Start-Sleep -Seconds 5
}
if ($registrationState -ne "Registered") {
    throw "Microsoft.CodeSigning did not reach Registered state."
}

az extension add --name artifact-signing --upgrade --yes
if ($LASTEXITCODE -ne 0) {
    throw "Unable to install or update the artifact-signing Azure CLI extension."
}

$resourceGroupExists = az group exists --name $ResourceGroup
if ($resourceGroupExists -ne "true") {
    az group create --name $ResourceGroup --location $Location | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create resource group $ResourceGroup."
    }
}

az artifact-signing show `
    --resource-group $ResourceGroup `
    --account-name $AccountName `
    2>$null | Out-Null
$accountExists = $LASTEXITCODE -eq 0

if (-not $accountExists) {
    az artifact-signing create `
        --resource-group $ResourceGroup `
        --name $AccountName `
        --location $Location `
        --sku Basic | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create Artifact Signing account $AccountName."
    }
}

az artifact-signing certificate-profile show `
    --resource-group $ResourceGroup `
    --account-name $AccountName `
    --name $ProfileName `
    2>$null | Out-Null
$profileExists = $LASTEXITCODE -eq 0

if (-not $profileExists) {
    az artifact-signing certificate-profile create `
        --resource-group $ResourceGroup `
        --account-name $AccountName `
        --name $ProfileName `
        --profile-type PublicTrust `
        --identity-validation-id $IdentityValidationId | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create Public Trust profile $ProfileName."
    }
}

$endpoint = az artifact-signing show `
    --resource-group $ResourceGroup `
    --account-name $AccountName `
    --query accountUri `
    -o tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($endpoint)) {
    throw "Unable to read Artifact Signing endpoint."
}

az artifact-signing certificate-profile show `
    --resource-group $ResourceGroup `
    --account-name $AccountName `
    --name $ProfileName `
    -o json | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Unable to verify Public Trust profile $ProfileName."
}

Write-Host ""
Write-Host "TM5 signing infrastructure is ready."
Write-Host "Artifact Signing endpoint: $endpoint"
Write-Host "Artifact Signing account:  $AccountName"
Write-Host "Certificate profile:        $ProfileName"
Write-Host ""
Write-Host "Configure these GitHub repository secrets for the existing OIDC signing workflow:"
Write-Host "  AZURE_CLIENT_ID"
Write-Host "  AZURE_TENANT_ID"
Write-Host "  AZURE_SUBSCRIPTION_ID=$SubscriptionId"
Write-Host "  AZURE_ARTIFACT_SIGNING_ENDPOINT=$endpoint"
Write-Host "  AZURE_ARTIFACT_SIGNING_ACCOUNT_NAME=$AccountName"
Write-Host ""
Write-Host "The Windows publisher is the legal/DBA identity validated by Microsoft."
Write-Host "To display TM5 as publisher, TM5 itself must be the validated identity; TM5-CodeSign is only the technical profile name."