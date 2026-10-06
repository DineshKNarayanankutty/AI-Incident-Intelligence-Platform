# AI Incident Intelligence Platform

Portfolio project for AI-300: Operationalizing Machine Learning and Generative AI Solutions.

This repository is intentionally phased. Phase 1 is local-only and does not deploy Azure resources.

## Phase 1: Local ML Foundation

Implemented in this phase:

- Synthetic incident dataset generation
- Incident data schema
- TF-IDF + Logistic Regression severity classifier
- Local MLflow tracking with model registration
- Evaluation metrics with a majority-class baseline
- Drift baseline artifact for later production monitoring
- Basic unit and smoke tests

Not implemented yet:

- Azure ML resources, pipelines, endpoint deployment, or Entra-protected inference
- FastAPI API layer
- Microsoft Foundry agent
- Prompt V1 vs V2 GenAI evaluation
- Application Insights / Azure Monitor tracing
- GitHub Actions CI/CD
- Bicep infrastructure

## Local Setup

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Generate the Phase 1 dataset:

```powershell
.\.venv\Scripts\python.exe -m src.data.generate_synthetic_data --output data/synthetic_incidents.csv --rows 400 --seed 42
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Train locally with MLflow tracking and local model registration:

```powershell
.\.venv\Scripts\python.exe -m src.training.train --data data/synthetic_incidents.csv --output-dir outputs/model --mlflow-tracking-uri sqlite:///outputs/mlflow/mlflow.db --register-model
```

Training writes local artifacts to `outputs/model/`, including:

- `model.joblib`
- `metrics.json`
- `label_order.json`
- `drift_baseline.json`
- `run_summary.json`

The synthetic data intentionally overlaps operational signals across adjacent severities, so the model has useful signal without trivially perfect metrics. The drift baseline captures reference distributions for incident metadata, severity labels, model predictions, and numeric operational fields. In later phases, production payloads can be compared against this baseline to detect data and prediction drift.

## Dataset Schema

Each incident record contains:

- Incident metadata: `incident_id`, `service`, `region`, `incident_type`
- Text fields: `title`, `description`
- Operational signals: `duration_minutes`, `affected_users`, `error_rate`, `latency_ms`
- Boolean risk signals: `has_data_loss`, `is_security_related`
- Target label: `severity`

Severity labels are `Low`, `Medium`, `High`, and `Critical`.
