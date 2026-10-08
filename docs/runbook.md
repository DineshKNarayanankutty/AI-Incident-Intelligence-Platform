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
7. FastAPI deployment (`FastAPI Deployment` workflow: tests, `scripts/package_api.py` clean runtime zip, App Service deployment, runtime configuration sync, smoke test).
8. Evaluation, drift, and monitoring.
9. E2E smoke test.

Drift checks use `data/reference/drift_baseline.json`. Categorical and numeric feature distributions are compared with PSI using reference-defined numeric bins. PSI >= 0.10 is reported as a warning and PSI >= 0.25 is treated as drift. Retraining is only submitted when the configured drift threshold is exceeded.

The repository does not automatically deploy anything from a push.


## Drift detection

Build or refresh the known-good reference profile only from an intentionally approved baseline dataset:

```powershell
python scripts/build_drift_baseline.py --data data/synthetic_incidents.csv
```

Run a drift check against the committed reference:

```powershell
python -m mlops.drift_check `
  --reference data/reference/drift_baseline.json `
  --data data/synthetic_incidents.csv `
  --threshold 0.25 `
  --warning-threshold 0.10 `
  --output outputs/drift/result.json
```

The result reports `drifted_features`, `warning_features`, `max_psi`, and per-feature categorical/numeric comparisons. Numeric PSI uses the reference profile's bins so the reference and current distributions are directly comparable.
