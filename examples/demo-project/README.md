# Demo Project

This demo shows the local Academic Writing Toolkit workflow without private research material.

Run these commands from the repository root:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

The demo includes:

- a short chapter draft in [`chapters/ch01.md`](chapters/ch01.md)
- two reading notes in [`literature/reading_notes/`](literature/reading_notes/)
- a BibTeX file in [`references.bib`](references.bib)
- an evidence-review packet in [`evidence/`](evidence/)
- a release-governance packet in [`release/`](release/)

Open this folder in Codex, Claude Code, Gemini CLI, Cursor, or another compatible local agent and ask:

```text
Explain how this demo project moves from reading notes to evidence review and release governance.
```
