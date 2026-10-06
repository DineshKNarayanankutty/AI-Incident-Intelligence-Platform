# 7–10 Minute Demo

1. Show the Phase 1 dataset and local model artifacts.
2. Run `pytest` to show the local baseline remains healthy.
3. Start FastAPI locally and call `/predict`.
4. Call `/analyze` and show prompt versioning.
5. Open `genai/evaluation/dataset.jsonl` and explain the evaluation contract.
6. Run V1 and V2 evaluation locally.
7. Show the comparison logic and explain the promotion gate.
8. Walk through Azure ML `pipeline.yml`, registered model, and managed endpoint YAML.
9. Walk through Bicep and GitHub Actions without deploying.
10. Explain the production flow: drift → retraining → evaluation → approval → deployment → observability.
