# ChatGPT App Publishing Notes

This project now includes a tool-only ChatGPT App implementation at:

`apps/chatgpt-academic-writing-toolkit/`

## Local Checks

Run from the repository root:

```bash
make chatgpt-app-check
make plugin-check
make test
```

The app-specific check runs the Node test suite for the MCP server and tool wrappers.

## Review Artifacts

- MCP server path: `apps/chatgpt-academic-writing-toolkit/src/server.js`
- Submission import file: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`
- Privacy URL source: `docs/privacy.md`
- Terms URL source: `docs/terms.md`
- App package version: `0.3.0`, aligned with `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`

## Current v0.3.0 Submission Endpoint

For the zero-cost v0.3.0 update of the already-published ChatGPT App, keep the existing Hugging Face Space MCP base URL:

```text
https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
```

Dashboard fields:

- App name: `Academic Writing Toolkit`
- Category: `EDUCATION`
- MCP Server URL: `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp`
- Privacy Policy URL: `https://github.com/yha9806/academic-writing-toolkit/blob/master/docs/privacy.md`
- Terms of Service URL: `https://github.com/yha9806/academic-writing-toolkit/blob/master/docs/terms.md`
- Submission import file: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`

Smoke-test before submitting:

```sh
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/health
curl -i https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
```

`/health` should return version `0.3.0` and `status: ok`. `GET /mcp` should return `405`; MCP traffic uses `POST /mcp`.

OpenAI currently requires an updated app draft to keep the same MCP base URL as the published version. Use the Render URL only for backup smoke testing or for a separate future app listing.

For the v0.3.0 draft, OpenAI Platform accepted the Hugging Face Space URL, confirmed domain verification, scanned 5 tools, and applied 5 imported tool justifications.

## Deployment Requirement

OpenAI Apps submission requires a public HTTPS MCP server URL. Localhost and temporary testing endpoints are not valid for review.

Deploy the app so this endpoint is reachable:

```text
https://YOUR_DOMAIN/mcp
```

Use these environment variables on the host:

```sh
HOST=0.0.0.0
PORT=3000
OPENAI_APPS_CHALLENGE=<challenge value from OpenAI Platform, when requested>
```

Before submission, verify the hosted deployment from outside local or private networks:

```sh
curl -fsS https://YOUR_DOMAIN/health
curl -i https://YOUR_DOMAIN/mcp
```

`/health` should return the app name, version, and `status: ok`. `GET /mcp` should return `405`; MCP traffic uses `POST /mcp`.

## Docker Deployment

Build from the repository root:

```sh
docker build -f apps/chatgpt-academic-writing-toolkit/Dockerfile -t academic-writing-toolkit-chatgpt-app .
docker run --rm -p 3000:3000 academic-writing-toolkit-chatgpt-app
```

For hosted deployment, configure the platform to route HTTPS traffic to the container and submit the public `https://YOUR_DOMAIN/mcp` URL.

## Cloud Run Deployment

Use Cloud Run when the MCP server should live behind an existing Firebase Hosting domain path. This keeps the main static site in place while routing only MCP-related paths to the ChatGPT App server.

Cloud Run files live in:

```text
deploy/cloud-run/
```

Deploy the app as a Cloud Run service named `academic-writing-toolkit-chatgpt-mcp` in the same region used by the Firebase Hosting rewrite. Prefer the manual GitHub Actions workflow in `.github/workflows/deploy-cloud-run-mcp.yml`, backed by a dedicated least-privilege Google Cloud deploy identity.

After the service URL passes direct smoke tests, add Firebase Hosting rewrites for these exact paths before the single-page-app fallback:

- `/mcp`
- `/health`
- `/.well-known/openai-apps-challenge`

After the hosting rewrite is deployed, submit:

```text
https://YOUR_DOMAIN/mcp
```

as the MCP Server URL in OpenAI Platform Apps Manage.

See `deploy/cloud-run/README.md` for build, deploy, verification, and rewrite examples.

## Hugging Face Space Deployment

The already-published ChatGPT App is bound to the Hugging Face Space domain:

```text
https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space
```

Use the Hugging Face Space path when updating the published app because OpenAI Platform rejects changing the MCP base URL inside the existing app version lineage.

The Space is a Docker Space on the free `cpu-basic` runtime. The Space root `Dockerfile` uses `PORT=7860`; keep that root Dockerfile in the Space even though the repository app Dockerfile uses `PORT=3000` for generic Docker hosts.

Update the Space from the repository root with a bounded upload package that includes:

- root Space `Dockerfile`
- root Space `README.md`
- `apps/chatgpt-academic-writing-toolkit/`
- runtime scripts under `scripts/`

