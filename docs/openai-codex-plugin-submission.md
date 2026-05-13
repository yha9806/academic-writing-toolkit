# OpenAI Codex Plugin Submission Packet

This file records the official-format submission details for the Academic Writing Toolkit Codex plugin.

## Official Status

As of 2026-05-13, OpenAI's Codex plugin build documentation says official public plugin publishing and self-serve plugin management are coming soon.

Official docs:

- https://developers.openai.com/codex/plugins
- https://developers.openai.com/codex/plugins/build

This package is prepared to match the official Codex plugin package format. It has not been submitted to an official OpenAI public Plugin Directory because the official self-serve submission surface is not yet available in the documented developer flow.

## Package Target

- Plugin name: `academic-writing-toolkit`
- Display name: `Academic Writing Toolkit`
- Repository: `https://github.com/yha9806/academic-writing-toolkit`
- Release ref: `v0.1.0`
- Current default branch ref used for local marketplace tracking: `master`
- Plugin path: `plugins/academic-writing-toolkit`
- Manifest: `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`
- Marketplace metadata for repo/team testing: `.agents/plugins/marketplace.json`

## Install Command For Review

```bash
codex marketplace add yha9806/academic-writing-toolkit --ref v0.1.0 --sparse .agents/plugins --sparse plugins/academic-writing-toolkit
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
- `integrate`
- `audit`
- `style`
- `logic-review`
- `verify-refs`
- `progress`
- `export`

## Review Notes

- The plugin is a Codex plugin package, not a ChatGPT Apps SDK app.
- `chatgpt-app-submission.json` is not generated because this repo does not expose a ChatGPT Apps MCP server or Apps SDK widget surface.
- The package uses bundled local skills and helper scripts only.
- The package does not declare an external app connector or MCP server.

## Verification

Run from the repository root before any official submission:

```bash
make plugin-sync
make plugin-check
make test
```

Expected result:

- plugin skills are in sync with `.claude/skills`
- plugin manifest and marketplace metadata validate
- helper scripts expose usable `--help`
- PNG asset paths and headers validate
- regression tests pass

## Community Submission Note

The plugin was also submitted to `codex-marketplace.com` as a community listing. That site states it is not affiliated with OpenAI. Treat that as a community distribution channel only, not as an official OpenAI Plugin Directory submission.
