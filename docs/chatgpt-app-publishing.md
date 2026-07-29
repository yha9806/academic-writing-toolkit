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
- Submission checklist file: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`
- Privacy URL source: `docs/privacy.md`
- Terms URL source: `docs/terms.md`
- App package version target: `0.5.0`, aligned with `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`

## v0.5.0 Submission And Deployment Endpoint

For the v0.5.0 update of the existing ChatGPT App submission, keep the existing
Hugging Face Space MCP base URL:

```text
https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
```

Dashboard fields:

- App name: `Academic Writing Toolkit`
- Category: `EDUCATION`
- MCP Server URL: `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp`
- Privacy Policy URL: `https://github.com/yha9806/academic-writing-toolkit/blob/main/docs/privacy.md`
- Terms of Service URL: `https://github.com/yha9806/academic-writing-toolkit/blob/main/docs/terms.md`
- Submission checklist file: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`

Smoke-test before submitting:

```sh
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/health
curl -i https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
```

After deployment, `/health` and MCP `serverInfo` must return version `0.5.0`.
`GET /mcp` should return `405`; MCP traffic uses `POST /mcp`.

The existing registered draft already uses the Hugging Face endpoint. Keep that
verified endpoint for this update unless the live portal explicitly permits and verifies
a replacement. The Render URL remains a backup smoke-test endpoint.

The endpoint previously passed domain verification and exposed five tools.
Re-scan the deployed stable endpoint after deployment; prior scan results do not
prove the new deployment.

Do not silently replace the endpoint bytes while an OpenAI review is active.
Either complete the stable deployment and re-scan before submitting, or keep the
reviewed deployment unchanged until the review decision and submit the stable
runtime through the next permitted review update.

At the GitHub v0.5.0 release gate, the endpoint under active OpenAI review still
reported `0.5.0-rc.4` from Space SHA
`876c6cf357de4dbdd2057066570b4f5a4366caa9`. The hosted package metadata was
subsequently promoted to `0.5.0` at Space SHA
`c88871ef8d1ce7629c10f038deab10c7421696f4`; the core server and tool source
bytes were unchanged. This deployment does not itself approve or publish the
ChatGPT App.

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

as the MCP Server URL in the OpenAI Plugins portal.

See `deploy/cloud-run/README.md` for build, deploy, verification, and rewrite examples.

## Hugging Face Space Deployment

The existing registered ChatGPT App draft uses the Hugging Face Space domain:

```text
https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space
```

Use the Hugging Face Space path for this draft update because it is the existing
domain-verified endpoint. Re-check the live portal before asserting any immutable
published-version URL rule.

The Space is a Docker Space on the free `cpu-basic` runtime. The Space root `Dockerfile` uses `PORT=7860`; keep that root Dockerfile in the Space even though the repository app Dockerfile uses `PORT=3000` for generic Docker hosts.

Update the Space through a Hugging Face pull request containing only runtime files whose
hashes differ from the current Space. Do not upload the GitHub repository root, use
`--delete`, or replace the Space's root `Dockerfile` and `README.md`.

After upload, wait until the Space runtime SHA matches the latest Space repo SHA, then verify:

```sh
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/health
curl -i https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp
curl -fsS https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/.well-known/openai-apps-challenge
```

Stable deployment gate:

- Space repo SHA and runtime SHA must match.
- `/health` must return version `0.5.0` and `status: ok`.
- `GET /mcp` must return `405 Method not allowed`.
- MCP initialize must report server version `0.5.0`.
- The scan must list five tools with the three required annotations and
  `outputSchema`.
- Five public-safe smoke calls must pass.
- `/.well-known/openai-apps-challenge` must return the configured challenge token.

Latest OpenAI dashboard check:

- Date: 2026-07-29
- App: `Academic Writing Toolkit`
- Portal status: `0.5.0` in review; not approved or published
- MCP Server URL: `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp`
- Authentication: `No Auth`
- Domain verification: verified
- Space repo/runtime SHA: `c88871ef8d1ce7629c10f038deab10c7421696f4`
- Live `/health` and MCP initialize version: `0.5.0`
- Live tool check: 5 tools with explicit `readOnlyHint`, `openWorldHint`,
  `destructiveHint`, and `outputSchema`; 5 public-safe calls passed
- Tests: 5 positive test cases and 3 negative test cases present
- Country availability: allow all countries
- Portal label submitted for review: `0.5.0`
- Reviewed metadata remains the portal's submission-time snapshot; the live
  `0.5.0` deployment is not evidence of approval
- Stable App status: deployed and under review; publication remains a separate
  post-approval action
- Known review risk: the submitted demonstration video covers ChatGPT Web only;
  the maintainer explicitly accepted the mobile-coverage risk before submission

## Render Deployment

Render is a zero-cost backup hosted path for smoke testing or for a separate future
listing. It is not the selected endpoint for this draft; the current domain-verified
draft uses the Hugging Face Space URL.

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
4. Wait for Render to deploy the `main` branch after checks pass.
5. Copy the service URL, for example `https://academic-writing-toolkit-chatgpt-app.onrender.com`.
6. Add a dedicated custom domain, such as `awt.example.com`, as the Render custom domain for this service.
7. In the DNS provider for that domain, create the CNAME record Render requests.
8. Verify `https://YOUR_AWT_DOMAIN/health` returns `status: ok`.
9. Use `https://YOUR_AWT_DOMAIN/mcp` as the MCP Server URL in the OpenAI Plugins portal.

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
- Confirm the submitting account has **Apps Management Write** permission.
- Use a public HTTPS MCP URL that OpenAI can reach during automated checks and manual review.
- For this existing registered draft, use the currently verified Hugging Face Space MCP
  URL unless the live portal explicitly accepts and verifies a replacement.
- Pre-warm the Hugging Face Space with `/health` immediately before saving or submitting the OpenAI dashboard draft.
- Keep the Render `onrender.com` URL as a backup smoke-test deployment only. Move to a custom domain or Firebase Hosting plus Cloud Run only if a future app version or separate listing needs that base URL.
- Copy the reviewed values from
  `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json` into the portal and
  re-check every test case. Do not assume a JSON-import control exists.
- Run the positive and negative test prompts in ChatGPT Developer Mode on web and mobile; expected outputs should be concise and match the stated tool behavior.
- Confirm every tool descriptor has explicit `readOnlyHint`, `openWorldHint`, `destructiveHint`, and `outputSchema`.
- Audit realistic tool responses for unnecessary personal data, debug fields, request IDs, logs, or secrets before submission.
- Confirm `docs/privacy.md` and `docs/terms.md` match the deployed app behaviour.

## Official Review Flow

Use the current OpenAI Plugins portal after deployment:

https://platform.openai.com/plugins

ChatGPT and Codex share one Plugins Directory. Submission, approval, and developer
publication are separate states.

Relevant docs:

- https://developers.openai.com/plugins/deploy/submission
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/apps-sdk/app-submission-guidelines
