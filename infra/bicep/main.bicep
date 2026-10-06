targetScope = 'resourceGroup'

@description('Azure region for the platform.')
param location string = resourceGroup().location

@description('Short prefix used in resource names.')
@minLength(3)
param namePrefix string = 'aiincident'

@description('App Service plan SKU for the FastAPI host. F1 is used to avoid the current B1 quota limit.')
@allowed([
  'F1'
  'B1'
])
param apiPlanSku string = 'F1'

@description('Tags applied to resources.')
param tags object = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}

var storageName = toLower('${namePrefix}st')
var acrName = toLower(replace('${namePrefix}acr', '-', ''))
var appInsightsName = '${namePrefix}-appi'
var logAnalyticsName = '${namePrefix}-logs'
var keyVaultName = '${namePrefix}-kv'
var mlWorkspaceName = '${namePrefix}-ml'
var foundryAccountName = '${namePrefix}-ai'
var foundryProjectName = '${namePrefix}-project'
var apiPlanName = '${namePrefix}-api-plan'
var apiAppName = '${namePrefix}-api'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    sku: {
      family: 'A'
      name: 'standard'
    }
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource mlWorkspace 'Microsoft.MachineLearningServices/workspaces@2026-03-01' = {
  name: mlWorkspaceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'Default'
  properties: {
    applicationInsights: appInsights.id
    containerRegistry: acr.id
    description: 'AI Incident Intelligence Platform Azure ML workspace'
    friendlyName: mlWorkspaceName
    keyVault: keyVault.id
    storageAccount: storage.id
  }
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2026-07-15-preview' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'AI Incident Intelligence'
    description: 'Foundry project for incident analysis and GenAIOps evaluation.'
  }
}

// -----------------------------------------------------------------------------
// FastAPI hosting
// -----------------------------------------------------------------------------

resource apiPlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: apiPlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: apiPlanSku
    tier: apiPlanSku == 'F1' ? 'Free' : 'Basic'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource apiApp 'Microsoft.Web/sites@2024-11-01' = {
  name: apiAppName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: apiPlan.id
    httpsOnly: true
    siteConfig: {
      alwaysOn: apiPlanSku != 'F1'
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      healthCheckPath: '/health'
      appSettings: [
        {
          name: 'APP_ENV'
          value: 'azure'
        }
        {
          name: 'INFERENCE_BACKEND'
          value: 'azureml'
        }
        {
          name: 'FOUNDRY_BACKEND'
          value: 'azure'
        }
        {
          name: 'AZURE_SUBSCRIPTION_ID'
          value: subscription().subscriptionId
        }
        {
          name: 'AZURE_RESOURCE_GROUP'
          value: resourceGroup().name
        }
        {
          name: 'AZURE_ML_WORKSPACE'
          value: mlWorkspace.name
        }
        {
          name: 'AZURE_ML_ENDPOINT_NAME'
          value: 'incident-severity-endpoint'
        }
        {
          name: 'AZURE_ML_DEPLOYMENT_NAME'
          value: 'blue'
        }
        {
          name: 'AZURE_ML_MODEL_NAME'
          value: 'incident-severity'
        }
        {
          name: 'AZURE_ML_MODEL_VERSION'
          value: '1'
        }
        {
          name: 'AZURE_ML_SCORING_URI'
          value: ''
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
        }
        {
          name: 'FOUNDRY_AGENT_NAME'
          value: ''
        }
        {
          name: 'FOUNDRY_AGENT_VERSION'
          value: ''
        }
        {
          name: 'AZURE_AI_MODEL_DEPLOYMENT_NAME'
          value: ''
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'OTEL_SERVICE_NAME'
          value: 'ai-incident-intelligence-api'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: '1'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: '1'
        }
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
      ]
    }
  }
}

// -----------------------------------------------------------------------------
// Azure ML endpoint invocation permission
// -----------------------------------------------------------------------------

resource mlEndpointInvokerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'aiincident-ml-endpoint-invoker')
  properties: {
    roleName: 'AI Incident ML Endpoint Invoker'
    description: 'Allows the AI Incident FastAPI managed identity to invoke Azure ML online endpoints for scoring.'
    type: 'CustomRole'
    assignableScopes: [
      resourceGroup().id
    ]
    permissions: [
      {
        actions: [
          'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/score/action'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
  }
}

resource apiMlInvokerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(mlWorkspace.id, apiApp.id, 'aiincident-ml-endpoint-invoker')
  scope: mlWorkspace
  properties: {
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: mlEndpointInvokerRole.id
  }
}

// -----------------------------------------------------------------------------
// Foundry Agent Consumer permission
// -----------------------------------------------------------------------------

resource apiFoundryAgentConsumerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryProject.id, apiApp.id, 'foundry-agent-consumer')
  scope: foundryProject
  properties: {
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'eed3b665-ab3a-47b6-8f48-c9382fb1dad6'
    )
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------

output mlWorkspaceName string = mlWorkspace.name
output foundryAccountName string = foundryAccount.name
output foundryProjectName string = foundryProject.name
output foundryProjectEndpoint string = 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output keyVaultName string = keyVault.name
output acrName string = acr.name
output apiAppName string = apiApp.name
output apiHostname string = apiApp.properties.defaultHostName
output apiPrincipalId string = apiApp.identity.principalId