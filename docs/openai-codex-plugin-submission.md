# OpenAI Codex Plugin Submission Packet

This file records the official-format submission details for the Academic Writing Toolkit Codex plugin.

## Official Status

As of 2026-07-08, OpenAI's Codex plugin build documentation describes the plugin package and marketplace model. OpenAI's Apps submission documentation says the current public distribution path is to submit a ChatGPT App through the dashboard; publishing an approved app creates the Codex distribution plugin, while self-serve plugin publishing is still documented as coming soon.

Official docs:

- https://developers.openai.com/codex/plugins
- https://developers.openai.com/codex/plugins/build
- https://developers.openai.com/apps-sdk/deploy/submission

This package is prepared to match the official Codex plugin package format. It has not been submitted to an official OpenAI public Plugin Directory because the official self-serve submission surface is not yet available in the documented developer flow.

## Package Target

- Plugin name: `academic-writing-toolkit`
- Display name: `Academic Writing Toolkit`
- Repository: `https://github.com/yha9806/academic-writing-toolkit`
- Package version: `0.3.2`
- Tagged release ref for external review: `v0.3.2`
- Current default branch ref used for local marketplace tracking: `master`
- Plugin path: `plugins/academic-writing-toolkit`
- Manifest: `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`
- Marketplace metadata for repo/team testing: `.agents/plugins/marketplace.json`
- ChatGPT App submission import: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`
- Current ChatGPT App MCP URL for dashboard review: `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp`

## Install Command For Review

Use `master` for current default-branch testing:

```bash
codex marketplace add yha9806/academic-writing-toolkit --ref master --sparse .agents/plugins --sparse plugins/academic-writing-toolkit
```

Use an immutable release tag after the `v0.3.2` tag has been created:

```bash
codex marketplace add yha9806/academic-writing-toolkit --ref v0.3.2 --sparse .agents/plugins --sparse plugins/academic-writing-toolkit
```

The local CLI currently exposes `codex marketplace add`. Some newer OpenAI docs show `codex plugin marketplace add`; use the command supported by the installed Codex CLI version.

## Official Manifest Mapping

The manifest follows the OpenAI Codex plugin docs:

- Required entry point: `.codex-plugin/plugin.json`
- Package metadata: `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`
- Bundled components: `skills: "./skills/"`
- Install-surface metadata: `interface.displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, `websiteURL`, `privacyPolicyURL`, `termsOfServiceURL`, `defaultPrompt`, `brandColor`, `composerIcon`, `logo`, `screenshots`
- Asset paths: all visual assets live under `./assets/`
- No absent component references: no `apps`, `mcpServers`, or `hooks` fields are declared unless those files are actually bundled

## Included Skills

- `read`
- `note`
- `verify`
- `map`
- `evidence-review`
- `integrate`
- `thesis-control`
- `audit`
- `release-governance`
- `manuscript-reframe`
- `revision-escalation`
- `style`
- `logic-review`
- `verify-refs`
- `human-eval-handoff-repair`
- `progress`
- `export`

## Review Notes

- The standalone plugin package is a Codex plugin package with bundled local skills and helper scripts.
- The repository also exposes a separate tool-only ChatGPT App MCP server under `apps/chatgpt-academic-writing-toolkit/`.
- `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json` is generated for the OpenAI Platform Apps dashboard review flow.
- For the zero-cost v0.3.2 review path, submit `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp` as the MCP Server URL because the published app version already uses that MCP base URL.
- On 2026-07-08, the OpenAI dashboard draft was ready on content, MCP URL, tool annotations, and test cases, but `Submit for Review` was blocked until the publisher organization completes OpenAI Business verification.
- The package uses bundled local skills and helper scripts only.
- The standalone plugin manifest does not currently declare `.app.json` or `.mcp.json`; public Codex distribution should follow the documented Apps approval and publication path until self-serve plugin publishing is available.

## Verification

Run from the repository root before any official submission:

```bash
make plugin-sync
make plugin-check
make chatgpt-app-check
make test
```

Expected result:

- plugin skills are in sync with `.claude/skills`
- plugin manifest and marketplace metadata validate
- helper scripts expose usable `--help`
- PNG asset paths and headers validate
- ChatGPT App tool descriptors and wrappers pass their Node test suite
- regression tests pass

## Community Submission Note

The plugin was also submitted to `codex-marketplace.com` as a community listing. That site states it is not affiliated with OpenAI. Treat that as a community distribution channel only, not as an official OpenAI Plugin Directory submission.
