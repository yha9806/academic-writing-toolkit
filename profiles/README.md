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

Validated baseline: `@deepseek-ai/dsh@0.1.0-rc.6` — see `COMPAT.json` at
the repo root for the dated, machine-readable claim.
