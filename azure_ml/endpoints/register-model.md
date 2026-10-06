# Azure ML asset registration

These commands are intentionally documentation-only. They are not executed by CI until the deployment workflow is approved.

```bash
az ml data create -f azure_ml/data/incident-data.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE"
az ml environment create -f azure_ml/environments/training-environment.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE"
az ml environment create -f azure_ml/environments/serving-environment.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE"
az ml model create -f azure_ml/model.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE"
az ml online-endpoint create -f azure_ml/endpoints/managed-endpoint.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE"
az ml online-deployment create -f azure_ml/endpoints/managed-deployment.yml -g "$AZURE_RESOURCE_GROUP" -w "$AZURE_ML_WORKSPACE" --all-traffic
```

The managed endpoint uses Microsoft Entra ID (`aad_token`) rather than embedding a key in the application. Current Azure ML documentation recommends explicit registered model/environment references for production deployments.