After upload, wait until the Space runtime SHA matches the latest Space repo SHA, then verify:

```sh
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/health
curl -i https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/.well-known/openai-apps-challenge
```

## Render Deployment

Render is a zero-cost backup hosted path for smoke testing or for a separate future app listing. It is not the MCP URL for updates to the already-published OpenAI app, because that app is currently bound to the Hugging Face Space base URL.

Cloud Run remains useful only if the MCP server must later live behind an existing Firebase Hosting domain path.

Render is configured by `render.yaml` at the repository root.

The Blueprint defines one Docker web service:

- service name: `academic-writing-toolkit-chatgpt-app`
- Dockerfile: `apps/chatgpt-academic-writing-toolkit/Dockerfile`
- build context: repository root
- plan: `free`
- region: `oregon`
- health check: `/health`
- deploy trigger: `checksPass`

Why Render for the first public MCP endpoint:

- Docker web services fit the existing Express MCP server without changing the app.
- Render provides a public `onrender.com` HTTPS URL by default.
- `checksPass` avoids deploying a commit before GitHub CI succeeds.
- The `free` plan keeps the first deployment cost at zero while we prepare the app.
- A dedicated custom subdomain, such as `awt.example.com`, keeps Academic Writing Toolkit separate from any existing app and main site.

The free plan may sleep when idle. If you use Render for OpenAI review and it fails because the MCP endpoint is slow to wake up or unavailable, temporarily upgrade the Render service to `starter` for the review window, then downgrade after approval if traffic stays low.

Setup:

1. In Render, create a Blueprint from `https://github.com/yha9806/academic-writing-toolkit`.
2. Confirm `render.yaml` is detected at the repository root.
3. Create the service from the Blueprint.
4. Wait for Render to deploy the `master` branch after checks pass.
5. Copy the service URL, for example `https://academic-writing-toolkit-chatgpt-app.onrender.com`.
6. Add a dedicated custom domain, such as `awt.example.com`, as the Render custom domain for this service.
7. In the DNS provider for that domain, create the CNAME record Render requests.
8. Verify `https://YOUR_AWT_DOMAIN/health` returns `status: ok`.
9. Use `https://YOUR_AWT_DOMAIN/mcp` as the MCP Server URL in OpenAI Platform Apps Manage.

Keep the main site on its existing app. Do not route the main site's `/mcp` path to Academic Writing Toolkit; that would mix two products on the same review surface.

If OpenAI Platform asks for a domain challenge, set this environment variable on the Render service and redeploy:

```sh
OPENAI_APPS_CHALLENGE=<challenge value from OpenAI Platform>
```

Then verify:

```sh
curl -fsS https://YOUR_AWT_DOMAIN/.well-known/openai-apps-challenge
```

## Review Checklist

Before pressing Submit for review:

- Complete OpenAI organization verification for the publisher name.
- Confirm the submitting account has `api.apps.write`; use `api.apps.read` to view drafts and review status.
- Use a public HTTPS MCP URL that OpenAI can reach during automated checks and manual review.
- For updates to the already-published app, use the Hugging Face Space MCP URL because OpenAI Platform requires the MCP base URL to match the current published version.
- Pre-warm the Hugging Face Space with `/health` immediately before saving or submitting the OpenAI dashboard draft.
- Keep the Render `onrender.com` URL as a backup smoke-test deployment only. Move to a custom domain or Firebase Hosting plus Cloud Run only if a future app version or separate listing needs that base URL.
- Import `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json` into the dashboard form and re-check every generated test case.
- Run the positive and negative test prompts in ChatGPT Developer Mode on web and mobile; expected outputs should be concise and match the stated tool behavior.
- Confirm every tool descriptor has explicit `readOnlyHint`, `openWorldHint`, `destructiveHint`, and `outputSchema`.
- Audit realistic tool responses for unnecessary personal data, debug fields, request IDs, logs, or secrets before submission.
- Confirm `docs/privacy.md` and `docs/terms.md` match the deployed app behaviour.

## Official Review Flow

As of 2026-06-15, use OpenAI Platform Apps Manage after deployment:

https://platform.openai.com/apps-manage

OpenAI's Apps SDK submission docs state that the dashboard app review flow is the current path to public distribution, and that publishing an approved app creates the Codex distribution plugin. Self-serve standalone Codex plugin publishing is documented as coming soon.

Relevant docs:

- https://developers.openai.com/apps-sdk/deploy/submission
- https://developers.openai.com/apps-sdk/app-submission-guidelines
- https://developers.openai.com/apps-sdk/build/mcp-server
