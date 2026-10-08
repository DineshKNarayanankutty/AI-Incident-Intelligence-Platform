$ErrorActionPreference = 'Stop'

# Start the local FastAPI app using the Azure ML + Microsoft Foundry backends.
# Authentication is handled by DefaultAzureCredential (normally `az login`).

$resourceGroup = 'rg-ai-incident-dev-central'
$workspaceName = 'aiincident77a8b195-ml'
$endpointName = 'incident-severity-endpoint'
$deploymentName = 'blue'
$projectEndpoint = 'https://aiincident77a8b195-ai.services.ai.azure.com/api/projects/aiincident77a8b195-project'
$agentName = 'incident-operations-agent'
$appInsightsName = 'aiincident77a8b195-appi'

$env:APP_ENV = 'local'
$env:INFERENCE_BACKEND = 'azureml'
$env:FOUNDRY_BACKEND = 'azure'
$env:AZURE_ML_ENDPOINT_NAME = $endpointName
$env:AZURE_ML_DEPLOYMENT_NAME = $deploymentName
$env:AZURE_ML_MODEL_NAME = 'incident-severity'
$env:AZURE_ML_MODEL_VERSION = '1'
$env:AZURE_AI_PROJECT_ENDPOINT = $projectEndpoint
$env:FOUNDRY_AGENT_NAME = $agentName
$env:OTEL_SERVICE_NAME = 'ai-incident-intelligence-api'
$env:OTEL_CONSOLE_EXPORTER = 'false'
$env:APPLICATIONINSIGHTS_METRIC_NAMESPACE_OPT_IN = 'true'
$env:AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING = 'false'

# Export local Azure-backend traces/metrics to the existing Application Insights resource.
$appInsightsConnectionString = az monitor app-insights component show `
    --app $appInsightsName `
    --resource-group $resourceGroup `
    --query connectionString `
    -o tsv

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($appInsightsConnectionString)) {
    throw 'Unable to retrieve the Application Insights connection string. Verify the App Insights resource exists and run az login.'
}

$env:APPLICATIONINSIGHTS_CONNECTION_STRING = $appInsightsConnectionString.Trim()

# Always retrieve the current scoring URI from Azure instead of relying on a
# stale copied value.
$uri = az ml online-endpoint show `
    --name $endpointName `
    --resource-group $resourceGroup `
    --workspace-name $workspaceName `
    --query scoring_uri `
    -o tsv

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($uri)) {
    throw 'Unable to retrieve the Azure ML scoring URI. Run az login and verify the endpoint exists.'
}

$env:AZURE_ML_SCORING_URI = $uri.Trim()

Write-Host "INFERENCE_BACKEND = $env:INFERENCE_BACKEND"
Write-Host "FOUNDRY_BACKEND   = $env:FOUNDRY_BACKEND"
Write-Host "FOUNDRY_AGENT_NAME = $env:FOUNDRY_AGENT_NAME"
Write-Host "AZURE_ML_SCORING_URI = $env:AZURE_ML_SCORING_URI"
Write-Host ''

& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
