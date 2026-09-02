# /logic-review — Paragraph Logic Review

Run `/logic-review` after the author-approved research spine is stable to
identify paragraphs that may need clearer flow, transitions, integration with
neighbouring prose, or removal of duplicated argumentative work.

The script `scripts/audit-logic.py` flags candidates such as very short paragraphs and repeated transition openings. The agent then reads the surrounding context, proposes edits, and waits for approval before changing chapter files.

The semantic pass labels passages as problem, gap, method, evidence,
interpretation, boundary, or transition. It flags repetitive sequences such as
five consecutive `evidence -> disclaimer` endings and consolidates duplicated
functions instead of producing synonymous caveats. Essential local qualifiers
remain next to the claims they bound; fuller study-boundary prose can be
concentrated in the abstract ending, Methods boundary,
Discussion/Limitations, and conclusion.

Use this after drafting or integration, before `/audit` and `/export`.
If the research object, intended use, core question, primary experiment, or
contribution order is unstable, stop the language pass and return to
`/thesis-control` or `/revision-escalation`.
