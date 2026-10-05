"""The checks the loop runs, and the ones it deliberately does not.

Every check registered in scripts/check-fails-closed.py appears here once: in CHECKS, with what makes it stale and
how to run it on the tracked draft, or in UNWIRED, with the reason it is not a check on a manuscript. A test holds
the two lists to the registry, so a new check cannot arrive in the toolkit without the loop either running it or
saying why not. The same test holds every skill to the Codex installer's list.

Per check:
  kind      script: deterministic, cheap, run by `loop update` whenever it is due.
            panel:  costs model calls and needs the host to open sub-agents; the loop only says when it is due.
  scripts   names in check-fails-closed.py's form: "<skill>/<file>" or "scripts/<file>".
  formats   draft formats the check can read. A draft in another format gets the status 不适用, never 最新.
  instead   for a format it cannot read: the check that covers the same ground there, or None when nothing does.
  scope     what makes a past run stale. kind: all | cite | numbers | sections | none (inputs only).
  needs     configuration the check cannot run without, as dotted paths into the workspace config.
  optin     True when writing that configuration is how a workspace turns the check on: without it the check is
            不适用 (not turned on), not 缺前提, so nothing asks for a run and it is no gap in the toolkit.
  inputs    function(cfg) -> {role: repo path} of files the check reads besides the draft; they are archived with it,
            and a change to any of them makes the check stale.
  outside   function(cfg) -> [absolute paths] read in place (a venue corpus, an intent card); their content hash is
            part of what a run is keyed on. An entry git:<repo> is that repository's HEAD commit instead.
  base      optional function(cfg, head) -> fallback git ref, for a check that compares two versions: the draft at the
            base coverage.resolve_base picks (the check's last clean head, else this ref) is archived beside the
            draft, in BASE_DIR, and the run record names it.
  argv      function(ctx) -> argument list, run with cwd = the archived tree.
"""
import os
import sys
from pathlib import Path

# The toolkit checkout the scripts live in. A mutation run copies the engine elsewhere and points this back.
ENGINE_ROOT = Path(os.environ.get("AWT_ROOT") or Path(__file__).resolve().parents[4])
KINDS = ("script", "panel")
SCOPES = ("all", "cite", "numbers", "sections", "none", "tree")
UNWIRED_REASON_MIN = 20


def get(cfg, dotted):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur or cur[part] in (None, "", [], {}):
            return None
        cur = cur[part]
    return cur


def script_path(name):
    if Path(name).is_absolute():  # tests register throwaway checks by absolute path
        return Path(name)
    skill, _, file = name.partition("/")
    if skill == "scripts":
        return ENGINE_ROOT / "scripts" / file
    return ENGINE_ROOT / ".claude" / "skills" / skill / "scripts" / file


def _py(ctx, name):
    return [sys.executable, str(script_path(name))]


def _node(ctx, name):
    return ["node", str(script_path(name))]


def _ledger_inputs(cfg):
    led = get(cfg, "overview.ledger") or {}
    out = {"ledger": led.get("path")} if led.get("path") else {}
    # Works named in the bibliography (shorttitle) or in a names table: a mention with no \cite is listed
    # (spec 2026-09-30-claim-ledger-reading Q2).
    if get(cfg, "inputs.bib"):
        out["bib"] = get(cfg, "inputs.bib")
    if led.get("names"):
        out["names"] = led["names"]
    # More ledgers checked with it (a supplement's own, 09-27): read together, each one's change makes it stale.
    for i, p in enumerate(led.get("also") or [], 1):
        out[f"ledger{i}"] = p
    for i, p in enumerate(led.get("archive") or []):
        out[f"archive{i}"] = p
    return out


def credits_path(cfg):
    """Where the author's accepted method credits live: the ledger's own setting, as the overview reads it."""
    led = get(cfg, "overview.ledger") or {}
    if led.get("credits"):
        return Path(led["credits"]).expanduser()
    return Path(cfg["_ws"]) / "human" / "credits.txt" if cfg.get("_ws") else None


