# AWT guards — live dsh headless e2e (P1 closing gate)

Proves, against the **real published dsh launcher** (`@deepseek-ai/dsh@0.1.0-rc.6`,
pinned exactly — no mock of dsh anywhere), that the AWT guard plugin mounted on
the monotonic `ctx.tools.guard` seam denies each forbidden chapter operation
with its typed denial code, observable in the persisted session log, while a
conforming write passes. This closes the open gate in
`docs/specs/2026-08-16-p1-guards-headless.md` (Session-2 gates / Closing status)
and parent spec `2026-08-16-awt-dsh-app-v0.1-design.md` §7.

## Run it

```sh
cd e2e
npm install         # installs @deepseek-ai/dsh@0.1.0-rc.6 (see package-lock.json)
node run-e2e.mjs    # exit 0 only when every required assertion holds
```

The runner:

1. builds `guards/dist` via `npm run build` in `../guards` (plain `tsc`; the
   plugin artifact **is** the shipped kernel — `guards/src/decisions.ts`
   compiled, not a reimplementation);
2. per scenario, creates a fresh temp thesis workspace (chapters/ch1.md with a
   quotation span; one lint-conforming notes file for smith 2024 built from
   `literature/reading_notes/_template_NOTES.md`; an active edit contract in
   `contracts/` whose `## Attempts` has an unchecked box) and a fresh temp
   `$DSH_HOME` holding the `awt-headless` profile;
3. spawns `node node_modules/@deepseek-ai/dsh/lib/bin.js --profile awt-headless "<task>"`
   with cwd = the workspace;
4. asserts on the **persisted session store** under `$DSH_HOME/sessions/`.

## Scenarios and expected outcomes

| scenario | scripted tool call | expected |
| --- | --- | --- |
| contract-scope | `write chapters/ch5.md` citing Jones (2021) | `CONTRACT_SCOPE` (contract active, ch5 out of `May change:`) |
| notes-missing | `write chapters/ch3.md` citing Jones (2021) | `NOTES_MISSING` (in scope, no notes for jones 2021) |
| quote-span | `edit chapters/ch1.md` altering text inside the quotation span | `QUOTE_SPAN_MODIFIED` |
| allowed-write | `write chapters/ch3.md` citing Smith (2024) | ALLOWED — negative control; the file must exist on disk afterwards, tool/result `isError:false`, zero denial codes in the log |
| page-range (stretch) | `read_pdf` pages 1–16 against a stub `read_pdf` tool | `PAGE_RANGE_EXCEEDED` via kernel `decidePdfRead` |
| export-unresolved | `export_docx` while `chapters/ch2.md` cites Jones (2021) with no notes | `EXPORT_SOURCES_UNRESOLVED` via kernel `decideExport` (corpus-wide; the stub tool leaves a marker when allowed) |

Fixture note: the guard kernel evaluates `CONTRACT_SCOPE` before
`QUOTE_SPAN_MODIFIED` (`decide()` order), so the quote-span scenario's
contract scopes `May change: chapters/ch1.md, chapters/ch3.md` — otherwise the
contract denial would mask the quote denial that scenario isolates. All other
scenarios use the base fixture contract `May change: chapters/ch3.md`.

Denied scenarios additionally assert the workspace was NOT mutated
(spec invariant 6: a denied operation changes no authoritative state).

## How the tool call reaches the guard (no mocks)

`plugins/awt-scripted-llm.plugin.mjs` subclasses the installed
`LlmAdapter` and registers via the real `ctx.llm.registerAdapter(['scripted'], adapter)`.
Its `stream()` emits an assistant `tool-call` block (raw-JSON arguments,
`usage` before a `finish {kind:'tool-calls'}`) on the first conversation
request, and a plain `stop` text on the next, so the call travels the genuine
loop: `assistant/message → tool/call → tools/pre-execute waterfall → monotonic
guards → tool/result`. Auxiliary requests (`options.purpose`, e.g.
session-title) get a plain text response. The base bundle's
`agent-default-model` row is patched to `{provider: scripted, model: scripted-1}`
so the headless runner routes to this adapter — no credentials, no network.

Session-log proof of the pipeline (verbatim, one run):

```
{"type":"tool/call","seq":19,...,"callId":"awt-e2e-call-1","name":"write","arguments":"{\"file_path\":\"/tmp/awt-e2e-ws-05WB0V/chapters/ch5.md\",...}"}
{"type":"tool/result","seq":20,...,"content":[{"type":"text","text":"Error: CONTRACT_SCOPE: \"chapters/ch5.md\" is outside the active edit contract's \"May change\" scope."}],"isError":true}...}
```

## Plugin-loading mechanism discovered (rc.6)

A profile is `$DSH_HOME/profiles/<name>/` holding:

