using './main.bicep'

param location = 'eastus'
param namePrefix = 'aiincident'
param modelDeploymentName = 'gpt-5-mini'
param tags = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}
