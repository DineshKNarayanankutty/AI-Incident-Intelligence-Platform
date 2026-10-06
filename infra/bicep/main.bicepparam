using './main.bicep'

param location = 'eastus'
param namePrefix = 'aiincident'
param apiPlanSku = 'B1'
param tags = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}
