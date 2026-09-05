# P0 — Catalogue Triage

- **Status:** Approved scope (author decisions of 2026-08-16); implementing
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md`
- **Author decisions recorded:** in-place rebuild on this repository; guards in
  pure TypeScript; headless-first (`awt-web` deferred to v0.2); citation
  heuristics disabled in v0.1 with a disclosed gap.

## Scope

1. **Skill catalogue 20 → 9 + 3 references** (parent spec §6). The canonical
   tree stays at `.claude/skills/` until P1 introduces profiles; `.agents/`
   symlinks are updated in place. Removed skills move to `archive/skills/`
   (deleted in P3 with their consumers), so every existing validator and test
   keeps a working path.
2. **Notes lint in TypeScript** under `guards/` (the package P1's guard
   plugins will grow from): validates the `/note` data contract (header
   fields, status vocabulary, Evidence status vocabulary, Thesis Connections
   table, Last updated line). Red-first tests included.
3. **Description-collision truth test**: each skill owns one exclusive routing
   keyword that may appear in no other description; `rebuttal` may appear in
   none; every description is at most 40 words.
4. **Citation tiers disabled**: `/audit` category D is replaced by a disclosed
   gap note; `scripts/audit-citations.py` remains in the repo (the ChatGPT App
   still spawns it until P3) but no skill invokes it.
5. Demo project notes brought into contract conformance (they currently
   violate it).

## Gates (all must be green to close P0)

- `npm --prefix guards test` green, including red-first fixtures that prove
  the lint fails on: wrong status vocabulary, missing Thesis Connections
  table, missing Source line, invalid Evidence status.
- Description-collision test green over the 9 shipped descriptions.
- `make doctor`, `make plugin-check`, and the regression suite pass on CI.
- `.claude/skills/` contains exactly 9 skill directories; `.agents/skills/`
  links resolve; `plugins/` regenerated to the same 9.

## Deferred (recorded, not silently dropped)

- `verify-refs` parser swap to `bibtexparser` → P1.
- Deletion of `archive/skills/`, `scripts/audit-{citations,logic,british-english}.py`,
  and `apps/` → P3 (parent spec §13).
- Session-log page budgets, notes-before-chapters guard, contract-scope guard
  → P1 (this phase ships the lint they will call).
- `map` word counts use `wc -w` via Bash in-skill; session-log projection → P2.
