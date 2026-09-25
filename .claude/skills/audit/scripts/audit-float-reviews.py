#!/usr/bin/env python3
r"""Say which figures and tables no one has looked at since they last changed.

    python3 audit-float-reviews.py --base-dir <manuscript> --main main.tex [--main supplement.tex ...]
                                   --reviews <reviews.tsv> [--json]
    python3 audit-float-reviews.py ... --render --pdf <x.pdf> --aux <x.aux> [--pdf .. --aux ..]
                                   [--built-from <commit>] --out <dir>

The gap this closes. Every check the loop runs reads text. An overflowing label,
a caption that no longer describes its figure, a figure that contradicts the
numbers beside it: these are seen only by someone who opens the rendered page,
and nothing recorded whether anyone had. This cannot judge a figure. It lists
every float the draft includes with a version fingerprint and says which have
no review of their current version.

A float is a figure, table or longtable environment (spacing inside \begin
allowed, and any environment a \newenvironment defines around one), or a
\captionof{figure|table} paragraph, in the document body of the files
reachable from --main through \input, \include, \subfile and \import. Text in
\iffalse...\fi and comment environments is not the document. Its id is its
first \label, in the environment or in a file it inputs, or <file>#<n>.

Its fingerprint is sha256 over, in order:
  - its environment text as it bears on the page: whole-line comments and the
    text of inline comments dropped (the % itself kept, because it joins
    lines), spaces within a line collapsed, a paragraph break kept;
  - every file it pulls in, by path and content: \input, \import (whose
    directory then leads), \includegraphics (extensions tried in driver order,
    the bare name last), and the data files that \addplot table,
    \pgfplotstableread, \includestandalone, \lstinputlisting, \verbatiminput,
    \csv... and \DTLloaddb read; a .tex file by its text normalised as above, so
    a regenerated table whose only change is a comment keeps its review;
  - the preamble of the main file it belongs to and every file that preamble
    pulls in, because a macro, a length or a font defined there changes how
    the float prints.
A file named by a macro (\input{\dir/x}) cannot be followed and fails the
check rather than being skipped. Not followed: macros defined outside the
preamble, \graphicspath, packages and classes.

The review record is a TSV with a header:

    label<TAB>fingerprint<TAB>reviewer<TAB>date<TAB>verdict<TAB>note

Only rows whose fingerprint is the float's current one count; the last such
row decides. A verdict that starts with "fix" keeps the float open.

  unreviewed    no row for the float's current fingerprint
  review-open   the latest current row says fix
  missing-file  the float pulls in a file that is not there
  unfollowed    an \input that names a macro or a missing file: floats behind
                it are not seen
  stale-row     PROMPT: a row whose label no longer names a float

--render writes the PDF page of each float (pdftoppm) and a REVIEW.md sheet
listing each float's number, page, PNG, fingerprint and caption, with a row to
fill in. The page is the physical one, from the PDF's named destination for
the label's anchor (pdfinfo -dests); without one, the printed page number is
used and the sheet says so. The .aux files are read with the \@input files
they name. With --built-from, each float's fingerprint at that commit is
compared with the current one, and a float whose rendered page shows an older
version is marked; without it the PDF's modification time is compared with the
float's files.

Exit: 1 on unreviewed, review-open, missing-file or unfollowed; 2 when no float
is found, the review record is unreadable, or a --pdf or --aux is missing; 0
otherwise. --render exits 2 when it renders nothing.
"""
import argparse
import hashlib
import json
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE_ENVS = ["figure", "figure*", "table", "table*", "sidewaysfigure", "sidewaysfigure*", "sidewaystable",
             "sidewaystable*", "wrapfigure", "wraptable", "SCfigure", "SCtable", "longtable", "longtable*"]
INPUTS = re.compile(r"\\(?:input|include|subfile)\s*\{([^{}]*)\}|\\input\s+([^\s{}\\%]+)"
                    r"|\\(?:sub)?import\*?\s*\{([^{}]*)\}\s*\{([^{}]+)\}")
