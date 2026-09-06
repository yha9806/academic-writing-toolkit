# Contributing

Academic Writing Toolkit is an open-source tool for PhD students. Its readers
are not developers of it: they clone it once, run the documented commands, and
expect the daily loop to work on their machine. Most of the rules below exist
because that expectation was broken at least once, and each one names the
incident that earned it.

Read the rules on evidence first. They are what makes this project's claims
worth anything, and they are the ones most often broken by accident.

## Evidence, and never collapsing it

Every claim in this repository carries an evidence class. They are stated
separately and never merged into the word "done".

| Class | Means |
| --- | --- |
| **E0** | a deterministic gate is green in CI |
| **E1** | a paired comparison on real inputs with machine-graded criteria |
| **E2** | the author ran one real chapter cycle through it |
| **E3** | evidence from someone who is not us |

Today the enforcement layer is E0. A three-source E1 pilot exists and its
result was negative under one small local model. E2 has not been run. The
README says so, and it must keep saying so: a tool aimed at people writing
theses has no business implying an efficacy it has not measured.

Concretely: `tested`, `committed`, `reviewed`, `merged` and `released` are five
different statements. Do not write one when you mean another. If a check was
blocked or skipped, say which and why.

## Verify on an environment that is not yours

**The rule:** any claim about installing, launching or first-run behaviour must
be reproduced on a machine state that has never run this toolkit — a fresh
clone, a fresh `$DSH_HOME`, and where relevant a deleted `harness/node_modules`.
State in the pull request which environment you verified on.

**Why:** `awt run` and `awt web` shipped in #42 as "the supported way to start
the app" and could not start on any clean machine. They worked for the author
because `$DSH_HOME/profiles/node_modules` already existed there, populated by
an unrelated earlier dsh run. Independently, #40 proposed a documented
`npm install` into that same directory; it completed in seven minutes and then
refused to boot, because dsh owns that tree and rejects a real directory placed
in it. Two people, two days, the same blind spot in opposite directions.

## A green gate is only evidence about what it covers

**The rule:** when you add or rely on a test, state what it would fail on. If a
change could break a path your gate does not exercise, say so rather than
letting the green tick imply coverage.

**Why:** #40's CI passed on three platforms while its launcher setup could not
start on any of them, because the suite launches dsh from an ordinary npm
prefix and never from the farm the documentation told users to create. A
separate audit found that a macOS matrix leg could not observe a symlink defect
because the harness called `.resolve()` on its temp directory first.

Absence of output is not evidence of success. A command that prints nothing, a
replacement that matched nothing, and a check that ran nothing all look
identical to a passing test.

## Fixtures may not assert what they mock

**The rule:** a test fixture must not stand in for the behaviour under test. If
a fixture hand-builds the thing a command is supposed to produce, at least one
unmocked test must exercise the real command.

**Why:** the scaffold suite hand-created a launcher under a scratch
`$DSH_HOME`, directly beneath a comment asserting that `install-profile` placed
it there. It never did. The mock made a blocking defect untestable and the
suite stayed green through the whole of it.

## Red first

**The rule:** a test for a fix must be shown failing before the fix lands. Say
in the pull request that you saw it red. A test that passes on the unfixed code
is a regression guard, which is fine — but label it as one rather than claiming
it demonstrates the fix.

**Why:** a batch of four new tests once included two that passed against the old
implementation, one because the fixture confounded the variable and one because
the wrong tool was under test.

## Public surface

This repository is public. Do not commit local filesystem paths, machine
account names, private project names, task identifiers from your own tooling,
or anything else that identifies a person or a machine. Frozen evidence packets
are no exception: sanitise the paths, regenerate the receipt hashes, and leave
the observations byte-identical. That order matters — an observation altered to
tidy a path is no longer an observation.

Never commit credentials. Provider keys live in the environment at run time;
profile files carry `apiKeyEnv` references and never values.

## Branches, pull requests and review

`main` is protected: pull requests only, `test` must pass, no force pushes.
Everything else is a short-lived branch, merged and then deleted. There is no
develop branch and no release branch.

- **Link an issue.** A pull request should say which problem it closes. Work
  with no issue behind it usually means the decision has not been made yet.
- **One concern per pull request.** If a fix and a new capability travel
  together, the fix waits for nothing and the capability waits for review.
- **Describe it in your own words.** If a tool wrote your branch, that is fine
  and common here — but the description must be a human explanation of what
  changed and what you verified, not the tool's transcript.
- **A human approves.** Automated review is welcome as input and is never the
  approval. Do not let one agent's output stand as the review of another's.
- **Conflicts.** Resolve by merging `main` into your branch. Search the whole
  file afterwards, not only the conflict markers: a superseded line that sits
  outside a conflict region merges cleanly and silently.

Design decisions that cross modules, are hard to reverse, or change the
product's shape get a spec in `docs/specs/` before implementation. A spec
records the problem, the goals, the **non-goals**, the decision and its
acceptance criteria — and carries a `Status:` header that is the single source
of truth for where that work stands. Writing a spec is not approving it, and
approving it is not implementing it.

## Running the gates

```bash
npm ci --prefix guards && npm run build --prefix guards
npm test --prefix guards         # kernel, testkit against the pinned harness, scaffold
make test                        # the regression suite
npm ci --prefix e2e
node e2e/run-e2e.mjs             # live denial table against the real launcher
node e2e/run-credential-probe.mjs
node e2e/run-skill-scope-probe.mjs
node e1/run-e1.mjs               # offline instrument check
```

All of these are keyless. Anything that needs a provider key is not a gate.

For an installation or first-run change, add the clean-machine walk:

```bash
rm -rf harness/node_modules
DSH=$(mktemp -d); WS=$(mktemp -d)/thesis
node scaffold/awt.mjs install-profile "$DSH"
node scaffold/awt.mjs init "$WS"
DSH_HOME="$DSH" node scaffold/awt.mjs run "$WS" "…"
```

## Where the work is

Current state and open decisions live in issues and in the `Status:` header of
each spec under `docs/specs/`, never in prose that can rot. Three gates stand
between here and a release fit for the audience above:

- **Gate A** — the daily loop runs in a workspace
  (`docs/specs/2026-09-06-gate-a-workspace-contract.md`)
- **Gate B** — the author completes one real chapter cycle (E2)
- **Gate C** — release, tagging and this document's own upkeep

They are ordered. Doing Gate C first would package something that does not yet
run.

## Reporting a problem

Open an issue. The most useful report names the command you ran, the platform,
what you expected, and what happened — and says whether you were in a workspace
created by `awt init` or in a clone of this repository, because several
behaviours legitimately differ between the two.
