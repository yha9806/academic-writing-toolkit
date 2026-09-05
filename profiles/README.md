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
DSH_HOME=~/.dsh npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-headless --dump-config | grep awt-guards
```

Run inside a thesis workspace created by `awt init` (profile boot is a
truth test — the guards refuse to mount against a non-workspace directory):

```bash
cd <your-thesis-workspace>
export DEEPSEEK_API_KEY=...   # or ANTHROPIC_API_KEY for the anthropic route
npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-headless "task"
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
cd <your-thesis-workspace-or-anywhere>
export DEEPSEEK_API_KEY=...
npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-web --host 127.0.0.1 --port 3180
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