def _ledger_argv(ctx):
    led = ctx["cfg"]["overview"]["ledger"]
    args = _py(ctx, "audit/audit-claim-ledger.py") + ["--base-dir", led["base_dir"], "--ledger", led["path"], "--json"]
    for p in led.get("also") or []:
        args += ["--ledger", p]
    # The also-checked files (a supplement outside base_dir): their citing sentences are the manuscript's too.
    for p in ctx.get("also") or []:
        args += ["--also-file", p]
    credits = credits_path(ctx["cfg"])
    if credits and credits.is_file():
        args += ["--credits", str(credits)]
    if (ctx.get("inputs") or {}).get("bib"):
        args += ["--bib", ctx["inputs"]["bib"]]
    if (ctx.get("inputs") or {}).get("names"):
        args += ["--names", ctx["inputs"]["names"]]
    return args


def _credits_outside(cfg):
    """The author's accepted method credits change what the ledger audit reports."""
    p = credits_path(cfg)
    return [str(p)] if p else []


def _literature_optional(cfg):
    """Reading notes and source PDFs a Markdown citation check reads when the repository has them."""
    return {"literature": get(cfg, "inputs.literature_dir") or "literature"}


def _bib(cfg):
    b = get(cfg, "inputs.bib")
    return {"bib": b} if b else {}


def _positioning_argv(ctx):
    args = _py(ctx, "audit/audit-claim-positioning.py") + ["--base-dir", ".", "--json"]
    if ctx["inputs"].get("bib"):
        args += ["--bib", ctx["inputs"]["bib"]]
    return args


def number_ledger_specs(cfg):
    """inputs.number_ledger: one path, or a list whose items are a path or {"path": ..., "files": [...]}: the prose
    files that ledger answers for (the text's numbers, a supplement's). [(path, files or None)]."""
    v = get(cfg, "inputs.number_ledger")
    out = []
    for x in ([v] if isinstance(v, (str, dict)) else (v or [])):
        if isinstance(x, str) and x:
            out.append((x, None))
        elif isinstance(x, dict) and isinstance(x.get("path"), str) and x["path"]:
            files = [f for f in (x.get("files") or []) if isinstance(f, str) and f]
            out.append((x["path"], files or None))
    return out


def number_ledgers(cfg):
    return [p for p, _ in number_ledger_specs(cfg)]


def _numbers_argv(ctx):
    args = _py(ctx, "audit/audit-number-ledger.py") + ["--base-dir", ".", "--json"]
    for p, files in number_ledger_specs(ctx["cfg"]):
        args += ["--ledger", p] + (["--ledger-files", f"{p}={','.join(files)}"] if files else [])
    return args


def _numbers_inputs(cfg):
    specs = number_ledger_specs(cfg)
    out = {"ledger": specs[0][0]} if specs else {}
    for i, (p, _) in enumerate(specs[1:], 1):
        out[f"ledger{i}"] = p
    # The files each ledger answers for are read and watched too (globs are expanded at the commit): a supplement's
    # tables that its ledger counts copies in (09-27: without them every table copy read as a changed count).
    for i, (_, files) in enumerate(specs):
        for j, f in enumerate(files or []):
            out[f"files{i}_{j}"] = f
    for i, p in enumerate(get(cfg, "inputs.number_artifacts") or []):
        out[f"artifact{i}"] = p
    return out


def method_ledger_cfg(cfg):
    """inputs.method_ledger: {"path": <tsv in the manuscript>, "repos": {name: {"path", "commit" | "commit_file",
    "prefixes"}}, "full": [draft files every sentence of which needs a row], "note_flags": <regex>,
    "manuscript_prefixes": [...]} (spec 2026-09-29-method-ledger). A bare string is the path alone."""
    v = get(cfg, "inputs.method_ledger")
    if isinstance(v, str) and v:
        return {"path": v}
    return v if isinstance(v, dict) and isinstance(v.get("path"), str) and v["path"] else None


