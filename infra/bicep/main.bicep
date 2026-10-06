targetScope = 'resourceGroup'

@description('Azure region for the platform.')
param location string = resourceGroup().location

@description('Short globally unique suffix used in resource names.')
@minLength(3)
param namePrefix string = 'aiincident'

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

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01' = {
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

output mlWorkspaceName string = mlWorkspace.name
output foundryProjectEndpoint string = 'https://${foundryAccount.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output keyVaultName string = keyVault.name
output acrName string = acr.name