OPT = r"\s*(?:\[[^\]]*\]\s*)*"
GRAPHICS = re.compile(r"\\includegraphics\*?" + OPT + r"\{([^{}]+)\}")
DATA = [re.compile(p) for p in (
    r"\\addplot3?\+?" + OPT + r"table" + OPT + r"\{([^{}]+)\}",
    r"\\pgfplotstableread" + OPT + r"\{([^{}]+)\}",
    r"\\includestandalone" + OPT + r"\{([^{}]+)\}",
    r"\\lstinputlisting" + OPT + r"\{([^{}]+)\}",
    r"\\verbatiminput\*?\s*\{([^{}]+)\}",
    r"\\csv(?:autotabular|autolongtable|autobooktabular|autobooklongtable|reader)\*?" + OPT + r"\{([^{}]+)\}",
    r"\\DTLloaddb" + OPT + r"\{[^{}]*\}\s*\{([^{}]+)\}")]
LABEL = re.compile(r"\\label\s*\{([^{}]+)\}")
CAPTIONOF = re.compile(r"\\captionof\s*\{(figure|table)\}")
DOC = re.compile(r"\\begin\s*\{document\}")
NEWENV = re.compile(r"\\(?:re)?newenvironment\s*\{([A-Za-z@]+\*?)\}(?:\s*\[[^\]]*\])*\s*\{[^{}]*?\\begin\s*\{([^{}]+)\}")
BRACED = r"(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*"
NEWLABEL = re.compile(r"\\newlabel\{([^{}]+)\}\{\{(" + BRACED + r")\}\{([^{}]*)\}(?:\{(" + BRACED + r")\}\{([^{}]*)\})?")
AUX_INPUT = re.compile(r"\\@input\{([^{}]+)\}")
IMAGE_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".mps", ".jbig2", ".jb2", "")
KNOWN_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".mps", ".jbig2", ".jb2", ".svg", ".tex", ".tikz", ".pgf"}
COLUMNS = ["label", "fingerprint", "reviewer", "date", "verdict", "note"]
DEPTH = 8


def strip_comment(line, keep_mark=False):
    """The line without its comment; with keep_mark the % stays (it still joins the line to the next)."""
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k = j
        while k > 0 and line[k - 1] == "\\":
            k -= 1
        if (j - k) % 2 == 0:
            return line[:j + 1] if keep_mark else line[:j]
        i = j + 1


def plain(text):
    """Text as it bears on the page: whole-line comments and dead blocks dropped, inline comment text dropped with
    its % kept, spaces collapsed, leading spaces dropped (TeX skips them), runs of blank lines as one."""
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("%")]
    text = "\n".join(strip_comment(l, keep_mark=True) for l in lines)
    text = re.sub(r"\\iffalse\b.*?\\fi\b", "", text, flags=re.S)
    text = re.sub(r"\\begin\s*\{comment\}.*?\\end\s*\{comment\}", "", text, flags=re.S)
    out, blank = [], False
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            if out and not blank:
                out.append("")
            blank = True
            continue
        blank = False
        out.append(line)
    return "\n".join(out).strip("\n")


class Tree:
    """Files as the working tree has them, or as a commit has them (--built-from), relative to the base directory."""

    def __init__(self, base, commit=None):
        self.base, self.commit, self._cache = Path(base), commit, {}

    def read(self, rel):
        if rel not in self._cache:
            if self.commit:
                r = subprocess.run(["git", "-C", str(self.base), "show", f"{self.commit}:./{rel}"],
                                   capture_output=True)
                self._cache[rel] = r.stdout if r.returncode == 0 else None
            else:
                p = self.base / rel
                self._cache[rel] = p.read_bytes() if p.is_file() else None
        return self._cache[rel]

    def text(self, rel):
        b = self.read(rel)
        return None if b is None else b.decode("utf-8", "replace")

    def digest(self, rel):
        """A .tex-like file by its plain text, anything else by its bytes."""
        if posixpath.splitext(rel)[1] in (".tex", ".tikz", ".pgf"):
            return hashlib.sha256(plain(self.text(rel) or "").encode("utf-8")).hexdigest()
        return hashlib.sha256(self.read(rel)).hexdigest()


def resolve(tree, name, here, exts):
    for base in here:
        for ext in exts:
            cand = posixpath.normpath(posixpath.join(base, name + ext) if base else name + ext)
            if not cand.startswith("../") and tree.read(cand) is not None:
                return cand
    return None


def input_refs(text):
    """[(name, import_dir or None)] for \\input, \\include, \\subfile, \\import in the text."""
    out = []
    for a, b, d, f in INPUTS.findall(text):
        if f:
            name, sub = f.strip(), d.strip()
        else:
            name, sub = (a or b).strip(), None
        if name:
            out.append((name if posixpath.splitext(name)[1] else name + ".tex", sub))
    return out


