# Infrastructure as Code

`main.bicep` is the resource-group-scoped infrastructure definition. It provisions the shared platform foundation and the FastAPI hosting layer. ML assets/models/endpoints and Foundry agents remain lifecycle artifacts managed by Azure ML/Foundry workflows.

Resources:
- Storage Account
- Log Analytics
- Application Insights
- Key Vault with RBAC
- Azure Container Registry with admin auth disabled
- Azure Machine Learning workspace with system-assigned identity
- Microsoft Foundry/AIServices account and project
- Linux App Service Plan (B1 by default)
- Linux App Service for FastAPI with system-assigned identity
- Least-privilege RBAC for FastAPI to invoke Azure ML online endpoints
- Foundry Agent Consumer RBAC for FastAPI at project scope

The App Service uses Python 3.11 and starts FastAPI with Uvicorn. Azure ML scoring URI and Foundry agent name are intentionally blank until those artifacts exist; the deployment workflows populate them later.

No secrets are stored in Bicep. Authentication is via managed identity.

Before deployment, review:
1. Region and service/model availability.
2. Global availability of storage, ACR, and App Service names.
3. RBAC permissions in your tenant.
4. Network/security requirements for the target environment.
