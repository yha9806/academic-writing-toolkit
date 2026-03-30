# /verify — Fact Verification

Fact-check claims encountered during reading — dates, names, events, citations, attribution of ideas.

---

## What It Does

`/verify` checks a factual claim against authoritative online sources and returns a structured verdict: Confirmed, Needs correction, Incorrect, or Unverifiable. It searches Wikipedia, academic databases, publisher websites, and encyclopedias.

Optionally, it can annotate your notes file with verification tags — but only with your explicit permission.

---

## When To Use

| Scenario | Command |
|----------|---------|
| A date seems wrong | `verify: Goodman published Languages of Art in 1968` |
| Attribution is unclear | `check this: was thing-power originally Spinoza's concept?` |
| Publication details need checking | `/verify the original German edition was 1927` |
| Inline during reading | `is this correct?` (agent infers claim from context) |

### Trigger Words

The skill activates on: `verify`, `check this`, `fact-check`, `is this correct`, `/verify`.

---

## Internal Workflow

```
User says "verify: Panofsky's Perspective as Symbolic Form was published in 1927"
│
├─ 1. Extract the specific factual claim
│     Claim: Publication date of Panofsky's "Perspective as Symbolic Form" = 1927
│
├─ 2. Search authoritative sources (WebSearch)
│     Priority: Wikipedia → academic databases → publisher sites → encyclopedias
│     Query: "Panofsky Perspective as Symbolic Form publication date"
│
├─ 3. Fetch and verify (WebFetch)
│     Cross-reference multiple sources
│     Note conflicting information if found
│
├─ 4. Compare original claim against verified data
│
├─ 5. Output structured verdict
│
└─ 6. Ask: "Annotate notes file?" (only if user confirms)
         If yes → Edit to add (verified) or (corrected: ...) tag
```

---

## Practical Walkthrough

### Scenario: Checking a publication date during reading

**Context:** You're reading Panofsky and encounter a claim about a publication date.

**You type:**
```
verify: Panofsky's "Perspective as Symbolic Form" was first published in 1927
```

**The agent produces:**

```
## Verification

**Claim**: Panofsky's "Perspective as Symbolic Form" was first published in 1927
**Verdict**: Needs correction

| Item | Original | Verified |
|------|----------|----------|
| First publication | 1927 | 1927 (as essay in Vortraege der Bibliothek Warburg) |
| Book edition | (not specified) | 1991 (English translation by Christopher Wood, Zone Books) |

**Source**: [Zone Books catalogue](https://www.zonebooks.org/books/...)
**Confidence**: High
**Notes**: The essay was originally delivered as a lecture in 1924-25 and
published in the Warburg lecture series in 1927. The standalone book
edition most commonly cited is the 1991 English translation. The date
1927 is correct for the original German essay publication.
```

### Scenario: Multiple claims at once

**You type:**
```
verify these:
1. Bennett draws on Deleuze's concept of assemblage
2. Vibrant Matter was published in 2010
3. Thing-power comes from Spinoza's conatus
```

**The agent produces three numbered verification blocks:**

```
### 1. Bennett draws on Deleuze's concept of assemblage
**Verdict**: Needs correction
| Item | Original | Verified |
|------|----------|----------|
| Source of assemblage concept | Deleuze | Deleuze and Guattari (A Thousand Plateaus, 1980) |
**Confidence**: High

### 2. Vibrant Matter was published in 2010
**Verdict**: Confirmed
| Item | Original | Verified |
|------|----------|----------|
| Publication year | 2010 | 2010 (Duke University Press) |
**Confidence**: High

### 3. Thing-power comes from Spinoza's conatus
**Verdict**: Needs correction
| Item | Original | Verified |
|------|----------|----------|
| Origin | Spinoza's conatus | Bennett draws on Spinoza but "thing-power" is her own coinage |
**Confidence**: Medium
**Notes**: Bennett is influenced by Spinoza's conatus but the specific
term "thing-power" does not appear in Spinoza. It is Bennett's synthesis.
```

---

## Annotation

After verification, the agent asks if you want to annotate your notes file.

**If you say "annotate" or "mark in notes":**

The agent uses Edit to find the relevant passage in your notes file and adds an inline tag:

```markdown
# Before
> "thing-power originates from Spinoza's conatus" (p.10)

# After
> "thing-power originates from Spinoza's conatus" (p.10)
> (corrected: "thing-power" is Bennett's own term, influenced by but
>  not identical to Spinoza's conatus. Verified 2026-03-30)
```

The original text is never altered — the tag is appended after it.

---

## Source Priority

The agent searches sources in this order:

| Priority | Source | Best for |
|----------|--------|----------|
| 1 | Wikipedia | Dates, biographical facts, historical events |
| 2 | Google Scholar / JSTOR / PhilPapers | Publication details, academic attribution |
| 3 | Publisher websites | Edition dates, ISBNs, translations |
| 4 | Stanford Encyclopedia of Philosophy | Concept attribution, philosophical lineages |
| 5 | Britannica | General reference when academic sources conflict |

---

## Confidence Levels

| Level | Meaning |
|-------|---------|
| High | Multiple authoritative sources agree |
| Medium | One reliable source, or minor ambiguity |
| Low | Sources conflict, or only non-authoritative sources found |

When confidence is Low, the agent reports all conflicting versions rather than picking one.

---

## Tips

1. **Be specific in your claim.** "Check this paragraph" is too vague. State the exact factual assertion: "verify: Languages of Art was published in 1968 by Bobbs-Merrill."

2. **Use during reading sessions.** `/verify` works best alongside `/read`. When you encounter a surprising claim, verify it immediately rather than making a note to check later.

3. **Batch related claims.** If you have 3-4 facts to check from the same source, verify them all at once. The agent numbers them sequentially.

4. **Annotate selectively.** You don't need to annotate every verified fact. Reserve annotations for corrections and surprising confirmations.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Asking to verify an interpretation | `/verify` checks facts, not arguments. "Is Bennett right about vitalism?" is not a factual claim. |
| Expecting auto-correction of notes | The agent never modifies notes without your explicit "annotate" instruction. |
| Not specifying which claim | If you just say "is this correct?" after a long passage, the agent may pick the wrong claim. Be specific. |

---

## Relationship to Other Skills

```
/read ──► user encounters a claim
              │
              ▼
          /verify ──► verdict displayed
              │
              ├─ user says "annotate"
              │       │
              │       ▼
              │    /note file gets verification tag
              │
              └─ user says "no" → move on
```

`/verify` is a side-channel during reading. It enriches notes but never interrupts the main `/read` → `/note` flow unless you ask it to.
