# AWT profiles

Canonical dsh profile templates. A profile is a directory under
`$DSH_HOME/profiles/<name>` — `package.json` names the ordered bundle
layers, `cordis.patch.yml` is the AWT overlay on top of them.

## awt-headless

The author-facing profile: dsh-base + dsh-headless, the AWT guards mounted
with enforcement-on defaults, and dormant pi-ai provider routes (deepseek
for cost, anthropic for prose fidelity) activated per request through
`apiKeyEnv` credential references. **No profile file ever contains a
secret**; a configured reference that resolves to nothing fails typed
(`MISSING_CREDENTIAL`) instead of falling through to ambient keys.

Install into your real `$DSH_HOME` (default `~/.dsh`; refuses to overwrite
an existing profile):

```bash
node scaffold/awt.mjs install-profile
```

Verify the composition without booting or credentials:

```bash
node harness/node_modules/@deepseek-ai/dsh/lib/bin.js --profile awt-headless --dump-config | grep awt-guards
```

Run inside a thesis workspace created by `awt init` (profile boot is a
truth test — the guards refuse to mount against a non-workspace directory):

```bash
export DEEPSEEK_API_KEY=...   # or ANTHROPIC_API_KEY for the anthropic route
node scaffold/awt.mjs run <your-thesis-workspace> "task"
```

`awt run` resolves the pinned launcher from `harness/` in the toolkit
checkout, which `install-profile` populates with `npm ci` from a tracked
lockfile. It does not live in `$DSH_HOME`: dsh owns
`$DSH_HOME/profiles/node_modules` and heals it by symlinking in the
installation it was launched out of, so AWT owns that installation rather
than inheriting whatever a machine happens to have. No package is resolved
at launch time, and an off-pin harness is a typed refusal
(`AWT_LAUNCH_HARNESS_UNPINNED`).

Anything after `--` goes to the harness untouched, which is how a launcher
overlay reaches it:

```bash
node scaffold/awt.mjs run <workspace> "task" -- --patch model.yml
```

Remove by deleting `$DSH_HOME/profiles/awt-headless`; upgrade by
re-running `install-profile` after removing (never merges in place).

## awt-web

The same enforcement, behind dsh's own web UI: **identical patch rows**
(guards, `read_pdf`, apiKeyEnv routes) with `dsh-web-app` in place of the
headless bundle — the difference between the two surfaces is exactly one
bundle name, which is the point: the product is the composition, not the
shell. `awt install-profile` installs both profiles together.

```bash
export DEEPSEEK_API_KEY=...
node scaffold/awt.mjs web <your-thesis-workspace> [port]
```

Then open http://127.0.0.1:3180, add your workspace via the native folder
picker, and converse. Port 3180 avoids colliding with other local dsh
instances on the stock 3080. Composition verified live 2026-08-16: the web
session injects the workspace contract (AGENTS.md/CLAUDE.md) and the
skill catalog, and requests reach the configured provider route.

Skill discovery inside these profiles is the **workspace catalogue only**:
the provider's two user-level roots (`$DSH_HOME/skills`, `~/.agents/skills`)
are pointed at a directory that does not exist, so nothing outside the
workspace's `.agents/skills` is offered. `e2e/run-skill-scope-probe.mjs`
plants decoys in both roots and asserts they stay invisible.

Validated baseline: `@deepseek-ai/dsh@0.1.0-rc.6` — see `COMPAT.json` at
the repo root for the dated, machine-readable claim.
