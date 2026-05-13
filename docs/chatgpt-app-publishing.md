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
```

## Docker Deployment

Build from the repository root:

```sh
docker build -f apps/chatgpt-academic-writing-toolkit/Dockerfile -t academic-writing-toolkit-chatgpt-app .
docker run --rm -p 3000:3000 academic-writing-toolkit-chatgpt-app
```

For hosted deployment, configure the platform to route HTTPS traffic to container port `3000` and submit the public `https://YOUR_DOMAIN/mcp` URL.

## Official Review Flow

Use OpenAI Platform Apps Manage after deployment:

https://platform.openai.com/apps-manage

OpenAI's Apps SDK submission docs state that the dashboard app review flow is the current path to public distribution, and that publishing an approved app creates the Codex distribution plugin. Self-serve standalone Codex plugin publishing is documented as coming soon.

Relevant docs:

- https://developers.openai.com/apps-sdk/deploy/submission
- https://developers.openai.com/apps-sdk/app-submission-guidelines
- https://developers.openai.com/apps-sdk/build/mcp-server
