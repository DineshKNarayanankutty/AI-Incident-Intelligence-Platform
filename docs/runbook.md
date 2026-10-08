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
9. Scheduled Production Drift Monitoring.
10. E2E smoke test.

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

## Candidate retraining and quality gate

When drift exceeds the configured threshold, the retraining workflow submits the Azure ML training pipeline, waits for completion, downloads the named model output, and evaluates `metrics.json` against `data/reference/production_model_metrics.json`. The candidate must meet the minimum accuracy/macro-F1 thresholds and must not regress from the production baseline. Only a passing candidate is registered as the next `incident-severity` model version; production traffic is not changed by this workflow.

## Safe model deployment and promotion

A passing candidate model is registered but is never promoted automatically by the retraining workflow. Use the `Azure ML Blue-Green Deployment` GitHub Actions workflow with the registered `model_version`.

1. Run with `promote=false`. The workflow detects which of `blue` or `green` is currently serving 100% traffic, uses the inactive deployment as the candidate slot, deploys the requested model version with 0% traffic, and invokes that deployment directly.
2. After the candidate passes validation, run the same workflow with `promote=true`. Traffic is switched to the candidate and the live endpoint is smoke-tested. If the live smoke test fails, traffic is automatically restored to the previous production deployment.
3. FastAPI's Azure ML scoring URI is synchronized after promotion or rollback.
4. Use the `Azure ML Rollback` workflow for a manual rollback. It smoke-tests the inactive deployment before routing 100% traffic back to it.

The blue/green strategy intentionally keeps the previous production deployment available at 0% traffic so rollback does not require rebuilding the previous model.

Current Azure ML CLI guidance supports creating a second deployment with zero traffic, invoking it directly with `--deployment-name`, and updating endpoint traffic explicitly rather than using `--all-traffic` for production rollouts. See the Azure safe-rollout guidance for the underlying pattern.


### Candidate quality evaluation

Candidate retraining fits on the current/drifted dataset but evaluates on the fixed reference holdout (`data/synthetic_incidents.csv`, stratified 25% holdout, random_state=42) so the quality gate compares like-for-like with production model v1. The controlled demo changes only whitespace and therefore shifts monitored `text_length` without changing TF-IDF tokens.

## 5. Candidate evaluation protocol

- `data/reference/candidate_evaluation.csv` is the fixed clean evaluation set: the stratified 25% holdout of `data/synthetic_incidents.csv` (`random_state=42`). It is committed and never regenerated by workflows (`python -m scripts.build_candidate_evaluation` rebuilds it deterministically).
- `data/reference/production_model_metrics.json` holds the full-precision production baseline measured on that same set, with the dataset fingerprint.
- Retraining fits the candidate on the current/drifted `training_data` (rows that also appear in the evaluation set are removed) and evaluates it on `evaluation_data` as-is. Azure ML (`azure_ml/pipeline.yml`) and `mlops/retraining.py` use the same protocol. Workflows override only `training_data`.
- Gate (`mlops/model_gate.py`): accuracy and macro_f1 >= 0.80, no regression versus production, and identical evaluation dataset fingerprint. `scripts/evaluate_candidate.py` prints candidate/production metrics, deltas and every check, and writes `outputs/candidate/gate.json`.
- The demo drift (`scripts/generate_drift_demo.py`) only pads descriptions with whitespace, so `text_length` drifts while TF-IDF tokens, labels and model inputs are unchanged.


## Scheduled production drift monitoring

Run the `Production Drift Monitoring` GitHub Actions workflow daily or manually. The scheduled run checks `data/synthetic_incidents.csv` against `data/reference/drift_baseline.json`, uses PSI 0.10 as the warning threshold and 0.25 as the drift/retraining threshold, and uploads the complete report as an artifact.

When drift is detected on the default approved production dataset path, the workflow dispatches `Drift Retraining` with `demo_drift=false`. The retraining workflow keeps the existing fixed evaluation protocol, quality gate, model registration, and manual blue-green promotion boundary unchanged.

For a custom manual monitoring dataset, the workflow reports drift but does not auto-trigger retraining because the current retraining workflow is intentionally anchored to the approved repository production dataset path. Connect an ingestion process to stage the current production snapshot at that approved path before enabling unattended retraining from live data.
