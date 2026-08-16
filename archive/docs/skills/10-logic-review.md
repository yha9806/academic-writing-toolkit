# /logic-review — Paragraph Logic Review

Run `/logic-review` to identify paragraphs that may need clearer flow, transitions, or integration with neighbouring prose.

The script `scripts/audit-logic.py` flags candidates such as very short paragraphs and repeated transition openings. The agent then reads the surrounding context, proposes edits, and waits for approval before changing chapter files.

Use this after drafting or integration, before `/audit` and `/export`.
