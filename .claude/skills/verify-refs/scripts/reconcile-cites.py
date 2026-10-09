#!/usr/bin/env python3
"""Reconcile a LaTeX manuscript's citations with its BibTeX file, both ways.

    python3 reconcile-cites.py --bib references.bib [--root DIR] [--style auto|author-year|numeric] [--json] FILE...

Reads each FILE and every file it pulls in with \\input, \\include or \\subfile (relative to --root, ".tex" added
when missing), and collects the keys of every citation command (\\cite, \\citet, \\citep, \\citeauthor, \\nocite,
\\parencite, \\textcite, \\autocite ...). \\nocite{*} cites every entry. Reports:

- cited-not-in-bib: a key the text cites that the bibliography does not define (with where it is first cited);
- bib-not-cited:    an entry the bibliography defines that nothing reads;
- author-named-twice: in a style that prints author names, a sentence that names a cited work's first author in its
  own words and also prints that name through the citation: "Smith et al. report ... \\citep{smith}" prints "Smith
  et al. report ... (Smith et al., 2020)". \\citet, \\citeauthor plus \\citeyearpar, or a numeric style says it
  once. Two citations of one key in a sentence that both print the name count too. The name is the first author's
  surname from the bibliography (a braced corporate author whole), matched with accents dropped; a capitalised word
  that opens the sentence counts only when "et al.", "and", "&", "'s", "(" or "," follows it, since an author called
  Long or Young would otherwise match every sentence that starts with the word. A name that names a method rather
  than its authors ("McNemar's test", "the Wilcoxon signed-rank test", "a Bonferroni correction") is left out:
  citing the method's source beside it is the usual form.

The citation style is read from the files: the last of \\setcitestyle, \\citestyle, natbib's numbers / authoryear
option, biblatex's style, apacite, and the class (acmart is numeric until set otherwise); failing those, the
bibliography style (plainnat, apalike, apacite ... print names; plain, unsrt, ieeetr ... do not). --style overrides
it, for a build that rewrites the class or the bibliography style for a venue so that the source says one style and
the submission prints another. A style it cannot tell is reported as unknown and author-named-twice is not checked.

A macro definition is not a citation: \\newcommand, \\renewcommand, \\providecommand, \\DeclareRobustCommand, \\def (and
\\gdef, \\edef, \\xdef) with their bodies, and \\let, are blanked before anything is read, so the "#1" of
\\newcommand{\\mycite}[1]{\\citep{#1}} is not a key; a citation made through such a macro is still read where it is
used. A key written out in a definition's body (\\newcommand{\\ours}{\\citet{key}}) is listed under definition_keys
and counts as cited, since the macro may be used, but is not reported missing from the bibliography, since it may not
be. A token that starts with a backslash or # is never taken for a key (it is counted under skipped_tokens).

Duplicate keys and malformed entries are verify-refs.py's job and are not repeated here; this uses its parser.
A \\input it cannot find is listed under unresolved_inputs, not counted as an issue (a generated file is often
missing from a clean tree), and the report says so.

Exit: 0 no issue; 1 at least one issue; 2 nothing to reconcile (no FILE could be read, or the
bibliography is unreadable or defines no entry).
"""
import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CITE_CMD = re.compile(r"\\([A-Za-z]*[Cc]ite[A-Za-z]*)\*?((?:\s*\[[^\]]*\]){0,2})\s*\{([^}]*)\}")
# citation commands that print no author name: years, dates, titles, numbers, nothing at all
NO_NAME = re.compile(r"^(?:nocite|[Cc]ite(?:year\w*|date\w*|title\w*|url\w*|num|field|list|text|key))$")
NAME_STYLES = re.compile(r"(?:nat|apalike|apacite[\w-]*|^apa[\w-]*|harv[\w-]*|chicago[\w-]*|^agsm|^dcu|^kluwer|named|"
                         r"authoryear|^spbasic|^agu|^egu|^ametsoc\w*|^jfm|^model[2-5]-names)$", re.I)
NUMBER_STYLES = re.compile(r"^(?:plain|abbrv|unsrt|alpha|ieeetr|IEEEtran\w*|acm|siam|splncs\w*|spmpsci|vancouver|"
                           r"elsarticle-num\w*|model1-num-names|amsplain|amsalpha|nature|naturemag|unsrturl|plainurl|"
                           r"abbrvurl|ACM-Reference-Format)$", re.I)