def graphic_exts(name):
    return ("",) if posixpath.splitext(name)[1].lower() in KNOWN_EXT else IMAGE_EXT


def pulled(tree, text, here, acc, missing, unfollowed, depth=0):
    """Files the text pulls in, recursively through .tex: acc [(path, digest)], and names that resolve to nothing or
    are macros."""
    seen = {p for p, _ in acc}

    def add(got):
        if got not in seen:
            seen.add(got)
            acc.append((got, tree.digest(got)))
            return True
        return False
    for name, sub in input_refs(text):
        if "\\" in name:
            unfollowed.append(name)
            continue
        child_here = ([posixpath.normpath(posixpath.join(h, sub)) if h else posixpath.normpath(sub) for h in here]
                      + here) if sub else here
        got = resolve(tree, posixpath.join(sub, name) if sub else name, here, ("",)) if sub else \
            resolve(tree, name, here, ("",))
        if not got:
            missing.append(name)
        elif add(got) and depth < DEPTH:
            # \input is found from the main file's directory first, as LaTeX finds it; \import puts its own first
            pulled(tree, plain(tree.text(got) or ""), child_here if sub else here + [posixpath.dirname(got)],
                   acc, missing, unfollowed, depth + 1)
    for name in GRAPHICS.findall(text):
        name = name.strip()
        if "\\" in name:
            unfollowed.append(name)
            continue
        got = resolve(tree, name, here, graphic_exts(name))
        if not got:
            missing.append(name)
        else:
            add(got)
    for rx in DATA:
        for name in rx.findall(text):
            name = name.strip()
            if name.startswith("\\"):
                continue  # a table held in a macro: the file that filled it is read where the macro was defined
            got = resolve(tree, name, here, ("", ".tex"))
            if not got:
                missing.append(name)
            else:
                add(got)
    return acc


def fingerprint(body, files, preamble):
    h = hashlib.sha256(body.encode("utf-8"))
    for path, digest in files:
        h.update(("\0" + path + "\0" + digest).encode())
    h.update(("\0preamble\0" + preamble).encode())
    return h.hexdigest()[:16]


def reach(tree, main):
    """({rel: here} body files in order met, preamble digest, custom float environments, problems) for one main."""
    main = posixpath.normpath(main)
    root = posixpath.dirname(main)
    text = plain(tree.text(main) or "")
    m = DOC.search(text)
    pre_text, body_text = (text[:m.start()], text[m.end():]) if m else ("", text)
    pre_files, pre_missing, pre_unf = [], [], []
    pulled(tree, pre_text, [root, ""], pre_files, pre_missing, pre_unf)
    pre_digest = hashlib.sha256(pre_text.encode("utf-8")).hexdigest() + "".join(d for _, d in pre_files)
    envs = set()
    for src in [pre_text] + [plain(tree.text(p) or "") for p, _ in pre_files if p.endswith(".tex")]:
        for name, inner in NEWENV.findall(src):
            if inner in BASE_ENVS:
                envs.add(name)
    body, problems = {main: ([root, ""], body_text)}, []

    def walk(rel, here, depth):
        for name, sub in input_refs(body[rel][1]):
            if "\\" in name:
                problems.append({"kind": "unfollowed", "float": rel, "detail": f"\\input{{{name}}} names a macro: "
                                 "floats behind it are not seen"})
                continue
            got = resolve(tree, posixpath.join(sub, name) if sub else name, here, ("",))
            if not got:
                problems.append({"kind": "unfollowed", "float": rel, "detail": f"{name} is not there"})
                continue
            if got in body or depth >= DEPTH:
                continue
            child = ([posixpath.normpath(posixpath.join(h, sub)) if h else posixpath.normpath(sub) for h in here]
                     + here) if sub else [root, posixpath.dirname(got), ""]
            body[got] = (child, plain(tree.text(got) or ""))
            walk(got, child, depth + 1)
    walk(main, [root, ""], 0)
    return body, pre_digest, envs, problems


def spans(text, envs):
    """[(env, start, end)] of the float environments in the text, outermost only."""
    names = sorted(set(BASE_ENVS) | envs, key=len, reverse=True)
    begin = re.compile(r"\\begin\s*\{(" + "|".join(re.escape(n) for n in names) + r")\}")
    out, pos = [], 0
    while True:
        m = begin.search(text, pos)
        if not m:
            return out
        end = re.compile(r"\\end\s*\{" + re.escape(m.group(1)) + r"\}").search(text, m.end())
        stop = end.end() if end else len(text)
        out.append((m.group(1), m.start(), stop))
        pos = stop


