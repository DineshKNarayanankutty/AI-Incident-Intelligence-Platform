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
