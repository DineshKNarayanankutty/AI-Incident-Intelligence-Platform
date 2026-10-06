using './main.bicep'

param location = 'centralus'
param namePrefix = 'aiincident77a8b195'
param apiPlanSku = 'F1'

param tags = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}