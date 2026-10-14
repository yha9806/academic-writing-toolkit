# Selected Codex plugin export

Status: Proposed for maintainer review; implementation and local E0 checks are on a contribution branch.

## Problem

The global installer owns helper relocation and resource preparation, but
consumers who distribute a selected group as a Codex plugin must wrap its
internal functions and preserve invocation metadata themselves.

## Goals

- Expose a supported CLI for exporting selected skills as a local Codex plugin.
- Reuse the same preparation and helper verification as the global installer.
- Preserve explicitly supplied invocation/UI metadata and tool restrictions.
- Publish a complete verified output atomically and retain existing output.

## Non-goals

Change the default nine-skill global installation, install or enable plugins,
publish a release, or claim scholarly quality beyond the existing checks.

## Decision

Add `scripts/export-codex-plugin.py`. `--skill` is repeatable and defaults to
the current catalogue. `--preserve-policy-from` reads selected installed skill
metadata; it does not copy local instruction bodies. A private runtime can be
prepared with the existing pinned requirements using `--install-deps`.

The output is local to the machine's selected Python runtime and, for the
readers workflow, its source checkout. It is not a portable release archive.
The exporter writes a Codex manifest and a source/selection receipt. An
existing byte-identical output is a no-op; a different output is refused.

## Acceptance criteria

- The real CLI exports an eight-skill selection without adding `readers`.
- Preserved manual invocation and tool restrictions match supplied metadata.
- Helper references resolve and real offline/DOCX smoke checks pass.
- Invalid selections and nonempty foreign output leave existing files intact.
- A fresh private runtime can export the package without prior toolkit setup.
- Existing global-installer tests continue to pass.

## Evidence boundaries

Local deterministic checks are E0-style evidence, not hosted CI or an E1/E2
writing evaluation. The PR records platform, test coverage and skipped paths.
