---
name: readers
description: Open a panel of instruction-bound amnesiac readers on part of a manuscript and report what they carried away, against the points the author wants them to carry. Use when the abstract or introduction changed, when the loop's coverage says the reader panel is stale, or when the author asks whether the contribution comes across.
allowed-tools: Read, Glob, Grep, Bash, Agent
---

# /readers — Reader Panel

## What it answers, and what it does not

It answers **what a first-time reader believes, remembers and could reuse** after reading a part of the manuscript,
set against the points the author wants carried (the intent card). It is how "does the contribution come across"
becomes something counted rather than asserted.

It does not answer whether the paper is good, whether a sentence changed its meaning (the author judges that), or
which single word is hard (word-level agreement with the author was too low to use). An eight-reader panel separates
only large differences; do not report a one-round rise or fall as a result. The script prints these limits in every
report.

## Before running

1. **Intent card.** The author's statement of who the reader is and the two to four points (M1, M2, ...) the reader
   should carry away. The writing loop names it in `target.intent_card`. If it lives outside the workspace's
   `human/` folder it is a draft, and the report says so. Do not write it for the author; draft it only when asked,
   and label it a draft.
2. **Directed questions** (optional, recommended): one per suspected misreading or per point you need confirmed,
   as `id<TAB>question` lines. Free-text summaries overstate misreadings; a directed question confirms one.
   Always consider one about reuse and one about which field the work belongs to.

## Steps

1. Build the packet. From a loop workspace (records which sentences, at which commit, the panel reads):

   ```
   python3 .claude/skills/readers/scripts/build-reader-packet.py --workspace <workspace> --out <dir> [--questions q.tsv]
   ```

   Or from any file: `--text <file> [--bib refs.bib]`. Citations stay in author-year form; they are never replaced by
   a placeholder.

2. Open the readers as sub-agents: two personas (`prompt_R1.txt`, `prompt_R2.txt`) × two models (a small and a
   larger one) × two samples = eight. Give each sub-agent the prompt file's content verbatim and nothing else. Save
   each reply unedited as `<dir>/outputs/<persona>_<model>_<n>.json`, e.g. `R1_haiku_1.json`.

3. Check the outputs; an incomplete output is not a reading and is named, not repaired:

   ```
   python3 .claude/skills/readers/scripts/check-reader-output.py --packet <dir>/packet.json --outputs <dir>/outputs
   ```

4. Judge the intent points. Two judges, independently: you, and a separate sub-agent given the readers' `remember`
   and directed answers with the reader names shuffled and the version not named. Each writes
   `reader<TAB>point<TAB>judge<TAB>✓|△|✗` rows to `<dir>/judgments.tsv`. Judges who disagree count as not carried.

5. Tally, and record the run in the workspace:

   ```
   python3 .claude/skills/readers/scripts/tally-readers.py --packet <dir>/packet.json --outputs <dir>/outputs --judgments <dir>/judgments.tsv
   ```

   To compare two versions, run a full panel on each and pass `--compare-packet/--compare-outputs/--compare-judgments`;
   the report puts a two-sided Fisher p beside each point.

6. Report to the author in three lines per scale (whole text, then paragraphs): what you want the reader to carry
   (the intent card), what the readers carried (the tally, counts with their denominators), and what the text added
   that the author did not intend (misreadings, points the readers took that are not on the card). Mark every
   machine-produced reading as a draft. The author decides what is a gap.

## Where the output goes

`report.md` beside the packet. Real runs on unpublished work stay in the private workspace; never commit reader
outputs or packets to a public repository.

## Fail closed

Each script exits 2 when there is nothing to read, check or tally. A panel with fewer than eight qualified readers,
or fewer than two personas or two models, is recorded as a failure rather than as a reading of the version.
