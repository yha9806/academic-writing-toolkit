# OpenAI Plugin Submission Packet

This file records the submission details for the Academic Writing Toolkit skills companion
and its separately deployed ChatGPT App MCP surface.

## Official Status

OpenAI now uses one Plugins Directory for ChatGPT and Codex. The portal supports packages
with skills, MCP apps, or both. A package is not public until it has passed OpenAI review
and the developer publishes the approved version.

Official docs:

- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/deploy/submission
- https://platform.openai.com/plugins

The repository plugin remains skills-only. A local combined plugin requires a real
`plugin_asdk_app...` technical ID from an MCP connection registered in ChatGPT
Developer Mode; do not invent that ID. The Plugins portal's **With MCP** flow instead
accepts the production MCP URL directly.

## Package Target

- Plugin name: `academic-writing-toolkit`
- Display name: `Academic Writing Toolkit`
- Repository: `https://github.com/yha9806/academic-writing-toolkit`
- Package version: `0.5.0`
- Tagged release ref for external review: `v0.5.0`
- Current default branch ref used for local marketplace tracking: `main`
- Plugin path: `plugins/academic-writing-toolkit`
- Manifest: `plugins/academic-writing-toolkit/.codex-plugin/plugin.json`
- Marketplace metadata for repo/team testing: `.agents/plugins/marketplace.json`
- ChatGPT App submission checklist: `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json`
- Current ChatGPT App MCP URL for dashboard review: `https://harryhurry-academic-writing-toolkit-chatgpt-app.hf.space/mcp`

## Install Command For Review

Use `main` for current default-branch testing:

```bash
codex marketplace add yha9806/academic-writing-toolkit --ref main --sparse .agents/plugins --sparse plugins/academic-writing-toolkit
```

Use the immutable release tag after `v0.5.0` has been created:

```bash
codex marketplace add yha9806/academic-writing-toolkit --ref v0.5.0 --sparse .agents/plugins --sparse plugins/academic-writing-toolkit
```

The local CLI currently exposes `codex marketplace add`. Some newer OpenAI docs show `codex plugin marketplace add`; use the command supported by the installed Codex CLI version.

## Official Manifest Mapping

The manifest follows the OpenAI Codex plugin docs:

- Required entry point: `.codex-plugin/plugin.json`
- Package metadata: `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`
- Bundled components: `skills: "./skills/"`
- Install-surface metadata: `interface.displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, `websiteURL`, `supportURL`, `privacyPolicyURL`, `termsOfServiceURL`, `defaultPrompt`, `brandColor`, `composerIcon`, `logo`
- Asset paths: all visual assets live under `./assets/`
- No screenshots: the skills-only companion has no custom UI
- No absent component references: no `apps`, `mcpServers`, or `hooks` fields are declared unless those files are actually bundled

## Included Skills

- `read`
- `note`
- `verify`
- `map`
- `evidence-review`
- `argument-governance`
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
- `peer-review`
- `self-review`
- `progress`
- `export`

## Review Notes

- The skills companion bundles 20 local skills and their helper scripts.
- It does not install or launch the local Workbench wheel.
- The ChatGPT App exposes five deterministic pasted-text tools. It does not gain local
  file discovery or Workbench agent execution merely because versions align.
- Use `apps/chatgpt-academic-writing-toolkit/chatgpt-app-submission.json` as the
  reviewed source when entering exactly five positive and three negative tests and the
  annotation justifications in OpenAI Platform.
- Submit or update the MCP URL only after `/health` and MCP `serverInfo` both
  report `0.5.0`, all five tools scan correctly, and the production dependency
  audit is clean.
- The standalone plugin manifest does not declare `.app.json`. A local combined plugin
  would need a Developer Mode connection ID; the portal **With MCP** flow uses the URL.

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
- plugin version is SemVer and aligns with the App package
- helper scripts expose usable `--help`
- icon asset paths and headers validate
- ChatGPT App tool descriptors and wrappers pass their Node test suite
- production dependency audit reports zero vulnerabilities
- regression tests pass

## Community Submission Note

The plugin was also submitted to `codex-marketplace.com` as a community listing. That site states it is not affiliated with OpenAI. Treat that as a community distribution channel only, not as an official OpenAI Plugin Directory submission.