def caption_of(body):
    m = re.search(r"\\caption(?:of\s*\{[^{}]*\})?\*?\s*(?:\[[^\]]*\])?\s*\{", body)
    if not m:
        return ""
    depth, j, i = 0, m.end() - 1, m.end() - 1
    while j < len(body):
        c = body[j]
        if c == "\\":
            j += 2
            continue
        depth += c == "{"
        depth -= c == "}"
        if depth == 0:
            break
        j += 1
    return re.sub(r"%\s*", "", re.sub(r"\s+", " ", body[i + 1:j])).strip()


def collect(tree, mains):
    """(floats, problems). Mains with a document environment go first, so a section file listed before its main
    still takes that main's preamble."""
    order = sorted(mains, key=lambda m: 0 if DOC.search(plain(tree.text(posixpath.normpath(m)) or "")) else 1)
    owner, problems = {}, []
    for m in order:
        body, pre, envs, probs = reach(tree, m)
        problems += probs
        for rel, (here, text) in body.items():
            owner.setdefault(rel, (here, text, pre, envs))
    floats = []
    for rel, (here, text, pre, envs) in owner.items():
        found = spans(text, envs)
        pieces = [(env, text[a:b]) for env, a, b in found]
        inside = lambda i: any(a <= i < b for _, a, b in found)
        for k, m in enumerate(CAPTIONOF.finditer(text), 1):
            if not inside(m.start()):
                # its paragraph, but never reaching into a float environment beside it
                a = text.rfind("\n\n", 0, m.start())
                a = max([a + 2 if a >= 0 else 0] + [e for _, _, e in found if e <= m.start()])
                b = text.find("\n\n", m.end())
                b = min([b if b >= 0 else len(text)] + [s for _, s, _ in found if s >= m.end()])
                pieces.append(("captionof " + m.group(1), text[a:b], m.start() - a))
        for n, piece in enumerate(pieces, 1):
            env, body = piece[0], piece[1]
            acc, missing, unfollowed = [], [], []
            pulled(tree, body, here, acc, missing, unfollowed)
            # a \captionof names the label that follows it
            labels = LABEL.findall(body[piece[2]:]) if len(piece) > 2 else []
            labels = labels or LABEL.findall(body)
            if not labels:
                for p, _ in acc:
                    if p.endswith(".tex"):
                        labels = LABEL.findall(plain(tree.text(p) or ""))
                        if labels:
                            break
            floats.append({"id": labels[0] if labels else f"{rel}#{n}", "env": env, "file": rel, "labels": labels,
                           "caption": caption_of(body), "pulled": [p for p, _ in acc],
                           "missing": missing + [f"{u} (a macro)" for u in unfollowed],
                           "fingerprint": fingerprint(body, acc, pre)})
    return floats, problems


def read_reviews(path):
    """[row] in file order, or raises ValueError. A missing file is no review at all."""
    if not path.is_file():
        return []
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    if header[:len(COLUMNS)] != COLUMNS:
        raise ValueError(f"expected columns {COLUMNS}, found {header}")
    rows = []
    for n, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) < 5 or not parts[0].strip() or not parts[1].strip() or not parts[4].strip():
            raise ValueError(f"line {n}: label, fingerprint and verdict are required")
        row = dict(zip(COLUMNS, parts + [""] * (len(COLUMNS) - len(parts))))
        row["line"] = n
        rows.append(row)
    return rows


