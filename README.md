# AI Incident Intelligence Platform

Portfolio project for **AI-300: Operationalizing Machine Learning and Generative AI Solutions**.

This repository contains the code-ready platform path from the original Phase 1 local ML foundation through Azure ML, FastAPI, Microsoft Foundry, GenAIOps evaluation/observability, PSI-based drift detection and drift-gated retraining scaffolding, Bicep, CI/CD, tests, and documentation. Final candidate-model promotion/rollback is intentionally a later lifecycle step.

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
13. Exercise the drift-gated retraining workflow.

The committed `data/reference/drift_baseline.json` is the stable reference profile for clean CI/retraining runs. Drift uses PSI across categorical distributions and binned numeric features; `0.10` is the warning threshold and `0.25` is the default retraining/alert threshold. Generated `outputs/` and `mlruns/` remain local/transient.

## Current Azure SDK basis

The repository targets current Azure ML v2 and Microsoft Foundry SDK patterns. Azure ML supports registered data/environment/model references and managed online endpoint YAML; Foundry's current Python SDK uses `AIProjectClient` and agent-scoped OpenAI Responses clients.

See `docs/ai-300-mapping.md` for exam-domain mapping.
