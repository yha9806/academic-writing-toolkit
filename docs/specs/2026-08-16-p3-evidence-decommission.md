# P3 — Evidence, Distribution Hardening, Decommission

- **Status:** Session 1 in progress. Sequenced: real-route profile +
  credential discipline → distribution hardening → E1 instrument (this
  session); legacy decommission + E2 handoff (session 2, same release as the
  replacement — never before).
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

## Non-goals

No npm publication or adoption claims (publishing machinery is tested, not
exercised); no structured-fact writer (harness-pin tripwire still governs);
no web UI; no new writing advice. Citation heuristics stay opt-in with the
disclosed gap (§15 Q4 default) unless the author decides otherwise.

## Budget

Two working sessions; the §12 standing rule (thesis progress outranks
toolkit progress) applies — E2 is the phase's point, not its afterthought.
