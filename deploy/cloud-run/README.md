# Cloud Run MCP Deploy

This directory documents the Cloud Run deployment path for the Academic Writing
Toolkit ChatGPT App MCP server.

Use this path when the MCP server must live behind an existing Firebase Hosting
domain path, such as `/mcp`, `/health`, and
`/.well-known/openai-apps-challenge`. Firebase Hosting can rewrite these paths
to a Cloud Run service in the same Google Cloud project while leaving the rest
of the static site untouched.

The container still uses the app Dockerfile:

```text
apps/chatgpt-academic-writing-toolkit/Dockerfile
```

## GitHub Actions Deploy

The preferred deployment path is the manual GitHub Actions workflow:

```text
.github/workflows/deploy-cloud-run-mcp.yml
```

Set these repository variables before running it:

| Variable | Purpose |
| --- | --- |
| `GCP_PROJECT_ID` | Google Cloud project that owns the Cloud Run service and hosting rewrite |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GitHub Actions Workload Identity provider resource name |
| `GCP_SERVICE_ACCOUNT` | Least-privilege deploy service account email |

Pre-create the Artifact Registry Docker repository used by the workflow input
`artifact_repository`; the default name is `academic-writing-toolkit` in
`asia-east1`.

```sh
gcloud artifacts repositories create academic-writing-toolkit \
  --repository-format docker \
  --location asia-east1 \
  --project "$GCP_PROJECT_ID"
```

The deploy service account needs permission to authenticate from GitHub Actions,
push Docker images to the Artifact Registry repository, deploy the Cloud Run
service, and act as the Cloud Run runtime service account. In Google Cloud IAM
terms, grant the narrowest equivalent of:

- Workload Identity User on the GitHub identity pool binding.
- Artifact Registry Writer on the Docker repository.
- Cloud Run Admin on the target service or project.
- Service Account User on the Cloud Run runtime service account.

Run the workflow manually from GitHub Actions. Keep the default service name and
region when pairing this service with the Firebase Hosting rewrite documented
below.

## Local Build

Run from the repository root:

```sh
PROJECT_ID=<gcp-project>
REGION=asia-east1
SERVICE_NAME=academic-writing-toolkit-chatgpt-mcp
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:$(git rev-parse --short HEAD)"

gcloud builds submit \
  --config deploy/cloud-run/cloudbuild.yaml \
  --substitutions _IMAGE="$IMAGE" \
  .
```

## Local Deploy

Cloud Run provides `PORT`; set only the host and production mode explicitly.
Keep `REGION` aligned with the Firebase Hosting rewrite; this guide defaults to
`asia-east1` for the existing hosting integration.

```sh
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "NODE_ENV=production,HOST=0.0.0.0"
```

If OpenAI Platform asks for domain verification, set the challenge value and
redeploy:

```sh
gcloud run services update "$SERVICE_NAME" \
  --region "$REGION" \
  --set-env-vars "NODE_ENV=production,HOST=0.0.0.0,OPENAI_APPS_CHALLENGE=<challenge value>"
```

## Verify Direct Service URL

Use the direct Cloud Run service URL before adding hosting rewrites:

```sh
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')"

curl -fsS "${SERVICE_URL}/health"
curl -i "${SERVICE_URL}/mcp"
curl -fsS "${SERVICE_URL}/.well-known/openai-apps-challenge"
```

`/health` should return `status: ok`. `GET /mcp` should return `405`; MCP
traffic uses `POST /mcp`.

## Firebase Hosting Rewrites

Add the exact rewrites before the single-page-app fallback in the hosting
project:

```json
{
  "source": "/mcp",
  "run": {
    "serviceId": "academic-writing-toolkit-chatgpt-mcp",
    "region": "asia-east1"
  }
}
```

Repeat the rewrite for `/health` and
`/.well-known/openai-apps-challenge`. Keep the catch-all rewrite to
`/index.html` last.

After deploying the hosting config, the OpenAI MCP server URL is:

```text
https://YOUR_DOMAIN/mcp
```