BIBLATEX_NAMES = re.compile(r"^(?:authoryear|authortitle|apa|chicago-authordate|ext-authoryear|ext-authortitle|mla|"
                            r"verbose|reading)", re.I)
STYLE_DECL = re.compile(
    r"\\documentclass\s*(?:\[(?P<clsopt>[^\]]*)\])?\s*\{(?P<cls>[^}]+)\}"
    r"|\\usepackage\s*(?:\[(?P<pkgopt>[^\]]*)\])?\s*\{(?P<pkg>[^}]+)\}"
    r"|\\(?:setcitestyle|citestyle|biboptions)\s*\{(?P<set>[^}]*)\}"
    r"|\\bibliographystyle\s*\{(?P<bst>[^}]*)\}")
ABBREV = re.compile(r"\b(e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Secs|No|approx|resp|ca)\.", re.I)
SENTENCE_END = re.compile(r"(?<=[.!?])(?:\s+|~)(?=[A-Z\\])|\n\s*\n|\\(?:section|subsection|subsubsection|paragraph|"
                          r"item|caption)\b")
ACCENT = re.compile(r"\\['\"`^~=.uvHckb]\s*\{?([A-Za-z])\}?")
# a surname used as the name of a method: "McNemar's test", "Wilcoxon signed-rank test", "Bonferroni correction"
EPONYM = re.compile(r"\s*(?:'s|\u2019s)?\s+(?:[\w-]+\s+){0,2}?(?:tests?|corrections?|coefficients?|statistics?|"
                    r"distances?|index|indices|algorithms?|criteri(?:on|a)|theorems?|laws?|procedures?|estimators?|"
                    r"transforms?|kappa|alpha|tau|rho|signed-rank|rank-sum|method|methods|scales?|curves?|plots?|"
                    r"distributions?|equations?|bounds?|inequalit(?:y|ies))\b")
AFTER_OPENING_NAME = re.compile(r"\s*(?:et\s+al|and\b|&|\\&|'s|\u2019s|\(|,)")
CITE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]*)\}")
INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
_CS = r"\\(?:[A-Za-z@]+|.)"  # a control sequence: a name, or one non-letter
# the head of a macro definition; a body in braces follows every kind but \let
DEFINITION = re.compile(
    r"\\(?:(?:new|renew|provide)command|DeclareRobustCommand)\*?\s*(?:\{\s*" + _CS + r"\s*\}|" + _CS + r")"
    r"\s*(?:\[[^\]]*\]\s*){0,2}(?=\{)"
    r"|\\[gex]?def\s*" + _CS + r"[^{}]{0,200}?(?=\{)"
    r"|(?P<let>\\let\s*" + _CS + r"\s*=?\s*" + _CS + r")")


def _blank(text, a, b):
    """text with [a, b) replaced by spaces, newlines kept, so offsets and line numbers do not move."""
    return text[:a] + re.sub(r"[^\n]", " ", text[a:b]) + text[b:]


def strip_definitions(text):
    """(text with every macro definition and its body blanked, [the blanked definitions]) (see DEFINITION). A body
    whose braces do not close is left as it is: only the head is blanked."""
    pos, defs = 0, []
    while True:
        m = DEFINITION.search(text, pos)
        if not m:
            return text, defs
        end = m.end()
        if not m.group("let"):
            depth, i = 0, end
            while i < len(text):
                c = text[i]
                if c == "\\":
                    i += 2
                    continue
                depth += c == "{"
                depth -= c == "}"
                i += 1
                if depth == 0:
                    end = i
                    break
        defs.append(text[m.start():end])
        text = _blank(text, m.start(), end)
        pos = end


def is_key(token):
    """A citation key: not empty, and not a macro (\\thekey) or a parameter (#1) left in a citation's braces."""
    return bool(token) and not token.startswith(("\\", "#"))


