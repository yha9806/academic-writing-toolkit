# /verify-refs — Reference Authenticity Check

Run `/verify-refs` on a Markdown or `.bib` reference file to check BibTeX structure before submission.

The default implementation is offline and deterministic. It validates required fields by entry type, duplicate keys, DOI shape, URL shape, and arXiv identifier shape.

For explicit metadata verification, run with `--online`. The checker uses CrossRef for DOI records, Semantic Scholar as a secondary DOI/arXiv source, and arXiv for preprint identifiers. Tests and offline review can pass `--metadata-dir` to use local CrossRef JSON, Semantic Scholar JSON, and arXiv Atom fixtures instead of live network calls.

This skill is generic toolkit functionality. It does not include project-specific self-citation keys, venue rules, or author names.