def check(a):
    base = Path(a.base_dir)
    tree = Tree(base)
    floats, problems = collect(tree, a.main)
    if not floats:
        print("NOTHING CHECKED: no figure or table environment is reachable from --main. This is not a pass.",
              file=sys.stderr)
        return 2, None
    rpath = Path(a.reviews) if Path(a.reviews).is_absolute() else base / a.reviews
    try:
        rows = read_reviews(rpath)
    except (OSError, ValueError) as e:
        print(f"REVIEWS: cannot read {rpath}: {e}", file=sys.stderr)
        return 2, None
    findings = list(problems)
    ids = {f["id"] for f in floats}
    for f in floats:
        current = [r for r in rows if r["label"].strip() == f["id"] and r["fingerprint"].strip() == f["fingerprint"]]
        f["review"] = ({k: current[-1][k] for k in ("reviewer", "date", "verdict", "note")} if current else None)
        older = [r for r in rows if r["label"].strip() == f["id"] and r["fingerprint"].strip() != f["fingerprint"]]
        if f["missing"]:
            findings.append({"kind": "missing-file", "float": f["id"], "detail": "pulls in " + ", ".join(f["missing"])})
        if not current:
            f["status"] = "unreviewed"
            findings.append({"kind": "unreviewed", "float": f["id"],
                             "detail": (f"reviewed at an older version ({older[-1]['fingerprint'].strip()}); changed since"
                                        if older else "no review")})
        elif current[-1]["verdict"].strip().lower().startswith("fix"):
            f["status"] = "open"
            findings.append({"kind": "review-open", "float": f["id"],
                             "detail": f"{current[-1]['reviewer']}: {current[-1]['note'][:160]}"})
        else:
            f["status"] = "reviewed"
    for r in rows:
        if r["label"].strip() not in ids:
            findings.append({"kind": "stale-row", "prompt": True, "float": r["label"].strip(),
                             "detail": f"line {r['line']} names no float in the draft"})
    hard = [x for x in findings if not x.get("prompt")]
    n_rev = sum(1 for f in floats if f["status"] == "reviewed")
    n_open = sum(1 for f in floats if f["status"] == "open")
    parts = [f"图表 {len(floats)} 个：看过这一版 {n_rev}"]
    if n_open:
        parts.append(f"看过但待改 {n_open}")
    unrev = [f["id"] for f in floats if f["status"] == "unreviewed"]
    if unrev:
        parts.append(f"没人看过这一版 {len(unrev)}（{'、'.join(unrev[:3])}{' 等' if len(unrev) > 3 else ''}）")
    miss = sum(1 for x in findings if x["kind"] == "missing-file")
    if miss:
        parts.append(f"引用的文件找不到 {miss}")
    unf = sum(1 for x in findings if x["kind"] == "unfollowed")
    if unf:
        parts.append(f"跟不进去的 \\input {unf} 处")
    reviewers = sorted({f["review"]["reviewer"] for f in floats if f.get("review")})
    payload = {"schema_version": 2, "base": str(base), "reviews": str(rpath),
               "summary_zh": "；".join(parts),
               "floats": [{k: f[k] for k in ("id", "env", "file", "labels", "caption", "fingerprint", "pulled",
                                             "missing", "status", "review")} for f in floats],
               "reviewers": reviewers, "findings": findings, "hard_finding_count": len(hard),
               "limits": "whether a figure is right is the reviewer's call; this records who looked at which "
                         "version. Not followed: macros defined outside the preamble, \\graphicspath, packages."}
    return (1 if hard else 0), payload


def aux_labels(pdf, aux, out, seen=None):
    """{label: [(pdf, number, printed page, anchor)]} from an .aux and the .aux files it \\@input's."""
    seen = set() if seen is None else seen
    p = Path(aux).resolve()
    if p in seen or not p.is_file():
        return out
    seen.add(p)
    text = p.read_text(encoding="utf-8", errors="replace")
    for label, number, page, _title, anchor in NEWLABEL.findall(text):
        out.setdefault(label, []).append((pdf, re.sub(r"[{}]|\\relax\s*", "", number).strip(), page.strip(),
                                          (anchor or "").strip()))
    for sub in AUX_INPUT.findall(text):
        aux_labels(pdf, p.parent / sub, out, seen)
    return out


def dests(pdf):
    """{named destination: physical page} from pdfinfo, or {} when it is not available."""
    if not shutil.which("pdfinfo"):
        return {}
    r = subprocess.run(["pdfinfo", "-dests", pdf], capture_output=True, text=True, errors="replace")
    out = {}
    for line in (r.stdout or "").splitlines():
        m = re.match(r"\s*(\d+)\s+\[.*\]\s+\"(.*)\"\s*$", line)
        if m:
            out.setdefault(m.group(2), int(m.group(1)))
    return out


