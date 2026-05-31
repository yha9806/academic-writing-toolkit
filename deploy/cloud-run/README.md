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

## Build

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

## Deploy

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
