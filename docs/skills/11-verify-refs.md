# /verify-refs — Reference Authenticity Check

Run `/verify-refs` on a Markdown or `.bib` reference file to check BibTeX structure before submission.

The default implementation is offline and deterministic. It validates required fields by entry type, duplicate keys, DOI shape, URL shape, and arXiv identifier shape. Future online checks can use CrossRef, Semantic Scholar, and arXiv explicitly when network access is available.

This skill is generic toolkit functionality. It does not include project-specific self-citation keys, venue rules, or author names.
