# Evidence Vocabulary

Salvaged from the retired `/release-governance` skill: the vocabulary earns
its keep; the 7-file packet system did not (its checker validated schema,
never truth, and the packets demonstrably rotted). Use these labels in
prose, reviews, and notes — no standing CSVs.

## Evidence states

- `verified_artifact` — the claim is checked against the exact artifact it
  is about (the file, the run, the quoted page), reproducibly.
- `draft_advisory` — an informed judgement (including any agent's review)
  that no artifact check backs yet.
- `human_final` — the author has personally confirmed it. Only a human can
  apply this label, and only after actually looking.

## The one rule that must never bend

**An agent-generated draft or review is never silently promoted to
author-confirmed evidence.** Work an agent produced stays `draft_advisory`
until the author examines it; tooling may verify structure, only the author
confirms substance. Labels live where the reader can see them — a claim
whose state the reader cannot determine is `draft_advisory` by default.

## Reading-notes firewall (same idea, upstream)

`Evidence status: full_text | abstract_only | metadata_only` in notes files
is this vocabulary applied to sources: cite as support only what was
actually read.