- `package.json` with `dsh.profile.bundles` (this e2e: `@deepseek-ai/dsh-base`,
  `@deepseek-ai/dsh-headless` — the same tuple as the shipped `headless`
  template, under the profile name `awt-headless`). `"type": "module"` matters:
  the loader imports the profile-local `.js` plugin files under this manifest.
- `cordis.patch.yml` — the user patch layer applied after every bundle layer.
  **Local plugins mount as `insert` rows whose `name` is a relative path**
  (`name: './awt-guards/dsh-plugin.js'`): the Cordis loader resolves relative
  specifiers against the config directory, which the dsh launcher anchors at
  the profile directory (it rewrites `<profile>/cordis.yml` on every boot).
  Bare package names resolve through the flat symlink farm
  `$DSH_HOME/profiles/node_modules` that `healProfilesModuleFallback` builds
  from the dsh installation's dependency closure — which is how the plugin
  files import `@deepseek-ai/dsh-llm` / `@deepseek-ai/dsh-tools` without any
  profile-local install.

The runner materializes the profile from `profile/` in this directory plus the
plugin files and a copy of `guards/dist` (as `<profile>/awt-guards/`). The
guard row mounts the shipped adapter directly:

```yaml
- insert:
    - id: awt-guards
      name: './awt-guards/dsh-plugin.js'
      config:
        projectRoot: !!js process.env.AWT_E2E_WORKSPACE
```

`guards/dist/dsh-plugin.js` exports `name`, `inject = ['tools']`, and
`apply(ctx, config)` — the Cordis function-plugin shape; `inject` makes the
mount wait for the `tools` service.

## Session-log location and format

`$DSH_HOME/sessions/<encoded-cwd>/session-<uuid>/session.jsonl[.zstd]`,
written by the base bundle's `session-persistence-jsonl` row. The default is
**multi-frame zstd** (`session.jsonl.zstd`; Node's one-shot
`zstdDecompressSync` reads only the first frame). The profile patch restates
the row with `compression: none` so the gate can grep plaintext:

```yaml
- id: session-persistence-jsonl
  config:
    root: !!js dshHomePath('sessions')
    compression: none
```

A guard denial materializes as a durable `tool/result` event whose content is
`Error: <reason>` with `isError: true` (`dsh-tools` `prepareExecution`:
`text: `Error: ${denialReason}``), so the typed code is greppable verbatim.

## rc.6-vs-master deltas and discoveries accommodated

1. **`ToolExecution.arguments`, not `args`.** The installed
   `@deepseek-ai/dsh-tools@0.1.0-rc.6` declares
   `ToolGuard = (execution: Readonly<ToolExecution>) => string | undefined`
   with the parsed call in `execution.arguments`. The P1 session-1 adapter
   compiled against a structural `{ name, args }` guess and would have been a
   silent no-op (every guard read `{}` and returned `undefined`).
   `guards/src/dsh-plugin.ts` now reads `execution.args ?? execution.arguments`.
   This is exactly the class of drift the live gate exists to catch.
2. **Session store is multi-frame zstd by default** (see above); patched to
   plaintext for this profile.
3. **`fs-observation-policy` no-clobber:** a `write` to an *existing* file the
   session never read fails in the tool body (`createIfAbsent`). Denied
   scenarios never reach the body, but the negative control targets a
   *new* file (`chapters/ch3.md` absent from the fixture) so the allowed write
   genuinely succeeds.
4. **Approvals:** the base `workspace-write` sandbox + `ask` approval policy
   allowed in-workspace writes without an interaction surface — no
   `danger-full-access` override was needed; the headless run's cwd is the
   workspace.
5. **Auxiliary LLM traffic:** `session-title-first-prompt-llm` calls the
   default (scripted) route with `options.purpose = 'session-title'`; the
   adapter must answer it (plain text) or the run stalls.
6. **`read_pdf` page budgets are now wired in the shipped adapter.** P1
   session 1 left `decidePdfRead`/`foldPdfRead` unmounted; `dsh-plugin.ts` now
   consults them in the same monotonic guard (defaults 15/90) and folds
   completed reads via an optional `ctx.on('tools/result', …)` subscription.
   The stub tool itself (`plugins/awt-read-pdf-stub.plugin.mjs`) is e2e-only —
   it exists because an unregistered name fails as `UNKNOWN_TOOL` before the
   guard stage; the real pdftotext-backed tool remains profile work.

## Files

- `package.json` / `package-lock.json` — exact `@deepseek-ai/dsh@0.1.0-rc.6` pin
- `profile/package.json`, `profile/cordis.patch.yml` — the `awt-headless` profile
- `plugins/awt-scripted-llm.plugin.mjs` — scripted provider on the real adapter seam
- `plugins/awt-read-pdf-stub.plugin.mjs` — e2e-only `read_pdf` stub tool
- `run-e2e.mjs` — fixture builder, per-scenario dsh launches, assertions, evidence table