def _method_argv(ctx):
    m = method_ledger_cfg(ctx["cfg"]) or {}
    args = _py(ctx, "audit/audit-method-ledger.py") + ["--base-dir", ".", "--ledger", m.get("path", ""), "--json"]
    for name, r in (m.get("repos") or {}).items():
        if not isinstance(r, dict) or not r.get("path"):
            continue
        args += ["--repo", f"{name}={r['path']}" + (f"@{r['commit']}" if r.get("commit") else "")]
        if r.get("commit_file"):
            args += ["--repo-commit-file", f"{name}={r['commit_file']}"]
        for pre in r.get("prefixes") or []:
            args += ["--repo-prefix", f"{name}={pre}"]
    for pre in m.get("manuscript_prefixes") or []:
        args += ["--manuscript-prefix", pre]
    for f in m.get("full") or []:
        args += ["--full", f]
    if m.get("note_flags"):
        args += ["--note-flags", m["note_flags"]]
    if ctx["cfg"].get("repo"):
        args += ["--git", str(Path(ctx["cfg"]["repo"]).expanduser())]
    if ctx.get("ws"):
        # row ids seen on earlier runs: a row that vanishes without being retired is reported (G3)
        state = Path(ctx["ws"]) / "cache" / "coverage" / "method-ledger-ids.json"
        if ctx.get("precheck"):
            # a precheck reads the ids seen so far and records none: it works on a copy
            copy = Path(ctx["tmp"]) / ".precheck-method-ledger-ids.json"
            if state.is_file():
                copy.write_bytes(state.read_bytes())
            state = copy
        args += ["--state", str(state)]
    return args


def _method_inputs(cfg):
    m = method_ledger_cfg(cfg)
    return {"ledger": m["path"]} if m else {}


def _method_outside(cfg):
    """An unpinned repository is read as its working copy: its HEAD commit makes the check stale. A pinned one moves
    only when the config (or the commit file in the draft) does."""
    m = method_ledger_cfg(cfg) or {}
    return [f"git:{r['path']}" for r in (m.get("repos") or {}).values()
            if isinstance(r, dict) and r.get("path") and not r.get("commit") and not r.get("commit_file")]


def _generated_inputs(cfg):
    return {"manifest": get(cfg, "inputs.generated")}


def _generated_outside(cfg):
    """The data repositories the manifest's generators run from, as git:<repo> (not a file path: coverage reads it as
    that repository's HEAD commit), so the check reruns when one commits.
    Read from the manifest at the configured ref; an unreadable manifest names none (the run then fails on it)."""
    import json
    import subprocess
    m = get(cfg, "inputs.generated")
    if not m or not cfg.get("repo"):
        return []
    r = subprocess.run(["git", "-C", str(Path(cfg["repo"]).expanduser()), "show", f"{cfg.get('ref') or 'HEAD'}:{m}"],
                       capture_output=True, text=True)
    if r.returncode:
        return []
    try:
        gens = json.loads(r.stdout).get("generators") or []
    except (ValueError, AttributeError):
        return []
    if not isinstance(gens, list):
        return []
    repos = {str(Path(os.path.expanduser(g["repo"])).resolve()) for g in gens
             if isinstance(g, dict) and isinstance(g.get("repo"), str) and g["repo"]}
    return [f"git:{r}" for r in sorted(repos)]


def _float_reviews_argv(ctx):
    """Every draft file and every also-checked file is a place a float can start from; the script follows \input from
    each and counts a file once."""
    mains = list(ctx["drafts"]) + [p for p in (get(ctx["cfg"], "inputs.also_checked") or [])
                                   if p not in ctx["drafts"] and (Path(ctx["tmp"]) / p).is_file()]
    args = _py(ctx, "audit/audit-float-reviews.py") + ["--base-dir", ".", "--reviews", ctx["inputs"]["reviews"], "--json"]
    for m in mains:
        args += ["--main", m]
    return args


def _fingerprint_venue_argv(ctx):
    corpus = get(ctx["cfg"], "target.venue_corpus.dir")
    return _py(ctx, "audit/audit-prose-fingerprint.py") + ["--target", ".", "--baseline", str(Path(corpus).expanduser()),
                                                           "--json", "--per-file"]


