# Codex Plugin Publishing Checklist

Use this checklist before submitting or sharing the Academic Writing Toolkit Codex plugin. This checklist targets the official OpenAI Codex plugin package format described in the OpenAI Developers Codex plugin docs.

## Official Directory Status

OpenAI's current Codex plugin build documentation says official public plugin publishing and self-serve plugin management are coming soon. Until that official submission surface exists, treat this repository as an official-format, submission-ready plugin package rather than a completed official directory listing.

Reference: https://developers.openai.com/codex/plugins/build

## Required Local Checks

Run these from the repository root:

```bash
make plugin-sync
make plugin-check
make test
```

`make plugin-sync` regenerates `plugins/academic-writing-toolkit/skills/` from the canonical `.claude/skills/` directory. `make plugin-check` validates the plugin manifest, marketplace entry, bundled helper scripts, asset paths, PNG headers, and sync state.

## Official Manifest Review

Check `plugins/academic-writing-toolkit/.codex-plugin/plugin.json` for:

- `name`: `academic-writing-toolkit`
- `version`: current release version
- `repository`, `homepage`, and `websiteURL`: public repository URLs
- `privacyPolicyURL`: `docs/privacy.md` on the public default branch
- `termsOfServiceURL`: `docs/terms.md` on the public default branch
- `composerIcon`, `logo`, and `screenshots`: PNG paths under `./assets/`
- `defaultPrompt`: no more than three short starter prompts

OpenAI's published plugin manifest example uses these same field groups: package metadata, bundled component paths, and the `interface` install-surface metadata.

## Marketplace Review For Testing

Check `.agents/plugins/marketplace.json` for:

- one `academic-writing-toolkit` entry
- `source.path`: `./plugins/academic-writing-toolkit`
- `policy.installation`: `AVAILABLE`
- `policy.authentication`: `ON_INSTALL`
- `category`: `Productivity`

This repo marketplace is for local, repo, team, or personal distribution. It is not an official OpenAI Plugin Directory submission by itself.

## Asset Review

Current local assets live in `plugins/academic-writing-toolkit/assets/`:

- `icon.png`
- `logo.png`
- `screenshot-workflow.png`
- `screenshot-progress.png`

These are functional generated assets. Replace them with final branded assets before a polished public launch if desired, then rerun `make plugin-check`.

## Submission Packet

Before an official OpenAI public plugin submission surface is available, keep the review packet in `docs/openai-codex-plugin-submission.md` current. It records the repository URL, plugin path, release ref, install command, manifest mapping, and local verification evidence.

## Release Notes

Before publishing a new version:

- update the manifest `version`
- run `make plugin-sync`
- run `make plugin-check`
- run `make test`
- commit the generated plugin package and supporting docs together
