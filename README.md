# AI Incident Intelligence Platform: Complete Beginner's Guide
[![CI](https://github.com/DineshKNarayanankutty/AI-Incident-Intelligence-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DineshKNarayanankutty/AI-Incident-Intelligence-Platform/actions/workflows/ci.yml)

This guide takes you from **an empty computer** to **a working project**, one small step at a time. You do not need to understand the code. You only need to copy the commands exactly and check that you see what the guide says you should see.

> **How much to trust each part (please read):**
> - **Part 2 (run on your own computer)** was run end to end by me on the actual code. Every command and every "you should see" in it comes from a real run.
> - **Parts 3 to 7 (Azure cloud and GitHub)** follow the project's own files (Bicep, Azure ML YAML, GitHub workflows). I had no Azure subscription, so I did **not** run them. If a command fails, the Troubleshooting section (Part 8) covers the likely causes.
> - Before you put anything on the internet, read **Part 5** and `SECURITY_REVIEW.md`. The web API has **no login** as shipped.

---

## Part 0: What is this project?

Imagine a company's website breaks. Someone writes a short report: *what broke, how many customers, how long*. This project:

1. **Predicts how serious the incident is** (Low, Medium, High, Critical) using a small machine-learning model.
2. **Asks an AI assistant to explain** the risk and suggest first steps (this part needs Microsoft Azure).
3. **Watches for "drift"**: if new incidents start to look very different from the ones the model learned from, it raises a flag.
4. **Retrains and swaps models safely** (a "blue/green" switch, with a rollback button).

You can do it at three levels:

| Level | What you get | Cost | Time | Needs |
|---|---|---|---|---|
| **A. Local** (Part 2) | Everything except the real AI explanations. Runs on your laptop. | Free | about 30 min | Python |
| **B. Azure** (Parts 3 to 5) | The full cloud version with a public web address and real AI answers | **Costs real money** (some parts run 24/7) | half a day | Azure account |
| **C. GitHub automation** (Part 6) | Buttons that train, test, deploy, monitor and roll back for you | Same as B | 1 to 2 hours | GitHub account |

**Start with A.** Only continue if you want the cloud version.

**About the data:** the incidents are *made up by a program* (synthetic). The model's 80% accuracy is on made-up data and says nothing about real-world performance. This is a learning and portfolio project.

---

## Part 1: Install the tools

### 1.1 Open a "terminal"
A terminal is a window where you type commands.
- **Windows:** press the Start button, type `PowerShell`, press Enter.
- **Mac:** press Cmd+Space, type `Terminal`, press Enter.
- **Linux:** you know where it is.

### 1.2 Install Python (needed for everything)
1. Go to https://www.python.org/downloads/ and install **Python 3.11** (3.10, 3.11 and 3.12 work; I tested 3.12).
2. **Windows:** on the first installer screen, **tick "Add python.exe to PATH"**. This is the most common mistake.
3. Close and reopen your terminal, then check:
   ```
   python --version
   ```
   You should see `Python 3.11.x` (or similar). On Mac/Linux, if that fails, use `python3 --version` and type `python3` wherever this guide says `python`.

### 1.3 Only for Parts 3 to 7 (cloud)
Install these later, when you get there:
- **An Azure account with a subscription:** https://azure.microsoft.com/free
- **Azure CLI:** https://learn.microsoft.com/cli/azure/install-azure-cli (check with `az --version`)
- **Git:** https://git-scm.com/downloads (check with `git --version`)
- **A GitHub account:** https://github.com

---

## Part 2: Run everything on your own computer (free, verified)

### Step 2.1: Open the project folder
Unzip `AI_Incident_Intelligence_Platform.zip`. In the terminal, go into the folder (the one that contains a file named `pyproject.toml`):

```
cd path\to\AI_Incident_Intelligence_Platform
```
(Mac/Linux use `/` instead of `\`.) **Every command in this guide must be run from this folder.**

Now delete the leftover files from the original author's computer. These are not needed and the SQLite file and `run_summary.json` files inside contain his Windows username:

- **Windows PowerShell:**
  ```powershell
  Remove-Item -Recurse -Force outputs, mlruns, .pytest_cache -ErrorAction SilentlyContinue
  Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
  ```
- **Mac/Linux:**
  ```bash
  rm -rf outputs mlruns .pytest_cache
  find . -name __pycache__ -type d -prune -exec rm -rf {} +
  ```

### Step 2.2: Create a private Python workspace (a "virtual environment")
This keeps the project's software separate from everything else on your computer.

- **Windows PowerShell:**
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
  If it says *"running scripts is disabled"*, run this once and try again:
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
- **Mac/Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

✅ **You should see** `(.venv)` at the start of your command line. If you close the terminal, you must run the activate line again next time.

### Step 2.3: Install the project's software
```
python -m pip install --upgrade pip
pip install -r requirements.txt
```
This takes a few minutes and prints a lot of text. That is normal. ✅ It is done when you get your command line back with no red "ERROR" at the end.

### Step 2.4: Run the automatic checks
```
python -m pytest -q
```
✅ **You should see** (in under a minute): `72 passed, 1 skipped`, followed by some yellow "warnings". Warnings are fine. The skipped test needs Azure.

```
python scripts/validate_project.py
```
✅ **You should see:** `Validated 28 required project artifacts; no Azure calls were made.`

### Step 2.5: Train the model
```
python -m src.training.train --register-model
```
✅ **You should see** a block of text ending with something like:
```
"accuracy": 0.8,
"macro_f1": 0.809...
"registered_model_name": "incident-severity-tfidf-logreg",
"registered_model_version": 1,
```
(The version number goes up by one each time you run this. Warnings above the block are normal.) A new folder `outputs/model/` now holds `model.joblib`. That file **is** the trained model.

### Step 2.6: Start the web API
```
uvicorn app.main:app --reload
```
✅ **You should see** `Uvicorn running on http://127.0.0.1:8000`. Leave this window open.

Open your browser at **http://127.0.0.1:8000/docs**. You will see an interactive page listing four items: `/health`, `/metrics`, `/predict`, `/analyze`.

**Try the prediction:**
1. Click **POST /predict**, then **Try it out**.
2. Replace the box contents with this and click **Execute**:
   ```json
   {
     "incident_id": "INC-TEST-1",
     "title": "Orders availability incident",
     "description": "Elevated latency and intermittent request failures.",
     "service": "orders",
     "region": "westus",
     "incident_type": "availability",
     "customer_impact": "broad",
     "detected_by": "on_call",
     "duration_minutes": 299,
     "affected_users": 396,
     "error_rate": 0.1735,
     "latency_ms": 310,
     "has_data_loss": false,
     "is_security_related": false
   }
   ```
✅ **You should see** a response like: `"severity": "Medium"`, `"confidence": 0.47...`, `"model_backend": "local"`, plus a `trace_id`.

**Try the explanation:** use **POST /analyze** with `{"incident": <the same JSON as above>, "include_explanation": true}`. In local mode the "analysis" is a fixed placeholder sentence starting `LOCAL DEMO ANALYSIS`. That is expected. Real AI-written answers need the Azure part (Part 4).

To stop the server: click the terminal window and press **Ctrl+C**.

### Step 2.7: Test the "AI answer quality" checker
```
python -m genai.evaluation.runner --backend local --prompt both --quality-gate
```
✅ **You should see** `QUALITY GATE: PASS` at the end.
*Honest note:* in local mode the program uses a fake "answerer" that ignores the prompt, so version 1 and version 2 of the prompt score **exactly the same**. This only proves the machinery works. Real prompt comparison needs `--backend foundry` on Azure.

### Step 2.8: Test the drift detector
**Normal data (no drift expected):**
- Windows: `python -m mlops.drift_check | Select-String '"drift_detected"'`
- Mac/Linux: `python -m mlops.drift_check | grep '"drift_detected"'`

✅ **You should see** `"drift_detected": false`

**Deliberately changed data (drift expected):**
```
python -m scripts.generate_drift_demo
```
- Windows: `python -m mlops.drift_check --data outputs/drift_demo/synthetic_incidents_drifted.csv | Select-String '"drift_detected"'`
- Mac/Linux: `python -m mlops.drift_check --data outputs/drift_demo/synthetic_incidents_drifted.csv | grep '"drift_detected"'`

✅ **You should see** `"drift_detected": true`. The demo makes descriptions much longer by adding blank spaces, so the detector reports `numeric.text_length` as drifted (score about 12.5; the alarm level is 0.25).

🎉 **Part 2 complete.** You have trained a model, served it through a web API, and run the quality and drift checks.

### What the main folders are for
| Folder | In plain words |
|---|---|
| `src/` | Makes fake incidents, trains the model, measures drift |
| `app/` | The web API (what people call to get predictions) |
| `genai/` | The AI instructions (`prompts/`), the answer checker (`evaluation/`), logging (`tracing/`, `monitoring/`) |
| `mlops/` | Drift check, retraining logic, "is the new model good enough?" gate |
| `azure_ml/` | Instructions for Azure's machine-learning service |
| `infra/bicep/` | A blueprint that builds the Azure resources |
| `.github/workflows/` | The GitHub automation buttons |
| `data/` | The incident data and reference files (do not edit) |
| `scripts/` | Helper tools |
| `tests/` | The automatic checks |

---

## Part 3: Prepare for Azure

### 3.1 Understand the cost first
Azure bills you for what you leave running. In this project the things that cost money **even when nobody uses them** are the **web app plan** (S1) and the **machine-learning endpoint** (one virtual machine, always on once created). Training compute shuts down when idle. AI answers are billed per use. Before you start:
1. In the Azure portal, search **Cost Management → Budgets** and create a small monthly budget with an email alert.
2. Remember **Part 7 (Clean up)** when you finish.

### 3.2 Choose your names
Azure needs globally unique names. Pick a **prefix**: 3 to 12 characters, **lowercase letters and digits only** (for example `incabc123`). Most resource names are built from it, and some (storage, key vault) have tight length limits.

Write down your choices (you will paste them into commands as you go):

| Placeholder used below | Your value | Example |
|---|---|---|
| `<PREFIX>` | | `incabc123` |
| `<RG>` (resource group) | | `rg-incident-demo` |
| `<LOCATION>` | a region close to you | `centralus` |
| `<WORKSPACE>` | always `<PREFIX>-ml` | `incabc123-ml` |
| `<APP>` (web app) | always `<PREFIX>-api` | `incabc123-api` |
| `<APPI>` (App Insights) | always `<PREFIX>-appi` | `incabc123-appi` |
| `<STORAGE>` | always `<PREFIX>st` | `incabc123st` |
| `<ENDPOINT>` | keep as is | `incident-severity-endpoint` |

**Every time a command below contains `<SOMETHING>`, replace the whole thing, including the angle brackets, with your value.**

### 3.3 Replace the original author's names
The project still contains the author's real resource names. Find them:
- Windows: `Get-ChildItem -Recurse -File -Exclude *.pyc,*.pkl,*.db | Select-String "77a8b195|rg-ai-incident" | Select Path,LineNumber`
- Mac/Linux: `grep -rn "77a8b195\|rg-ai-incident" --exclude-dir=.venv --exclude-dir=.git --exclude=*.pyc .`

Edit these (any text editor, such as Notepad or VS Code):
1. `infra/bicep/main.bicepparam`: change `location` to `<LOCATION>` and `namePrefix` to `<PREFIX>`.
2. `.env.example` (bottom two lines) and `scripts/run_local_azure.ps1` (lines 6 to 12): replace with your names. (Optional, only used for local runs against Azure.)
3. `scripts/compare_live_models.py` is a one-off script for the author's specific setup. Ignore it.

### 3.4 Sign in to Azure
```
az login
az account set --subscription "<YOUR SUBSCRIPTION NAME OR ID>"
az account show
```
✅ `az account show` should print your subscription.

First-time subscriptions may need these services switched on (each command takes a few seconds; run all):
```
az provider register --namespace Microsoft.MachineLearningServices
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.Web
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.OperationalInsights
```

**Your account's role:** the infrastructure step creates permissions for other services, so your account needs **Owner** (or Contributor plus User Access Administrator) on the resource group. If you created the subscription yourself, you already have it.

### 3.5 Check you have virtual-machine quota
The training cluster uses size `Standard_E4ads_v5` and the endpoint uses `Standard_D2ds_v5`. New subscriptions sometimes have zero quota for them. Check in the Azure portal: **Azure Machine Learning studio → Quota**. If you have none:
- For the endpoint, edit `instance_type` in `azure_ml/endpoints/managed-deployment.yml`.
- For the training cluster, edit `size` in `azure_ml/compute/compute.yml` **and also** the same size name in `scripts/validate_project.py` (line 63) and `tests/test_project_artifacts.py` (line 60), or your own tests will fail on purpose.

---

## Part 4: Build the Azure version

Run these in order from the project folder, with `(.venv)` active. After each step, check the ✅ line before moving on.

### Step 4.1: Create the resource group (a folder in Azure that holds everything)
```
az group create --name <RG> --location <LOCATION>
```
✅ Output contains `"provisioningState": "Succeeded"`.

### Step 4.2: Build the infrastructure
The blueprint (`main.bicep`) insists on a few values that only exist *after* the machine-learning endpoint is built, which creates a chicken-and-egg problem on a first run. We give it **temporary placeholder values** now and replace them with real ones in Step 4.8.

Set the placeholders in the same terminal you will run the deploy from:

- **Windows PowerShell:**
  ```powershell
  $env:AZURE_ML_SCORING_URI = "https://placeholder.invalid/score"
  $env:AZURE_ML_DEPLOYMENT_NAME = "blue"
  $env:AZURE_ML_MODEL_VERSION = "1"
  $env:FOUNDRY_AGENT_NAME = "incident-operations-agent"
  $env:FOUNDRY_AGENT_VERSION = ""
  $env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "incident-gpt"
  ```
- **Mac/Linux:**
  ```bash
  export AZURE_ML_SCORING_URI="https://placeholder.invalid/score"
  export AZURE_ML_DEPLOYMENT_NAME="blue"
  export AZURE_ML_MODEL_VERSION="1"
  export FOUNDRY_AGENT_NAME="incident-operations-agent"
  export FOUNDRY_AGENT_VERSION=""
  export AZURE_AI_MODEL_DEPLOYMENT_NAME="incident-gpt"
  ```

First do a "dry run" that changes nothing and lists what would be created:
```
az deployment group what-if --resource-group <RG> --parameters infra/bicep/main.bicepparam
```
If it lists about 10 resources to create and no errors, build for real (takes several minutes):
```
az deployment group create --resource-group <RG> --parameters infra/bicep/main.bicepparam
```
✅ Then run `az resource list --resource-group <RG> --output table`. You should see: a storage account, Log Analytics workspace, Application Insights, Key Vault, Container Registry, ML workspace, an AI Services account (plus its project), an App Service plan and a web app.

Save the AI project address for later:
```
az deployment group show --resource-group <RG> --name main --query properties.outputs.foundryProjectEndpoint.value -o tsv
```
(If that says the deployment is not found, run `az deployment group list --resource-group <RG> -o table` to see its real name.) It looks like `https://<PREFIX>-ai.services.ai.azure.com/api/projects/<PREFIX>-project`. Call it `<PROJECT_ENDPOINT>`.

### Step 4.3: Create the AI model deployment (by hand in the portal)
The blueprint creates the AI *project* but not the AI *model* inside it.
1. Go to https://ai.azure.com and sign in. Open the project named `<PREFIX>-project`.
2. Find **Models + endpoints → Deploy model** and choose a chat model that your region offers.
3. **Name the deployment exactly `incident-gpt`.** The code looks for that name. Which model you pick is up to you; any chat model works.

If a later step says you lack permission, give your own account the **Azure AI User** role on the project (Access control (IAM) → Add role assignment).

### Step 4.4: Create the AI agent
- **Windows PowerShell:**
  ```powershell
  $env:AZURE_AI_PROJECT_ENDPOINT = "<PROJECT_ENDPOINT>"
  $env:FOUNDRY_AGENT_NAME = "incident-operations-agent"
  python scripts/create_foundry_agent.py
  ```
- **Mac/Linux:**
  ```bash
  export AZURE_AI_PROJECT_ENDPOINT="<PROJECT_ENDPOINT>"
  export FOUNDRY_AGENT_NAME="incident-operations-agent"
  python scripts/create_foundry_agent.py
  ```
✅ It prints `Agent name: incident-operations-agent` and `Agent version: <number>`. Write the number down as `<AGENT_VERSION>`.

### Step 4.5: Set up the machine-learning pieces
Tell the Azure ML tool where to work, so you do not repeat it in every command:
```
az extension add --name ml --yes
az configure --defaults group=<RG> workspace=<WORKSPACE>
```
Then run each of these in order. Each one takes seconds to minutes:

```
az ml compute create --file azure_ml/compute/compute.yml
az ml data create --file azure_ml/data/incident-data.yml
az ml environment create --file azure_ml/environments/training-environment.yml
az ml environment create --file azure_ml/environments/serving-environment.yml
```
Register the model you trained in Step 2.5 (the file `outputs/model/model.joblib` **must exist**):
```
az ml model create --file azure_ml/model.yml
```
✅ Check with `az ml model list --output table`. You should see `incident-severity` version `1`.

### Step 4.6: Create the live prediction endpoint
```
az ml online-endpoint create --file azure_ml/endpoints/managed-endpoint.yml
az ml online-deployment create --file azure_ml/endpoints/managed-deployment.yml --all-traffic
```
The second command is slow (often 10 to 20 minutes the first time, because Azure builds the software image). This is the part that starts billing continuously.

✅ Test it:
```
az ml online-endpoint invoke --name incident-severity-endpoint --request-file azure_ml/endpoints/test-request.json
```
You should get JSON containing `"predictions"` with a `"severity"`.

Get the endpoint's address:
```
az ml online-endpoint show --name incident-severity-endpoint --query scoring_uri -o tsv
```
Call that `<SCORING_URI>`.

*(Optional)* To see cloud training work: `az ml job create --file azure_ml/pipeline.yml`, then follow it in https://ml.azure.com under **Jobs**.

### Step 4.7: Put the website code online
Package the app and upload it (no GitHub needed):
```
python scripts/package_api.py --out build/api-package
az webapp deploy --resource-group <RG> --name <APP> --src-path build/api-package.zip --type zip
```
✅ You should see a deployment-succeeded message. (If the uploaded file name is wrong on your system, check that `build/api-package.zip` exists.)

### Step 4.8: Replace the placeholders with the real values
**Do not re-run the full infrastructure deployment for this.** It would overwrite the web app's settings. Use this narrower command:
```
az webapp config appsettings set --resource-group <RG> --name <APP> --settings AZURE_ML_SCORING_URI=<SCORING_URI> AZURE_ML_DEPLOYMENT_NAME=blue AZURE_ML_MODEL_VERSION=1 FOUNDRY_AGENT_NAME=incident-operations-agent FOUNDRY_AGENT_VERSION=<AGENT_VERSION> AZURE_AI_MODEL_DEPLOYMENT_NAME=incident-gpt
```
The app restarts. Wait a minute or two.

### Step 4.9: Check that it all works
Open `https://<APP>.azurewebsites.net/health` in your browser. ✅ You should see `"status":"ok"`, `"inference_backend":"azureml"`, `"foundry_backend":"azure"`. (The first start can take several minutes while Azure installs the packages.)

Then run the full check:
```
python scripts/smoke_test.py https://<APP>.azurewebsites.net
```
✅ You should see `/health 200`, `/predict 200 ... backend=azureml`, `/analyze 200 ...` and `Smoke test passed.` The `/analyze` answer is now written by the real AI.

If something fails, jump to **Part 8**.

### Step 4.10 (optional): Fill in demo "production" data for the drift monitor
The drift monitor reads from the storage account's `production` container. Your own account has management rights but **no permission to read or write blob data** until you grant it:
```
az role assignment create --assignee "<YOUR EMAIL>" --role "Storage Blob Data Contributor" --scope "/subscriptions/<SUBSCRIPTION ID>/resourceGroups/<RG>/providers/Microsoft.Storage/storageAccounts/<STORAGE>/blobServices/default/containers/production"
```
Wait a couple of minutes, then:
```
python -m scripts.seed_production_events --source data/synthetic_incidents.csv --account-name <STORAGE> --container production --overwrite
```
✅ `Seeded 400 production event blobs ...`. (This also stores the true severity for each demo incident so that retraining has labels. Real traffic never has them.)

---

## Part 5: Lock the door (do this before you share the address with anyone)

As shipped, **anyone on the internet who knows `https://<APP>.azurewebsites.net` can call your API**, run up your AI bill, and write junk into your data store. Full details are in `SECURITY_REVIEW.md` (findings S1, S2, S3).

**Simplest fix, allow only your own computer.** Find your public IP address (search "what is my IP"), then:
```
az webapp config access-restriction add --resource-group <RG> --name <APP> --rule-name my-computer --action Allow --ip-address <YOUR.IP.ADDRESS>/32 --priority 100
```
Once an "Allow" rule exists, everyone else is blocked. Add the same rule for each place you work from.

**Better fix, require a Microsoft sign-in:** Azure portal → your web app → **Authentication → Add identity provider → Microsoft**, and choose **Require authentication**.

Be aware that both options also block the automatic `/health` check in the GitHub deploy workflow and `scripts/smoke_test.py` from other computers. Run the smoke test from an allowed computer, and in the workflow either allow GitHub's addresses or remove that check.

**Also:** do not type real customer names, personal data or passwords into incident descriptions. They are saved to storage and processed by the AI.

For the code-level fixes (input checks, rate limits, a login in the code, closing the workflow loopholes), follow the fix order at the bottom of `SECURITY_REVIEW.md`.

---

## Part 6: Add the GitHub automation (optional)

This gives you "Run workflow" buttons for training, evaluation, deployment, drift monitoring, retraining and rollback.

### Step 6.1: Put the project on GitHub (private repository recommended)
1. On GitHub, click **New repository**, name it, choose **Private**, and **do not** add a README. Copy the repository address.
2. In your project folder:
   ```
   git init -b main
   git add .
   ```
3. **Safety check before committing.** This must print nothing:
   - Windows: `git ls-files | Select-String "outputs/|mlruns/|__pycache__|\.env$"`
   - Mac/Linux: `git ls-files | grep -E "outputs/|mlruns/|__pycache__|\.env$"`

   If it prints anything, you skipped the Step 2.1 cleanup, or `.gitignore` is not working. Fix that first.
4. ```
   git commit -m "Initial commit"
   git remote add origin <YOUR REPOSITORY ADDRESS>
   git push -u origin main
   ```

**Immediately after pushing**, the scheduled **Production Drift Monitoring** workflow starts running every day at 02:17 UTC and will fail daily (with emails) until Azure is connected. Either finish Part 6 now or disable it: GitHub → **Actions** → that workflow → **⋯ → Disable workflow**.

### Step 6.2: Create a secret-free login for GitHub (OIDC)
This lets GitHub sign in to Azure **without any password stored anywhere**.
```
az ad app create --display-name incident-github
```
Copy the `appId` value from the output (`<APP_ID>`), then:
```
az ad sp create --id <APP_ID>
```
Create a file named `credential.json` containing (replace the two words):
```json
{
  "name": "github-production",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<GITHUB_USERNAME>/<REPOSITORY_NAME>:environment:production",
  "audiences": ["api://AzureADTokenExchange"]
}
```
```
az ad app federated-credential create --id <APP_ID> --parameters credential.json
```
The `:environment:production` part matters: only runs that go through your protected `production` environment can log in. If you also want to run the **Infrastructure** workflow (which defaults to an environment called `dev`), repeat with `"name": "github-dev"` and `environment:dev`.

### Step 6.3: Give that login permission
```
az role assignment create --assignee <APP_ID> --role Contributor --scope /subscriptions/<SUBSCRIPTION ID>/resourceGroups/<RG>
```
For blob data, the monitoring workflow both **reads** events and **writes** snapshots, so **Reader is not enough** (the writes would fail). Grant write access to the one container:
```
az role assignment create --assignee <APP_ID> --role "Storage Blob Data Contributor" --scope "/subscriptions/<SUBSCRIPTION ID>/resourceGroups/<RG>/providers/Microsoft.Storage/storageAccounts/<STORAGE>/blobServices/default/containers/production"
```
Be aware this means a hijacked pipeline could edit your stored events (`SECURITY_REVIEW.md`, finding I1).

### Step 6.4: Create the protected environments
GitHub repository → **Settings → Environments → New environment** → name it `production`. Tick **Required reviewers** and add yourself, so every cloud workflow waits for your approval. (Optionally create `dev` too.)

### Step 6.5: Add the secrets and variables
In the `production` environment (and `dev` if you made it), add these **secrets**:

| Secret | Value | How to get it |
|---|---|---|
| `AZURE_CLIENT_ID` | `<APP_ID>` | from Step 6.2 |
| `AZURE_TENANT_ID` | your tenant ID | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | your subscription ID | `az account show --query id -o tsv` |

Then **Settings → Secrets and variables → Actions → Variables** (repository level) and add:

| Variable | Value |
|---|---|
| `AZURE_RESOURCE_GROUP` | `<RG>` |
| `AZURE_ML_WORKSPACE` | `<WORKSPACE>` |
| `AZURE_ML_ENDPOINT_NAME` | `incident-severity-endpoint` |
| `AZURE_API_APP_NAME` | `<APP>` |
| `AZURE_APP_INSIGHTS_NAME` | `<APPI>` |
| `AZURE_AI_PROJECT_ENDPOINT` | `<PROJECT_ENDPOINT>` |
| `FOUNDRY_AGENT_NAME` | `incident-operations-agent` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `incident-gpt` |

### Step 6.6: Use the buttons
On GitHub, open **Actions**, pick a workflow on the left, click **Run workflow**, then approve it if asked. Suggested order:

| # | Workflow | What it does | ✅ Success looks like |
|---|---|---|---|
| 1 | **CI** | Runs automatically on every push to `main` | Green tick |
| 2 | **Infrastructure** | Safe dry run only (never changes Azure) | Green tick, what-if listing |
| 3 | **FastAPI Deployment** | Tests, packages and deploys the web app, then checks `/health` | Green tick |
| 4 | **Azure ML Training** | Trains in the cloud | Job shows in ml.azure.com |
| 5 | **GenAIOps Evaluation** | Scores AI answers (choose `foundry`) | `QUALITY GATE: PASS` |
| 6 | **Production Drift Monitoring** | Daily drift check on stored events | Summary page with `drift_detected` |
| 7 | **Drift Retraining** | Choose `demo_drift = true` for a safe demo | A new model version plus a "gate" result in the artifacts |
| 8 | **Azure ML Blue-Green Deployment** | Enter the new `model_version`. Run once with `promote` off, then again with it on | New model serves live traffic |
| 9 | **Azure ML Rollback** | Emergency undo | Traffic back on the other slot |

**Cautions:**
- **Type only plain values** into text boxes (numbers like `0.8`, or `training/current/incidents.csv`). Two of the workflows pass these boxes straight into a shell command (`SECURITY_REVIEW.md`, finding G1).
- **Rollback switches to whichever slot is idle.** If your last run was "promote off", that idle slot holds the *unapproved new* model. Use Rollback only right after a promotion, or check first (finding G5).
- Promotion's success message is not fully trustworthy (finding G6). After promoting, check traffic with `az ml online-endpoint show --name incident-severity-endpoint --query traffic`.

---

## Part 7: Clean up (stop the billing)

Delete everything in one go:
```
az group delete --name <RG> --yes --no-wait
```
Some Azure services keep deleted names reserved, which blocks re-using the same prefix. Release them:
```
az keyvault purge --name <PREFIX>-kv
az cognitiveservices account purge --name <PREFIX>-ai --resource-group <RG> --location <LOCATION>
```
(Wait until the group deletion finishes first; if the commands say "not found", they are already gone.)

Remove the GitHub login: `az ad app delete --id <APP_ID>`.

The blueprint also creates a custom permission role called *AI Incident ML Endpoint Invoker*, which may outlive the group. See it with `az role definition list --name "AI Incident ML Endpoint Invoker"` and delete with `az role definition delete --name "AI Incident ML Endpoint Invoker"`.

Finally, confirm in the portal (**Resource groups**) that `<RG>` is gone.

---

## Part 8: Troubleshooting

| What you see | Why | What to do |
|---|---|---|
| `python is not recognized` | Python not on PATH | Reinstall and tick "Add python.exe to PATH"; reopen the terminal |
| `running scripts is disabled` | Windows safety setting | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again |
| No `(.venv)` in front of the line | Workspace not active | Re-run the activate command from Step 2.2 |
| `No module named 'src'` (or `app`, `genai`) | You are in the wrong folder | `cd` into the folder with `pyproject.toml`; use `python -m ...` exactly as written |
| API fails with `outputs/model/model.joblib` not found | You haven't trained yet | Run Step 2.5, then start the API again |
| `Address already in use` | Port 8000 is taken | `uvicorn app.main:app --reload --port 8001` |
| pytest fails after you changed the cluster size | The tests check the size on purpose | Edit both places listed in Step 3.5 |
| Copying `.env.example` to `.env` has no effect | Nothing in the project reads `.env` files | Set variables in the terminal as in Step 4.2, or use `uvicorn ... --env-file .env` |
| `what-if` says an environment variable is missing | Placeholders not set in *this* terminal | Re-run the six lines in Step 4.2 in the same window |
| `what-if` complains about an unknown resource type or API version | The blueprint uses a preview Azure version that your region or CLI may not support | Update the Azure CLI (`az upgrade`), then try another region; if it persists, change the `@…` version on that resource in `main.bicep` to one your CLI lists |
| `AuthorizationFailed` during infrastructure deploy | You lack Owner rights | Use an Owner account on the resource group |
| `QuotaExceeded` / cannot create VM | No quota for that VM size | Step 3.5 |
| `403` / `AuthorizationPermissionMismatch` on blob steps | Data-level role missing (management rights are not enough) | Step 4.10 role command; wait a few minutes |
| Web app shows "Application Error" | Startup or packaging problem | `az webapp log tail --resource-group <RG> --name <APP>` |
| `/predict` returns 500 in Azure | Wrong scoring URI, or the web app cannot call the endpoint yet | Re-check Step 4.8 values; wait ~10 minutes after the first deploy for permissions to spread |
| `/analyze` returns 500 in Azure | AI model deployment/agent missing, or permission not spread yet | Confirm Step 4.3 name is exactly `incident-gpt`, Step 4.4 succeeded; wait and retry |
| GitHub: "Login failed" / `AADSTS70021` | The login's trust rule doesn't match | Check the `subject` in Step 6.2: spelling, owner, repo and `environment:production` |
| Drift workflow: 403 on upload | Pipeline has Reader only | Use Contributor on the container (Step 6.3) |
| Drift workflow: `TypeError: can't compare offset-naive and offset-aware` | A stored event has no or a bad timestamp (finding B1) | Delete the odd blob under `events/`, or fix `scripts/build_production_snapshot.py` |

---

## Part 9: What was and was not verified

**Verified by running it (Python 3.12, Linux):** installing both requirement files (all versions resolved); `pytest` (72 passed, 1 skipped); `validate_project.py`; training and local model registration; the API with `/health`, `/metrics`, `/docs`, `/predict`, `/analyze`; the local prompt-evaluation gate; the drift check on normal and deliberately drifted data; dependency and static security scans.

**Not verified (no Azure subscription, Azure CLI, Bicep compiler or GitHub repository available):** compiling `main.bicep`; every Azure and GitHub step in Parts 3 to 7; Azure role names (for example *Azure AI User*); whether the committed `infra/bicep/main.json` matches `main.bicep`; whether the preview Azure API versions in the Bicep file are available in your region; the exact Azure CLI output wording.

**Limits of the project itself:**
- Data is synthetic, so the 80% accuracy means little outside this demo, and the committed "production baseline" (exactly 0.80) was *reproduced locally*, not measured on a deployed model.
- Locally, the AI explanation is a fixed placeholder, and V1/V2 prompt scores are identical by construction.
- The security items in `SECURITY_REVIEW.md` are **not fixed** by this guide. Part 5 covers only the simplest protection.

---

## Glossary

| Word | Plain meaning |
|---|---|
| **Terminal / PowerShell** | A window where you type commands |
| **Virtual environment (`.venv`)** | A private box of software for one project |
| **API** | A web address that programs (or you, via `/docs`) can send data to and get answers back |
| **Model** | The trained program that guesses severity |
| **Training** | Teaching the model from example incidents |
| **Drift** | New data looks different from what the model learned from |
| **PSI** | A score for how much data has changed. 0.10 is a warning and 0.25 is "drift" |
| **Quality gate** | A pass/fail check a new model or prompt must clear before it can be used |
| **Azure** | Microsoft's cloud |
| **Resource group** | A folder in Azure holding related services |
| **Azure ML** | Azure's machine-learning service (trains and serves the model) |
| **Foundry** | Azure's AI service (hosts the chat model and the "agent") |
| **Endpoint** | A live address where the model answers questions |
| **Bicep** | A blueprint file that builds Azure services automatically |
| **Managed identity** | An Azure service's own passwordless ID |
| **OIDC** | A way for GitHub to prove who it is to Azure without a stored password |
| **Blue/green** | Two copies of the model, one live and one being tested, so you can switch safely |
| **Rollback** | Switching back to the previous version |
| **Workflow** | A GitHub "Run workflow" button that performs a list of steps |
