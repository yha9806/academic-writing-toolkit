# P3 — Evidence, Distribution Hardening, Decommission

**2026-09-05 amendment:** the user-requested
[long-document integration](2026-09-05-long-document-integration.md) adds an
optional `workbench/` development package. The decommission record below
describes the original P3 work; the packaged Codex plugin and ChatGPT App
remain retired. The dsh guards and evidence classes are unchanged.

- **Status:** Session 1 COMPLETE (items 1–3 landed and locally verified:
  credential probe green; bundle contract + pack smoke green; E1 offline
  lane discriminates on all four metrics — 84/84 guards, make test 123/123,
  audit clean). The canonical profile also gained the real pdftotext-backed
  `read_pdf` plugin (the e2e stub is now e2e-only). Session 2: §13
  decommission EXECUTED (mvp workbench + wheel packaging; ChatGPT App +
  Cloud Run/Render deploys + App listing docs; plugins/ mirror + sync
  scripts + old marketplace manifest; stale release/ packet — with the bash
  suite, CI jobs, README, and use-case docs reshaped in the same commits;
  every removal points at v0.5.0). **Deliberate deviation from §13's
  archive note:** `archive/skills/` is RETAINED — its validators are
  exercised by ~60 suite tests (thesis-control, evidence-review,
  release-governance against temp fixtures) and §13 never named it; the 11
  bundles are out of the catalogue, which is the property that matters. The
  E2 runbook is `docs/e2-dogfood-runbook.md`. On 2026-09-05 the
  [three-source local E1 pilot](../../e1/published/2026-09-05-local-qwen/README.md)
  collected twelve task observations with a real local model. Neither arm
  produced conforming notes; no writing-efficacy improvement is claimed.
  The author-executed E2 chapter cycle and any cloud-model comparison remain
  unexecuted. One P3-scope item from
  the parent's non-goals (a one-shot thesis-control CSV import script) is
  NOT built — flagged, not silently dropped.
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md` §11 (evidence
  classes), §13 (decommission table), §14 (P3 row)
- **Inputs:** `docs/research/2026-08-16-ecosystem-practices.md` adoptions
  #5 and #8 (deferred from P2 by design)

## Scope, in order

1. **Real-route profile + credential discipline (eco #8).** A canonical
   `profiles/awt-headless/` template: dsh-base + dsh-headless bundles, the
   guards row with enforcement-on defaults, and dormant llm-pi-ai routes
   (prose-fidelity and cost routes) carrying **`apiKeyEnv` references only —
   no secret ever enters a profile file**. `awt install-profile` copies the
   template plus the built guards into a real `$DSH_HOME`, refusing to
   overwrite an existing profile. Red-first gate: a route whose configured
   reference resolves to nothing fails the request with typed
   `MISSING_CREDENTIAL` before any network I/O — asserted by a keyless probe
   (`e2e/run-credential-probe.mjs`), which becomes the fifth `awt verify`
   stage (it needs no key; it asserts the failure).
2. **Distribution hardening (eco #5).** The guards package becomes an
   installable dsh bundle: `dsh.bundle.patch` manifest → `cordis.patch.yml`
   row with safe enforcement-on defaults, `files` whitelist, `engines.dsh`,
   peerDependencies pinned to the attested rc line. A bundle-contract test
   asserts the distribution claim itself. A machine-readable compat baseline
   (`COMPAT.json`: harness version, upstream audit commit, lastVerified)
   replaces prose claims; a pack-and-install smoke (`npm pack` → install the
   tarball into a fresh scratch `DSH_HOME` via the real `dsh plugin add` →
   `--dump-config` carries the row) proves the install story; a scheduled CI
   workflow re-runs the attestation and reports failures as evidence, never
   silently editing claims.
3. **E1 paired-session instrument (§11).** A producer
   (`e1/run-e1.mjs`) drives paired headless sessions per PDF — the skills
   arm (awt profile) vs the plain arm (same model, no skills, no guards) —
   and machine-grades: quote fidelity (string-match quoted spans against
   `pdftotext` of the cited pages), page-number accuracy, notes-file
   parseability (the notes lint), and citations-to-unopened-sources in the
   drafted section. Graders are pure functions with their own offline unit
   tests; the offline lane (scripted adapter) proves the instrument
   end-to-end in CI; the real lane is key-gated and skips cleanly without
   keys. Input PDFs are referenced by a local manifest (`e1/pdfs.json`:
   path + sha256 + page window) and are **never committed**; published
   output is the metrics JSON + a rendered table, generated only by the
   producer — a hand-authored comparison table is a spec violation.
4. **Legacy decommission (§13) — session 2.** Lands in the same PR as the
   replacement so main never loses a working install: mvp workbench
   (`awt/mvp.py`, `mvp_index.html`; `workflow_io.py` SHA-256 binding
   survives as a validator), ChatGPT App (`apps/`), Cloud Run/Render deploys
   (`deploy/`, `render.yaml`, `.github/workflows/deploy-cloud-run-mcp.yml`),
   `plugins/` mirror + sync scripts, stale `release/` packet. The bash
   regression suite and CI jobs that test those surfaces are reshaped in the
   same commits; every removal leaves a README pointer to `v0.5.0` (the last
   supporting tag).
5. **E2 dogfood handoff — session 2.** One real chapter cycle (read → note →
   integrate → edit-contract → review → audit → export) executed **by the
   author** in the dsh app; the session log is the evidence artifact. The
   toolkit side prepares the workspace, profile, and a runbook — it cannot
   run E2 on the author's behalf: an agent-driven "dogfood" would be exactly
   the self-evaluation the evidence classes exist to forbid.

## Gates

- Credential probe green: typed `MISSING_CREDENTIAL`, pre-network, keyless.
- Bundle-contract test green; pack-and-install smoke green on a clean
  checkout; `COMPAT.json` present with harness version + date; scheduled
  re-attestation workflow exists and its steps pass when run on demand.
- E1: grader unit tests + offline lane green in CI; a real-lane run with a
  key produces `e1/results/` metrics from the producer alone.
- Decommission (s2): `make test` green after reshape; public-content audit
  clean; no reference to a removed surface outside README pointers.
- E2 (s2): the author's chapter-cycle session log exists and replays.

## Amendment: awt-web ships in v0.1 (2026-08-16, author-directed)

Parent §15 Q3 deferred the web UI to v0.2 on the assumption it would cost
material P1 scope. It cost one bundle name: `profiles/awt-web` is the
identical enforcement patch over `dsh-base + dsh-web-app`, validated live
before landing (workspace contract + skill catalog injected into a real
web session; the request reached the provider route and failed only on
account balance — 402, not toolchain). `awt install-profile` installs both
surfaces; the scaffold test pins that their patches stay byte-identical.
The headless-first sequencing that Q3 actually protected (P1 e2e without a
browser) is unchanged.

## Non-goals

No npm publication or adoption claims (publishing machinery is tested, not
exercised); no structured-fact writer (harness-pin tripwire still governs);
no web UI; no new writing advice. Citation heuristics stay opt-in with the
disclosed gap (§15 Q4 default) unless the author decides otherwise.

## Budget

Two working sessions; the §12 standing rule (thesis progress outranks
toolkit progress) applies — E2 is the phase's point, not its afterthought.