def _fingerprint_bib_argv(ctx):
    args = _py(ctx, "audit/audit-prose-fingerprint.py") + [
        "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "inputs.literature")).expanduser()), "--json",
        "--per-file"]
    for g in get(ctx["cfg"], "inputs.literature_exclude") or []:
        args += ["--exclude", g]
    return args


def _venue_outside(cfg):
    out = []
    m = get(cfg, "target.venue_corpus.dir")
    if m:
        out.append(str(Path(m).expanduser()))
    return out


ACCEPTED_DEFAULT = ".awt-accepted-rewrites.tsv"


def accepted_rewrites_path(cfg):
    """The ledger of flagged sentences the author accepted (key, reason, who, sentence), in the manuscript repository:
    read in place by the changed-sentence audit's committed runs and by the rewrite gates."""
    return Path(cfg["repo"]) / (get(cfg, "draft.accepted_rewrites") or ACCEPTED_DEFAULT)


def claim_ledgers(cfg):
    """The claim ledgers, as absolute paths in the working tree: the changed-sentence check names the rows an edit
    unbinds (spec 2026-09-30-claim-ledger-reading Q6), and it runs in a copy that holds only the draft."""
    led = get(cfg, "overview.ledger") or {}
    repo = Path(cfg.get("repo") or ".").expanduser()
    return [str(repo / p) for p in [led.get("path")] + list(led.get("also") or []) if p]


def _sentence_outside(cfg):
    # An acceptance changes what the last run means: the ledger is read in place, so editing it makes the run stale.
    # So does a claim ledger: the rows an edit unbinds come from it.
    return _venue_outside(cfg) + [str(accepted_rewrites_path(cfg))] + claim_ledgers(cfg)


def spelling_mode(cfg):
    """consistent (either convention, never a mixture) for a journal or a conference, british otherwise, unless the
    workspace names one in target.spelling."""
    return get(cfg, "target.spelling") or ("consistent" if cfg.get("genre") in ("journal", "conference") else "british")


def _literature_outside(cfg):
    lit = get(cfg, "inputs.literature")
    return [str(Path(lit).expanduser())] if lit else []


def _intent_outside(cfg):
    """What the panel is keyed on besides the text: the intent card and the directed questions."""
    return [str(Path(p).expanduser()) for p in (get(cfg, "target.intent_card"), get(cfg, "target.readers.questions")) if p]


def _notes_inputs(cfg):
    return {f"note{i}": p for i, p in enumerate(get(cfg, "inputs.notes") or [])}


def _notes_argv(ctx):
    return _node(ctx, "note/notes-lint.mjs") + ["--json"] + [v for k, v in sorted(ctx["inputs"].items())]


def _none(cfg):
    return {}


# Where a changed-sentence check finds the version before the edit, beside the archived draft. A dot directory, so a
# check that reads the whole tree skips it.
BASE_DIR = ".awt-base"


def _base_ref(cfg, head):
    """The fallback base of the changed-sentence check: draft.base_ref when the author has set one, else the commit
    before head. coverage.resolve_base prefers the last commit at which the check flagged nothing, so a round of
    several commits is read as a whole and a flagged sentence stays reported until it is fixed or accepted (by moving
    draft.base_ref forward)."""
    return get(cfg, "draft.base_ref") or f"{head}~1"


def _carriers_file(ctx):
    """The claims ledger's required wordings, one pattern per line, for the changed-sentence check to hold removed
    sentences against (spec 2026-09-25 §4.2). Written in a dot directory beside the draft, which the check does not
    read as prose. None when there is no ledger, no pattern, or no directory to write in."""
    path = (ctx.get("cfg") or {}).get("claims")
    if not path or not ctx.get("tmp"):
        return None
    try:
        raw = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError:
        return None
    from . import state as S
    _, claims, _, _ = S.parse(raw)
    patterns = [r for c in claims for r, _ in c.get("must") or []]
    if not patterns:
        return None
    out = Path(ctx["tmp"]) / ".loop-carriers" / "required.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(p + "\n" for p in patterns), encoding="utf-8")
    return out


