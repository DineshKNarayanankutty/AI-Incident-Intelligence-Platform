# Deployment Runbook

## 0. Preflight — no Azure resources required

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
python scripts/validate_project.py
```

## 1. Build local artifacts

```powershell
python -m src.data.generate_synthetic_data --rows 400 --seed 42
python -m src.training.train --register-model
```

## 2. Azure ML lifecycle

Register the data asset, environments, model, endpoint, and deployment using the YAML files under `azure_ml/`.

Do not change the model contract between local and managed serving.

## 3. FastAPI

Local:

```powershell
$env:INFERENCE_BACKEND="local"
$env:FOUNDRY_BACKEND="local"
uvicorn app.main:app --reload
```

Azure ML + Foundry:

```text
INFERENCE_BACKEND=azureml
FOUNDRY_BACKEND=azure
AZURE_ML_SCORING_URI=<endpoint scoring URI>
AZURE_AI_PROJECT_ENDPOINT=<Foundry project endpoint>
FOUNDRY_AGENT_NAME=<agent name>
```

Authentication uses `DefaultAzureCredential`; use managed identity/OIDC in Azure rather than application secrets.

## 4. CI/CD order

1. CI tests and static validation.
2. Infrastructure what-if.
3. Infrastructure deployment.
4. Azure ML training and model registration.
5. Model/endpoint deployment (then sync scoring URI to App Service).
6. Foundry agent/model setup.
7. FastAPI deployment.
8. Evaluation, drift, and monitoring.
9. E2E smoke test.

The repository does not automatically deploy anything from a push.