def _parser():
    spec = importlib.util.spec_from_file_location("verify_refs", HERE / "verify-refs.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = ["verify-refs.py"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod.parse_bibtex


def read_tree(files, root):
    """([(path, text without comments or macro definitions)], [unresolved inputs], [macro definitions]) for the files
    given and everything they input, each file once."""
    out, seen, unresolved, defs = [], set(), [], []
    stack = [Path(f) for f in reversed(files)]
    while stack:
        p = stack.pop()
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            text, found = strip_definitions(COMMENT.sub("", p.read_text(encoding="utf-8", errors="replace")))
            defs += found
        except OSError:
            unresolved.append(str(p))
            continue
        out.append((p, text))
        for m in reversed(list(INPUT.finditer(text))):
            name = m.group(1).strip()
            q = Path(root) / name
            if not q.suffix:
                q = q.with_suffix(".tex")
            if q.exists():
                stack.append(q)
            else:
                unresolved.append(name)
    return out, unresolved, defs


def citation_style(files):
    """(author-year | numeric | unknown, where it was read). The last declaration that settles it wins; the
    bibliography style is read only when none does."""
    decided, bst, natbib = None, None, False
    for path, text in files:
        for m in STYLE_DECL.finditer(text):
            where = f"{path}:{text.count(chr(10), 0, m.start()) + 1}"
            if m.group("cls"):
                cls, opts = m.group("cls").strip(), m.group("clsopt") or ""
                if cls == "acmart":
                    decided = ("numeric", f"{where} (acmart's default)")
                elif cls == "elsarticle" or cls.startswith("cas-"):
                    decided = ("author-year", where) if "authoryear" in opts else ("numeric", f"{where} ({cls}'s default)")
            elif m.group("pkg"):
                opts = m.group("pkgopt") or ""
                for pkg in (x.strip() for x in m.group("pkg").split(",")):
                    if pkg == "natbib":
                        natbib = True
                        if re.search(r"\b(?:numbers|super)\b", opts):
                            decided = ("numeric", where)
                        elif "authoryear" in opts:
                            decided = ("author-year", where)
                    elif pkg == "biblatex":
                        st = re.search(r"\b(?:cite)?style\s*=\s*([\w-]+)", opts)
                        name = st.group(1) if st else "numeric"
                        decided = ("author-year" if BIBLATEX_NAMES.match(name) else "numeric", where)
                    elif pkg in ("apacite", "harvard", "chicago", "achicago"):
                        decided = ("author-year", where)
            elif m.group("set") is not None:
                v = m.group("set")
                if re.search(r"authoryear|acmauthoryear", v):
                    decided = ("author-year", where)
                elif re.search(r"\b(?:numbers|numeric|acmnumeric|super)\b", v):
                    decided = ("numeric", where)
                elif NAME_STYLES.search(v.strip()):
                    decided = ("author-year", where)
            elif m.group("bst"):
                bst = (m.group("bst").strip(), where)
    if decided:
        return decided
    if bst:
        name = Path(bst[0]).name
        if NUMBER_STYLES.match(name) and name != "ACM-Reference-Format":
            return "numeric", f"{bst[1]} ({name})"
        if NAME_STYLES.search(name) and (natbib or not name.endswith("nat")):
            return "author-year", f"{bst[1]} ({name})"
    return "unknown", "nothing in the files read settles it"


def plain_name(s):
    s = ACCENT.sub(r"\1", s).replace("{", "").replace("}", "")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def first_surname(author):
    """The first author's surname, or a braced corporate author whole; None for no author."""
    a = (author or "").strip()
    if not a:
        return None
    depth, cut = 0, len(a)
    for i, c in enumerate(a):
        depth += c == "{"
        depth -= c == "}"
        if depth == 0 and a[i:i + 5].lower() == " and ":
            cut = i
            break
    first = a[:cut].strip()
    if first.startswith("{") and first.endswith("}") and first.count("{") == 1:
        return plain_name(first)
    depth = 0
    for i, c in enumerate(first):
        depth += c == "{"
        depth -= c == "}"
        if depth == 0 and c == ",":
            return plain_name(first[:i]).split()[-1] if plain_name(first[:i]) else None
    words = plain_name(first).split()
    return words[-1] if words else None


def sentence_spans(text):
    """(start, end) of each sentence in a LaTeX text, with abbreviations not read as ends."""
    masked = ABBREV.sub(lambda m: m.group(0).replace(".", "\u2024"), text)
    out, start = [], 0
    for m in SENTENCE_END.finditer(masked):
        out.append((start, m.start()))
        start = m.start() if m.group(0).startswith("\\") else m.end()
    out.append((start, len(text)))
    return [(a, b) for a, b in out if text[a:b].strip()]


def named_twice(files, surnames):
    """author-named-twice issues: a cited key's first author named in the sentence's words and printed again."""
    issues = []
    for path, text in files:
        body = text.split("\\begin{document}", 1)
        offset = len(body[0]) + len("\\begin{document}") if len(body) == 2 else 0
        part = body[-1]
        for a, b in sentence_spans(part):
            sent = part[a:b]
            printing = {}
            for m in CITE_CMD.finditer(sent):
                if NO_NAME.match(m.group(1)):
                    continue
                for k in (x.strip() for x in m.group(3).split(",")):
                    if is_key(k):
                        printing[k] = printing.get(k, 0) + 1
            if not printing:
                continue
            words = plain_name(CITE_CMD.sub(" ", sent))
            opening = re.match(r"\s*(?:\\[A-Za-z]+\*?\s*)*", words).end()
            for k, n in printing.items():
                name = surnames.get(k)
                if not name:
                    continue
                said = False
                for m in re.finditer(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", words):
                    if EPONYM.match(words, m.end()):
                        continue
                    if m.start() > opening or AFTER_OPENING_NAME.match(words, m.end()):
                        said = True
                        break
                if said or n > 1:
                    line = text.count("\n", 0, offset + a + len(sent) - len(sent.lstrip())) + 1
                    issues.append({"kind": "author-named-twice", "severity": "medium", "key": k, "name": name,
                                   "location": f"{path}:{line}", "sentence": " ".join(sent.split())[:300],
                                   "message": f"{name} is named in the sentence and the citation prints the name "
                                              "again; \\citet, or \\citeauthor with \\citeyearpar, says it once."})
    return issues


def main():
    ap = argparse.ArgumentParser(description="Reconcile LaTeX citations with a BibTeX file.")
    ap.add_argument("--bib", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--style", choices=("auto", "author-year", "numeric"), default="auto",
                    help="the citation style the submitted version prints, when a build changes it from the source's")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    try:
        entries = _parser()(Path(a.bib).read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        sys.stderr.write(f"reconcile-cites: cannot read the bibliography {a.bib}: {e}\n")
        return 2
    defined = [e["key"] for e in entries]
    if not defined:
        sys.stderr.write(f"reconcile-cites: {a.bib} defines no entry\n")
        return 2
    files, unresolved, defs = read_tree(a.files, a.root)
    if not files:
        sys.stderr.write("reconcile-cites: none of the files given could be read\n")
        return 2
    first = {}
    everything = False
    skipped = 0
    for path, text in files:
        for m in CITE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            for k in (x.strip() for x in m.group(1).split(",")):
                if k == "*":
                    everything = True
                elif is_key(k):
                    first.setdefault(k, f"{path}:{line}")
                elif k:
                    skipped += 1
    in_defs = sorted({k for d in defs for m in CITE.finditer(d) for k in (x.strip() for x in m.group(1).split(","))
                      if is_key(k) and k != "*"})
    bib = set(defined)
    issues = [{"kind": "cited-not-in-bib", "severity": "high", "key": k, "location": loc,
               "message": "Cited in the text, not defined in the bibliography."}
              for k, loc in sorted(first.items()) if k not in bib]
    if not everything:
        issues += [{"kind": "bib-not-cited", "severity": "medium", "key": k, "location": a.bib,
                    "message": "Defined in the bibliography, cited nowhere in the files read."}
                   for k in sorted(bib - set(first) - set(in_defs))]
    style, style_from = (a.style, "--style") if a.style != "auto" else citation_style(files)
    if style == "author-year":
        surnames = {e["key"]: first_surname(e["fields"].get("author") or e["fields"].get("editor")) for e in entries}
        issues += named_twice(files, surnames)
    payload = {"schema_version": 1, "bib_entries": len(bib), "cited_keys": len(first), "nocite_all": everything,
               "skipped_tokens": skipped, "definition_keys": in_defs,
               "citation_style": style, "citation_style_from": style_from,
               "files_read": [str(p) for p, _ in files], "unresolved_inputs": sorted(set(unresolved)),
               "issues": issues, "issue_count": len(issues)}
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for i in issues:
            print(f"{i['location']}: {i['kind']}: {i['key']}")
        print(f"read {len(files)} file(s); {len(first)} cited key(s), {len(bib)} bibliography entries; "
              f"{len(issues)} issue(s)" + (f"; unresolved inputs: {', '.join(sorted(set(unresolved)))}" if unresolved else ""))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
