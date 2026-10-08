param(
    [string]$ResourceGroup = $env:AZURE_RESOURCE_GROUP,
    [string]$ClientId = $env:AZURE_CLIENT_ID,
    [string]$ContainerName = "production"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    throw "Provide -ResourceGroup or set AZURE_RESOURCE_GROUP."
}
if ([string]::IsNullOrWhiteSpace($ClientId)) {
    throw "Provide -ClientId or set AZURE_CLIENT_ID."
}

$storageAccount = az storage account list `
    --resource-group $ResourceGroup `
    --query "[?tags.project=='ai-incident-intelligence'].name | [0]" `
    -o tsv

if ([string]::IsNullOrWhiteSpace($storageAccount)) {
    throw "Could not find the tagged AI Incident Storage account in $ResourceGroup."
}

$objectId = az ad sp show --id $ClientId --query id -o tsv
if ([string]::IsNullOrWhiteSpace($objectId)) {
    throw "Could not resolve the service principal object ID for $ClientId."
}

$scope = az storage account show `
    --name $storageAccount `
    --resource-group $ResourceGroup `
    --query id -o tsv
$scope = "$scope/blobServices/default/containers/$ContainerName"

az role assignment create `
    --assignee-object-id $objectId `
    --assignee-principal-type ServicePrincipal `
    --role "Storage Blob Data Reader" `
    --scope $scope | Out-Null

Write-Host "Granted Storage Blob Data Reader to GitHub Actions principal $objectId on $scope"
