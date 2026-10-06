using './main.bicep'

param location = 'eastus'
param namePrefix = 'aiincident'
param tags = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}