def render(a, payload):
    if len(a.pdf) != len(a.aux) or not a.pdf:
        print("RENDER: give --pdf and --aux in pairs", file=sys.stderr)
        return 2
    gone = [p for p in a.pdf + a.aux if not Path(p).is_file()]
    if gone:
        print("RENDER: not found: " + ", ".join(gone), file=sys.stderr)
        return 2
    if not shutil.which("pdftoppm"):
        print("RENDER: pdftoppm is not installed", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    labels = {}
    for pdf, aux in zip(a.pdf, a.aux):
        aux_labels(pdf, aux, labels)
    named = {pdf: dests(pdf) for pdf in a.pdf}
    stems = [Path(p).stem for p in a.pdf]
    name_of = {p: (Path(p).stem if stems.count(Path(p).stem) == 1 else f"{k + 1}-{Path(p).stem}")
               for k, p in enumerate(a.pdf)}
    then = None
    if a.built_from:
        then = {f["id"]: f["fingerprint"] for f in collect(Tree(a.base_dir, a.built_from), a.main)[0]}
    rendered, rows = {}, []
    for f in payload["floats"]:
        hits = [h for l in f["labels"] for h in labels.get(l, [])]
        if not hits:
            rows.append((f, None, None, None, ["not in any .aux given: not rendered"]))
            continue
        pdf, number, printed, anchor = hits[0]
        notes = []
        if len({h[0] for h in hits}) > 1:
            notes.append(f"the label is in {len({h[0] for h in hits})} of the .aux files given; rendered from {pdf}")
        page = named[pdf].get(anchor) if anchor else None
        if page is None:
            page = int(printed) if printed.isdigit() else None
            notes.append("no named destination for the label: the printed page number was used as the PDF page")
        if page is None:
            rows.append((f, number, printed, None, notes + ["no usable page"]))
            continue
        key = (pdf, page)
        if key not in rendered:
            stem = f"{name_of[pdf]}-p{page:03d}"
            r = subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", str(page), "-l", str(page), "-png", "-singlefile",
                                pdf, str(out / stem)], capture_output=True, text=True)
            rendered[key] = (out / (stem + ".png")) if r.returncode == 0 else None
        png = rendered[key]
        if png is None:
            notes.append("pdftoppm failed")
        elif then is not None:
            if then.get(f["id"]) != f["fingerprint"]:
                notes.append(f"PDF built from {a.built_from}, where this float was a different version: "
                             "rebuild before reviewing")
        else:
            files = [Path(a.base_dir) / f["file"]] + [Path(a.base_dir) / p for p in f["pulled"]]
            newest = max((p.stat().st_mtime for p in files if p.is_file()), default=0)
            if newest > Path(pdf).stat().st_mtime:
                notes.append("a file of this float is newer than the PDF: rebuild before reviewing")
        rows.append((f, number, page, png, notes))
    lines = ["# Figure and table review sheet", "",
             f"Built from: {a.built_from or 'unknown (mtime compared)'}. PDFs: "
             + ", ".join(f"{p} (sha256 {hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]})" for p in a.pdf), "",
             "Look at each page; then add a row to the review record (verdict ok, or fix with a note).", ""]
    for f, number, page, png, notes in rows:
        kind = "Figure" if "figure" in f["env"].lower() else "Table"
        lines += [f"## {kind} {number or '?'} · `{f['id']}` · PDF page {page or '-'}", "",
                  f"- PNG: {png.name if png else '-'}", f"- fingerprint: `{f['fingerprint']}` · now: {f['status']}",
                  f"- caption: {f['caption'][:400] or '(none)'}"]
        lines += [f"- **{n}**" for n in notes]
        lines += ["", "```", f"{f['id']}\t{f['fingerprint']}\t<reviewer>\t<date>\t<ok|fix>\t<note>", "```", ""]
    (out / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    n = sum(1 for *_, png, _ in rows if png)
    print(f"rendered {len(set(p for *_, p, _ in rows if p))} page(s) for {n} of {len(rows)} float(s) -> "
          f"{out / 'REVIEW.md'}")
    for f, number, page, png, notes in rows:
        for note in notes:
            print(f"  {f['id']}: {note}")
    return 0 if n else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--main", action="append", required=True)
    ap.add_argument("--reviews", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--pdf", action="append", default=[])
    ap.add_argument("--aux", action="append", default=[])
    ap.add_argument("--built-from")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    code, payload = check(a)
    if payload is None:
        return code
    if a.render:
        if not a.out:
            print("RENDER: --out is required", file=sys.stderr)
            return 2
        return render(a, payload)
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["summary_zh"])
        for x in payload["findings"]:
            print(f"  {x['kind']}{' (prompt)' if x.get('prompt') else ''}  {x['float']}: {x['detail']}")
        print(f"\n{payload['limits']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
