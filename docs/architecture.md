# Architecture

```text
                         ┌──────────────────────────┐
                         │      FastAPI API          │
                         │ /predict   /analyze       │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
             Local inference                     Azure ML endpoint
             Phase 1 artifact                     Entra/AAD token
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      │
                              Severity prediction
                                      │
                                      ▼
                           Foundry agent analysis
                           Prompt V1 / Prompt V2
                                      │
                                      ▼
                        Evaluation + tracing + metrics
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                    Drift profile             CI/CD gates
                         │                         │
                         ▼                         ▼
                  Retraining trigger       Azure ML pipeline
```

## Design choices

- Phase 1 training code remains the source of truth for feature construction and model training.
- Azure ML is responsible for managed training/orchestration, model registration, and managed online serving.
- FastAPI owns application contracts and hides whether inference is local or remote.
- Foundry owns agent execution; prompt files are versioned in Git so changes are reviewable.
- Evaluation is treated as a release gate rather than an informal demo.
- Application Insights/OpenTelemetry is an optional cloud sink; local execution requires no Azure telemetry.
- No secret values are committed; GitHub Actions uses OIDC secrets and runtime environment variables.


### Drift detection

The MLOps layer builds a committed known-good reference profile and compares current incident data with PSI. Categorical features are compared directly; numeric features are binned using edges learned from the reference profile. A PSI of 0.10 is a warning and 0.25 is the default drift/retraining threshold.

### Candidate retraining gate

Drift detection can trigger an Azure ML training job. The resulting candidate artifacts are evaluated against the committed production metrics baseline. A candidate must satisfy minimum quality and non-regression checks before Azure ML registration. Deployment and traffic promotion remain separate lifecycle steps so the production `incident-severity:1` model is not changed automatically.

## Model promotion path

```text
Drift detected
      ↓
Azure ML candidate training
      ↓
Candidate quality gate vs production
      ↓
Register incident-severity:<candidate-version>
      ↓
Blue/green candidate deployment (0% traffic)
      ↓
Direct candidate invocation
      ↓
Optional promotion
      ↓
100% candidate traffic
      ↓
Live smoke test
   ↙ failure       ↘ success
rollback            production
```

Only the deployment workflow changes endpoint traffic. The retraining workflow never changes production traffic.
