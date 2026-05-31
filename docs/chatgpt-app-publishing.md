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
- App package version: `0.2.0`, aligned with `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`

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

For hosted deployment, configure the platform to route HTTPS traffic to container port `3000` and submit the public `https://YOUR_DOMAIN/mcp` URL.

## Review Checklist

Before pressing Submit for review:

- Complete OpenAI organization verification for the publisher name.
- Confirm the submitting account has `api.apps.write`; use `api.apps.read` to view drafts and review status.
- Use a public HTTPS MCP URL that OpenAI can reach during automated checks and manual review.
- Import `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json` into the dashboard form and re-check every generated test case.
- Run the positive and negative test prompts in ChatGPT Developer Mode on web and mobile; expected outputs should be concise and match the stated tool behavior.
- Confirm every tool descriptor has explicit `readOnlyHint`, `openWorldHint`, `destructiveHint`, and `outputSchema`.
- Audit realistic tool responses for unnecessary personal data, debug fields, request IDs, logs, or secrets before submission.
- Confirm `docs/privacy.md` and `docs/terms.md` match the deployed app behaviour.

## Official Review Flow

Use OpenAI Platform Apps Manage after deployment:

https://platform.openai.com/apps-manage

OpenAI's Apps SDK submission docs state that the dashboard app review flow is the current path to public distribution, and that publishing an approved app creates the Codex distribution plugin. Self-serve standalone Codex plugin publishing is documented as coming soon.

Relevant docs:

- https://developers.openai.com/apps-sdk/deploy/submission
- https://developers.openai.com/apps-sdk/app-submission-guidelines
- https://developers.openai.com/apps-sdk/build/mcp-server