def _sentence_changes_argv(ctx):
    args = _py(ctx, "audit/audit-sentence-changes.py") + ["--target", ".", "--base", BASE_DIR, "--json"]
    carriers = _carriers_file(ctx)
    if carriers:
        args += ["--carriers", str(carriers)]
    for p in claim_ledgers(ctx["cfg"]):
        args += ["--ledger", p]
    corpus = get(ctx["cfg"], "target.venue_corpus.dir")
    if corpus:
        args += ["--baseline", str(Path(corpus).expanduser())]
        if ctx.get("ws"):
            # reading a corpus of PDFs takes seconds; the measured sentences are kept in the workspace cache
            args += ["--venue-cache", str(Path(ctx["ws"]) / "cache" / "coverage" / "venue-sentences.json")]
    return args


def _no_outside(cfg):
    return []


CHECKS = [
    {"id": "claim-ledger", "name": "主张台账", "kind": "script", "scripts": ["audit/audit-claim-ledger.py"],
     "formats": ["latex"], "instead": {"markdown": "citation-fidelity"},
     "scope": {"kind": "cite"}, "needs": ["overview.ledger"], "config_keys": ["overview.ledger"],
     "inputs": _ledger_inputs, "outside": _credits_outside, "argv": _ledger_argv, "also": True},
    {"id": "claim-positioning", "name": "定位", "kind": "script", "scripts": ["audit/audit-claim-positioning.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _bib, "outside": _no_outside, "argv": _positioning_argv},
    {"id": "number-ledger", "name": "数字台账", "kind": "script", "scripts": ["audit/audit-number-ledger.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "numbers"}, "needs": ["inputs.number_ledger"],
     "inputs": _numbers_inputs, "outside": _no_outside, "also": True,
     "argv": _numbers_argv},
    {"id": "method-ledger", "name": "文字对代码", "kind": "script", "scripts": ["audit/audit-method-ledger.py"],
     "formats": ["latex"], "instead": {},
     "scope": {"kind": "tree"}, "needs": ["inputs.method_ledger"], "optin": True, "tree": True,
     "config_keys": ["inputs.method_ledger"],
     "inputs": _method_inputs, "outside": _method_outside, "argv": _method_argv},
    {"id": "generated-copies", "name": "生成物对照", "kind": "script", "scripts": ["audit/audit-generated-copies.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "tree"}, "needs": ["inputs.generated"], "tree": True, "timeout": 600,
     "inputs": _generated_inputs, "outside": _generated_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-generated-copies.py") + [
         "--base-dir", ".", "--manifest", ctx["inputs"]["manifest"], "--json"]},
    {"id": "float-reviews", "name": "图表看过", "kind": "script", "scripts": ["audit/audit-float-reviews.py"],
     "formats": ["latex"], "instead": {},
     "scope": {"kind": "tree"}, "needs": ["inputs.float_reviews"], "tree": True,
     "inputs": lambda cfg: {"reviews": get(cfg, "inputs.float_reviews")}, "outside": _no_outside,
     "argv": _float_reviews_argv},
    {"id": "fingerprint-venue", "name": "文风·对照目标刊物", "kind": "script",
     "scripts": ["audit/audit-prose-fingerprint.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["target.venue_corpus.dir"], "config_keys": ["target.venue"],
     "inputs": _none, "outside": _venue_outside, "argv": _fingerprint_venue_argv},
    {"id": "fingerprint-bibliography", "name": "文风·对照参考文献", "kind": "script",
     "scripts": ["audit/audit-prose-fingerprint.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["inputs.literature"], "config_keys": ["inputs.literature_exclude"],
     "inputs": _none, "outside": _literature_outside, "argv": _fingerprint_bib_argv},
    {"id": "structure-venue", "name": "句子结构·对照目标刊物", "kind": "script",
     "scripts": ["audit/audit-prose-structure.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["target.venue_corpus.dir"], "config_keys": ["target.venue"],
     "inputs": _none, "outside": _venue_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-prose-structure.py") + [
         "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "target.venue_corpus.dir")).expanduser()), "--json"]},
    {"id": "structure-bibliography", "name": "句子结构·对照参考文献", "kind": "script",
     "scripts": ["audit/audit-prose-structure.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["inputs.literature"], "config_keys": ["inputs.literature_exclude"],
     "inputs": _none, "outside": _literature_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-prose-structure.py") + [
         "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "inputs.literature")).expanduser()), "--json"]
         + [x for g in (get(ctx["cfg"], "inputs.literature_exclude") or []) for x in ("--exclude", g)]},
    {"id": "sentence-changes", "name": "改句结构", "kind": "script", "scripts": ["audit/audit-sentence-changes.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": [], "config_keys": ["draft.base_ref", "target.venue"],
     "inputs": _none, "outside": _sentence_outside, "base": _base_ref, "argv": _sentence_changes_argv},
    {"id": "verify-refs", "name": "参考文献条目", "kind": "script", "scripts": ["verify-refs/verify-refs.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "none"}, "needs": ["inputs.bib"],
     "inputs": _bib, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "verify-refs/verify-refs.py") + ["--bib", ctx["inputs"]["bib"], "--json"]},
    {"id": "notes-lint", "name": "阅读笔记格式", "kind": "script", "scripts": ["note/notes-lint.mjs"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "none"}, "needs": ["inputs.notes"],
     "inputs": _notes_inputs, "outside": _no_outside, "argv": _notes_argv},
    {"id": "citation-fidelity", "name": "引文忠实度", "kind": "script", "scripts": ["audit/audit-citation-fidelity.mjs"],
     "formats": ["markdown"], "instead": {"latex": "claim-ledger"},
     "scope": {"kind": "cite"}, "needs": [], "optional": _literature_optional,
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _node(ctx, "audit/audit-citation-fidelity.mjs") + ["--base-dir", ".", "--json"]},
    {"id": "citation-style", "name": "引文格式", "kind": "script", "scripts": ["scripts/audit-citations.py"],
     "formats": ["markdown"], "instead": {"latex": "cite-bib"},
     "scope": {"kind": "cite"}, "needs": [], "optional": _literature_optional,
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-citations.py") + ["--base-dir", ".", "--json"]},
    # The three chapter checks read chapters/*.md; "view" has the loop write the draft there first, LaTeX or
    # Markdown, wherever the draft lives (prose-view.py). Without it a draft outside chapters/ read as nothing.
    {"id": "british-english", "name": "拼写", "kind": "script",
     "scripts": ["scripts/audit-british-english.py", "audit/prose-view.py"],
     "formats": ["markdown", "latex"], "instead": {}, "view": True,
     "scope": {"kind": "all"}, "needs": [], "config_keys": ["target.spelling", "genre"],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-british-english.py") + ["--base-dir", ctx.get("view", "."), "--json",
                                                                         "--mode", spelling_mode(ctx["cfg"])]},
    {"id": "paragraph-logic", "name": "段落逻辑", "kind": "script",
     "scripts": ["scripts/audit-logic.py", "audit/prose-view.py"],
     "formats": ["markdown", "latex"], "instead": {}, "view": True,
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-logic.py") + ["--base-dir", ctx.get("view", "."), "--json"]},
    # Paragraphs whose first sentence leads with a number, a formula, or a table or figure. A pointer for reading, not
    # a verdict: data paragraphs rightly open with data. Added after an author rejected figure-first openings that
    # every sentence-level check had passed.
    {"id": "paragraph-openers", "name": "段首", "kind": "script",
     "scripts": ["scripts/audit-openers.py", "audit/prose-view.py"],
     "formats": ["markdown", "latex"], "instead": {}, "view": True,
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-openers.py") + ["--base-dir", ctx.get("view", "."), "--json"]},
    # Quantities in the abstract against the abstracts the venue publishes (spec 2026-10-05-abstract-numbers): a prompt
    # above the 90th percentile, never a verdict on which number goes. Added after a revision doubled the venue's most.
    {"id": "abstract-numbers", "name": "摘要数字", "kind": "script", "scripts": ["audit/audit-abstract-numbers.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "sections", "config": "target.abstract_sections", "default": ["A"]},
     "needs": ["target.venue_corpus.dir"], "config_keys": ["target.venue"],
     "inputs": _none, "outside": _venue_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-abstract-numbers.py") + [
         "--baseline", str(Path(get(ctx["cfg"], "target.venue_corpus.dir")).expanduser()), "--json"] + ctx["drafts"]},
    {"id": "word-count", "name": "字数", "kind": "script", "scripts": ["map/count-words.mjs", "audit/prose-view.py"],
     "formats": ["markdown", "latex"], "instead": {}, "view": True,
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _node(ctx, "map/count-words.mjs") + ["--base-dir", ctx.get("view", "."), "--json"]},
    # LaTeX citations come from a BibTeX file, so the check is that the two agree both ways, across every \input.
    {"id": "cite-bib", "name": "引文对账", "kind": "script", "scripts": ["verify-refs/reconcile-cites.py"],
     "formats": ["latex"], "instead": {"markdown": "citation-style"}, "tree": True,
     "scope": {"kind": "cite"}, "needs": ["inputs.bib"], "also": True,
     "inputs": _bib, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "verify-refs/reconcile-cites.py") + ["--bib", ctx["inputs"]["bib"], "--root", ".",
                                                                       "--json"] + ctx["drafts"]},
    {"id": "readers", "name": "读者组", "kind": "panel",
     "scripts": ["readers/build-reader-packet.py", "readers/check-reader-output.py", "readers/tally-readers.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "sections", "config": "target.readers.sections", "default": ["A", "I"]},
     "needs": ["target.intent_card"], "config_keys": ["target.readers.sections", "target.readers.personas"],
     "inputs": _none, "outside": _intent_outside, "argv": None},
]

UNWIRED = {
    "review/audit-review-findings.py":
        "只验 /review 写出的发现文件能否解析、是否只落在声明读过的文件里；对象是评审报告。/review 本身是模型阅读的稿件评审，"
        "见 MODEL_READ",
    "scripts/check_lost_in_conversation_bench.py":
        "校验 writing-control 基准的夹具目录（三种工作流与控制产物是否齐），对象是基准夹具，不是稿件",
    "scripts/audit-public-content.py":
        "审的是 AWT 公开仓自己有没有混进私密内容；对象是工具仓，不是用户的稿件，由 AWT 的测试套件调用",
}

# Skills present on disk but not installed for Codex, with the reason. Empty: every skill is installed.
SKILLS_NOT_INSTALLED = {}

# Checks a model performs by reading, with no script and so no run record: the loop cannot tell whether they have
# looked at the current draft. They are listed in every coverage table so that their absence is visible.
MODEL_READ = {
    "review": "/review：模型通读稿件，写出带锚点的发现（文件:行 + 原文 + 一句话问题）；没有运行记录，循环看不出它读的是哪一版",
    "audit": "/audit 的 A 数字一致、B 术语与缩写首次定义、C 交叉引用：由模型阅读完成，不是脚本；循环看不出它们查没查过当前稿",
}

# Skills that make no check on a manuscript, with what they do instead.
SKILL_ROLES = {
    "read": "逐页读文献、写带页码的笔记；不对稿件下判断",
    "integrate": "把笔记整合进章节：整合计划、编辑范围、升级规则；不对稿件下判断",
    "export": "把章节转成 Word 与 ZIP；不对稿件下判断",
}

# check-fails-closed.py's NOT_CHECKS, acknowledged here: moving a check there to escape the wiring invariant has to
# be done in two places, on purpose.
NOT_CHECKS_ACK = {
    "export/convert_to_docx.py", "audit/citations.mjs", "audit/quote-fidelity.mjs", "audit/pdf-pages.mjs",
    "audit/build-venue-baseline.py", "audit/venue-topic-fit.py",
}


def by_id(cid):
    return next(c for c in CHECKS if c["id"] == cid)


def project_checks(cfg):
    """A manuscript's own checks (a submission build, a glyph check), declared in the workspace:

        "project_checks": [{"id": "build", "name": "...", "argv": ["python3", "tools/build.py"],
                            "auto": false, "timeout": 900}]

    Each runs on the whole repository archived at HEAD and is stale whenever that tree changes. They make no JSON
    promise, so exit 0 is a pass and anything else a failure. `auto: false` (the default) keeps a slow build out of
    `loop update`: it is run by `loop coverage --run --only <id>`, and until then it shows as not current."""
    out = []
    for p in cfg.get("project_checks") or []:
        argv = list(p["argv"])
        out.append({"id": p["id"], "name": p.get("name") or p["id"], "kind": "script", "project": True,
                    "definition": dict(p),
                    "auto": bool(p.get("auto", False)), "timeout": int(p.get("timeout", 900)), "scripts": [],
                    "formats": ["latex", "markdown"], "instead": {}, "scope": {"kind": "tree"}, "needs": [],
                    "inputs": _none, "outside": _no_outside, "argv": (lambda ctx, argv=argv: argv)})
    return out


def all_checks(cfg):
    """The toolkit's checks and this workspace's own."""
    return CHECKS + project_checks(cfg)


def wired_scripts():
    return {s for c in CHECKS for s in c["scripts"]}


def wiring_problems(registered, skills, installed, documented=None, not_checks=None):
    """Problems with how the toolkit's checks and skills reach a manuscript. Empty list = nothing unaccounted for."""
    problems = []
    wired = wired_scripts()
    for name in sorted(set(registered) - wired - set(UNWIRED)):
        problems.append(f"{name}：已登记为检查（check-fails-closed.py），但写作循环既不跑它，也没在 UNWIRED 写理由")
    for name in sorted(wired - set(registered)):
        problems.append(f"{name}：目录里有，但没在 check-fails-closed.py 登记为检查（空目标会不会假绿没人验）")
    for name in sorted(set(UNWIRED) - set(registered)):
        problems.append(f"{name}：在 UNWIRED 里，但已不是登记的检查；删掉这一条")
    for name, reason in sorted(UNWIRED.items()):
        if len((reason or "").strip()) < UNWIRED_REASON_MIN:
            problems.append(f"{name}：UNWIRED 的理由太短（少于 {UNWIRED_REASON_MIN} 字），说清楚为什么它不是对稿件的检查")
    for s in sorted(set(skills) - set(installed) - set(SKILLS_NOT_INSTALLED)):
        problems.append(f"技能 {s}：在 .claude/skills/ 里，但 Codex 安装器不装它，也没在 SKILLS_NOT_INSTALLED 写理由")
    if documented is not None:
        for s in sorted(set(skills) - set(documented)):
            problems.append(f"技能 {s}：装得上，但 docs/skills/README.md 的技能表里没有它，用户发现不了")
    for s in sorted(set(installed) - set(skills)):
        problems.append(f"技能 {s}：安装器要装，但 .claude/skills/ 里没有")
    for c in CHECKS:
        for s in c["scripts"]:
            if not script_path(s).is_file():
                problems.append(f"{c['id']}：脚本 {s} 不在盘上")
    owners = {s.split("/", 1)[0] for s in wired}
    for s in sorted(set(skills) - owners - set(SKILL_ROLES) - set(MODEL_READ)):
        problems.append(f"技能 {s}：没有一项检查在目录里，也没在 SKILL_ROLES / MODEL_READ 说明它是什么")
    if not_checks is not None:
        for name in sorted(set(not_checks) ^ NOT_CHECKS_ACK):
            problems.append(f"{name}：check-fails-closed 的 NOT_CHECKS 与 catalogue.NOT_CHECKS_ACK 不一致（改一边必须改另一边）")
    return problems
