
using './main.bicep'

param location = 'centralus'
param namePrefix = 'aiincident77a8b195'
param apiPlanSku = 'S1'

param azureMlScoringUri = readEnvironmentVariable('AZURE_ML_SCORING_URI')
param azureMlDeploymentName = readEnvironmentVariable('AZURE_ML_DEPLOYMENT_NAME')
param azureMlModelVersion = readEnvironmentVariable('AZURE_ML_MODEL_VERSION')

// Pass-through of live Foundry settings: appSettings replaces the whole
// collection on deployment, so these must never be blanked.
param foundryAgentName = readEnvironmentVariable('FOUNDRY_AGENT_NAME')
param foundryAgentVersion = readEnvironmentVariable('FOUNDRY_AGENT_VERSION', '')
param foundryModelDeploymentName = readEnvironmentVariable('AZURE_AI_MODEL_DEPLOYMENT_NAME')

param tags = {
  project: 'ai-incident-intelligence'
  environment: 'dev'
}
