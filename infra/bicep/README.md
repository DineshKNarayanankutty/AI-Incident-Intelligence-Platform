# Infrastructure as Code

`main.bicep` is the resource-group-scoped infrastructure definition. It declares the shared platform resources only; ML assets, models, endpoints, and Foundry agent versions remain application/ML lifecycle artifacts.

Resources:
- Storage Account
- Log Analytics
- Application Insights
- Key Vault with RBAC
- Azure Container Registry with admin auth disabled
- Azure Machine Learning workspace with system-assigned identity
- Microsoft Foundry/AIServices account and project

No deployment is performed by this repository's validation commands.

Before deployment, review:
1. Region and service availability.
2. Model quota and deployment name.
3. RBAC assignments required by your tenant.
4. Network/security requirements for the target environment.
