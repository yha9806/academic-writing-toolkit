# OpenAI Skills-Only Plugin Publishing Checklist

Use this checklist for Academic Writing Toolkit `v0.5.0`. OpenAI currently
supports skills-only plugin submission through
<https://platform.openai.com/plugins>.

Official references:

- <https://learn.chatgpt.com/docs/build-plugins>
- <https://learn.chatgpt.com/docs/submit-plugins>

The repository marketplace remains useful for local testing, but it is not an
official OpenAI listing.

## 1. Lock The Candidate

- [ ] Start from the latest `main`.
- [ ] Merge through a PR so the exact candidate receives Linux CI evidence.
- [ ] Confirm the worktree is clean and `.agents/skills/` has no accidental
      Windows symlink deletions.
- [ ] Use one new version identity: manifest, App package, docs, tag, ZIP names,
      and release packet all say `0.5.0`.
- [ ] Do not rewrite the historical `v0.4.0` readiness record.

## 2. Validate The Package

Run:

```bash
make plugin-sync
make plugin-check
make chatgpt-app-check
make test
python3 scripts/audit-public-content.py --base-dir . --json
```

`make plugin-check` must verify:

- valid manifest and marketplace JSON;
- exactly 21 canonical and packaged Skills;
- allowed Skill frontmatter keys;
- no missing helper or visual asset;
- one to three non-empty starter prompts, each at most 128 characters;
- manifest and submission-packet version agreement;
- exactly five positive and three negative Skills-only reviewer cases;
- required support, privacy, terms, availability, release-note, policy, and
  owner-gate fields;
- canonical/plugin sync.

Also run the OpenAI Skill Creator `quick_validate.py` against all 21 packaged
Skills with UTF-8 mode enabled. The repository validator supplements that
check; it does not replace OpenAI's review scanner.

## 3. Review The Listing

Check `plugins/academic-writing-toolkit/.codex-plugin/plugin.json` and
`submission/openai/skills-only-submission.json` together:

- [ ] Name and descriptions state that the product organises a research project
      rather than acting primarily as a rebuttal generator.
- [ ] Website: <https://github.com/yha9806/academic-writing-toolkit>
- [ ] Support: <https://github.com/yha9806/academic-writing-toolkit/issues>
- [ ] Privacy and terms resolve publicly.
- [ ] Category is `Productivity`.
- [ ] All three starter prompts match exactly.
- [ ] Release notes describe only behaviour present in the final ZIP.
- [ ] Region selection is confirmed by the owner.

Do not add an undocumented `interface.supportURL` field to the manifest.
Support is a portal/submission-packet field.

## 4. Forward-Test The 5+3 Cases

Use the exact prompts in
`submission/openai/skills-only-submission.json` against the final plugin ZIP.

- [ ] Five positive cases pass their stated evidence and author-control gates.
- [ ] `N01` does not trigger the plugin.
- [ ] `N02` does not fabricate evidence.
- [ ] `N03` does not bypass the contribution-focus author gate.
- [ ] Record date, tester, final ZIP SHA-256, result, and any deviation.

Static JSON validation proves the packet shape, not the model's semantic
behaviour. The forward-test record is required release evidence.

## 5. Review The Visual Assets

The two v0.5.0 listing screenshots must show the current flagship workflows:

1. canonical project intent and the
   `gap → data → result → claim → contribution → innovation evidence` spine,
   including licensed and unlicensed headline scope;
2. attempts one to three, stop before attempt four, diagnosis, author decision,
   and factual session summary.

Regenerate them from source:

```bash
python3 scripts/render-plugin-assets.py
make plugin-check
```

Inspect both 1600×1000 PNGs at full size and thumbnail size. Colour is never
the only status signal.

## 6. Build The Immutable Release

After all local checks and PR CI pass:

- [ ] Merge to `main`.
- [ ] Record the final commit SHA.
- [ ] Create annotated tag `v0.5.0`.
- [ ] Build the source ZIP from that tag.
- [ ] Build the plugin-only ZIP from
      `plugins/academic-writing-toolkit/` at that tag.
- [ ] Generate `SHA256SUMS`.
- [ ] Verify the plugin ZIP contains `.codex-plugin/plugin.json`, all 21 Skills,
      and all referenced PNG assets.
- [ ] Update `docs/product/v0.5.0-release-readiness.md` and `release/` with
      actual results rather than planned values.

From the final tag, the deterministic build command is:

```bash
python3 scripts/build-plugin-release.py \
  --ref v0.5.0 \
  --version 0.5.0 \
  --out-dir dist/v0.5.0
```

## 7. Complete Owner-Controlled Portal Gates

- [ ] The publisher has a verified individual or business identity.
- [ ] The submitting account has Apps Management Write access.
- [ ] Manifest developer, licence owner, and verified publisher identity are
      intentionally aligned.
- [ ] Upload the exact tested plugin ZIP.
- [ ] Confirm availability and policy declarations.
- [ ] Submit for review manually.
- [ ] After approval, publish manually.

Repository automation must leave these fields as owner actions until they have
actually been completed.

## Separate ChatGPT App

The MCP App under `apps/chatgpt-academic-writing-toolkit/` has a different
review path and different 5+3 test cases. Do not use its hosted URL, tool tests,
or historical Business-verification status as evidence for the skills-only
submission.
