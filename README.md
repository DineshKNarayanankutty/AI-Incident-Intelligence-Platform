# AI Incident Intelligence Platform

Portfolio project for **AI-300: Operationalizing Machine Learning and Generative AI Solutions**.

This repository contains the code-ready platform path from the original Phase 1 local ML foundation through Azure ML, FastAPI, Microsoft Foundry, GenAIOps evaluation/observability, PSI-based drift detection, scheduled drift monitoring, Azure ML candidate retraining, candidate-vs-production quality gating, blue-green deployment, rollback, Bicep, CI/CD, tests, and documentation.

> **Safety boundary:** this repository is code-ready, not deployed. No Azure resource creation is performed by the default local commands or test suite. Azure deployment workflows are explicit/manual.

## Phase 1 preserved

The original local implementation remains under `src/`:

- deterministic synthetic incident generation
- schema
- TF-IDF + Logistic Regression severity classifier
- MLflow local tracking and registration
- evaluation against majority baseline
- drift baseline

The new layers call the same feature construction/training code instead of creating a second model implementation.

## Repository map

```text
src/                       Phase 1 ML source of truth
azure_ml/                  Azure ML assets, components, pipeline, endpoint
app/                       FastAPI application and Azure client abstractions
genai/                     Foundry prompts, evaluation, optimization, telemetry
mlops/                     drift/retraining integration
infra/bicep/               Azure resource infrastructure
.github/workflows/         CI, infra, training, evaluation, deployment, retraining
tests/                     unit/config/integration stubs
docs/                      architecture, AI-300 mapping, runbook, demo
```

## Local execution

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
python scripts/validate_project.py
python -m src.training.train --register-model
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Local mode uses the Phase 1 `outputs/model/model.joblib` artifact and a deterministic local Foundry fallback. No Azure credentials are required.

## Azure execution

The Azure paths use:

- Azure ML v2 YAML for data, environment, component, pipeline, model, and managed online endpoint.
- Microsoft Entra authentication through `DefaultAzureCredential`.
- Microsoft Foundry `AIProjectClient` and an agent-scoped OpenAI Responses client.
- Application Insights/OpenTelemetry for cloud telemetry.
- Bicep for shared infrastructure.
- GitHub Actions OIDC rather than long-lived cloud credentials.

Azure identifiers are environment variables/GitHub configuration, not source-code constants.

## Recommended implementation order

1. Run all local tests.
2. Build/inspect Bicep.
3. Provision infrastructure through an approved environment.
4. Register AML assets.
5. Run training pipeline.
6. Register/promote model.
7. Create managed endpoint.
8. Create/configure Foundry agent.
9. Run GenAIOps evaluation.
10. Connect FastAPI to Azure backends.
11. Enable Application Insights telemetry.
12. Run the PSI-based drift check against the committed reference profile.
13. Enable production incident event storage in Azure Blob Storage.
14. Run the `Production Drift Monitoring` workflow and verify the current production snapshot.
15. Exercise the drift-gated retraining workflow.
16. For a controlled end-to-end demo, run Drift Retraining with `demo_drift=true`; this generates a temporary dataset with whitespace-only text-length drift without changing the model tokens or committed production dataset.
17. Candidate training uses the drifted data for fitting but evaluates against the same fixed reference holdout protocol used for production model v1.
18. Review the candidate-vs-production quality gate result before model registration.
19. Validate the blue-green candidate rollout and rollback workflows.

The committed `data/reference/drift_baseline.json` is the stable reference profile for clean CI/retraining runs. Drift uses PSI across categorical distributions and binned numeric features; `0.10` is the warning threshold and `0.25` is the default retraining/alert threshold. Generated `outputs/` and `mlruns/` remain local/transient.

## Current Azure SDK basis

The repository targets current Azure ML v2 and Microsoft Foundry SDK patterns. Azure ML supports registered data/environment/model references and managed online endpoint YAML; Foundry's current Python SDK uses `AIProjectClient` and agent-scoped OpenAI Responses clients.

See `docs/ai-300-mapping.md` for exam-domain mapping.


### Model promotion and rollback

Candidate models are registered only after the drift-triggered quality gate passes. Production traffic is changed separately through the `Azure ML Blue-Green Deployment` workflow. Candidate deployments receive 0% traffic during validation, then may be promoted to 100% after direct and live smoke tests. The `Azure ML Rollback` workflow restores the previous deployment without rebuilding it.
### Scheduled production drift monitoring

The `Production Drift Monitoring` workflow runs daily and can also be started manually. In Azure, the FastAPI application records prediction observations as append-only JSON events in the `production` blob container using its managed identity. The monitoring workflow authenticates with GitHub Actions OIDC, downloads the event stream, builds a current unique-incident CSV snapshot, and evaluates it against `data/reference/drift_baseline.json`. PSI >= 0.10 is a warning and PSI >= 0.25 is treated as drift.

When drift is detected, the current feature snapshot is published to `production/snapshots/current/incidents.csv`. Retraining is dispatched only when a separate ground-truth severity label is available for the training rows; model predictions are never reused as supervised labels. The labeled snapshot is published to `production/training/current/incidents.csv` and passed to the existing `Drift Retraining` workflow. The retraining workflow still uses the fixed clean evaluation set and the same strict quality gate. Model promotion remains a separate manual blue-green approval step.

The GitHub Actions service principal needs `Storage Blob Data Reader` on the `production` container, while the FastAPI App Service managed identity needs `Storage Blob Data Contributor`. Bicep supports assigning both when `githubActionsPrincipalObjectId` is supplied; otherwise run `scripts/configure_production_storage_rbac.ps1` once with the existing `AZURE_RESOURCE_GROUP` and `AZURE_CLIENT_ID`. The built-in role IDs follow Microsoft Azure RBAC: Storage Blob Data Reader `2a2b9908-6ea1-4ae2-8e65-a410df84e7d1` and Storage Blob Data Contributor `ba92f5b4-2d11-453d-a403-e96b0029c9fe`.

For a demo environment with no historical API traffic, use `python -m scripts.seed_production_events --source data/synthetic_incidents.csv --account-name <storage-account> --container production --overwrite` after the RBAC setup. This bootstraps labeled historical events in storage without changing the committed production dataset. New API observations remain prediction-only until an approved labeling process supplies ground truth.
