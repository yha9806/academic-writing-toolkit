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
\captionof{figure|table} with the center, minipage or flush environment
around it (its paragraph when there is none), in the document body of the
files reachable from --main through \input, \include, \subfile and \import.
Not the document: comment and filecontents environments, and a block opened
by \iffalse at the start of a line up to its matching \fi (TeX's conditionals
and those a \newif declares are counted; with no matching \fi nothing is
dropped). Its id is its first \label, in the environment or in a file it
inputs, or <file>#<n>.

The text is read as TeX reads it: whole-line comments and the text of inline
comments dropped, a line break a space, a line ending in % joined to the next
with nothing, a blank line a paragraph break. So re-wrapping a caption keeps a
review, and a removed % or a new blank line between two panels reopens it.

A float's fingerprint is sha256 over its text and every file it pulls in, by
path and content: \input, \import (whose directory then leads),
\includegraphics and \includesvg (the directories of \graphicspath tried
too; extensions in driver order, the bare name last), and the data files that
\addplot table (a file, or a table \pgfplotstableread filled anywhere in the
draft), \pgfplotstableread, \includestandalone, \lstinputlisting,
\verbatiminput, \csv... and \DTLloaddb read; inline data is not a file. A .tex
file counts by its text read as above, so a regenerated table whose only
change is a comment keeps its review.

Each main file's preamble, with every file it pulls in, is reviewed as one item
of its own (label preamble:<main>): a macro, a length or a font there can
change how every float prints, and one row to look again says so without
reopening every float at once. A file named by a macro (\input{\dir/x}), or a
missing one, in the preamble or the body fails the check rather than being
skipped. Not followed: what a macro expands to (an image named inside a
\newcommand), packages and classes.

The review record is a TSV with a header:

    label<TAB>fingerprint<TAB>reviewer<TAB>date<TAB>verdict<TAB>note

Only rows whose fingerprint is the item's current one count; the last such row
decides. A verdict that starts with "fix" keeps the item open.

  unreviewed    no row for the float's (or preamble's) current fingerprint
  review-open   the latest current row says fix
  missing-file  the float pulls in a file that is not there
  unfollowed    an \input that names a macro or a missing file: what is behind
                it is not seen
  stale-row     PROMPT: a row whose label names nothing in the draft

--render writes the PDF page of each float (pdftoppm) and a REVIEW.md sheet
listing each float's number, page, PNG, fingerprint and caption, with a row to
fill in, and a row for each preamble. The page is the physical one, from the
PDF's named destination for the label's anchor (pdfinfo -dests); without one,
the printed page number is used and the sheet says so. The .aux files are read
with the \@input files they name. With --built-from, each item's fingerprint
at that commit is compared with the current one, and one whose rendered page
shows an older version is marked; without it the PDF's modification time is
compared with the float's files.

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
GRAPHICS = re.compile(r"\\include(?:graphics|svg)\*?" + OPT + r"\{([^{}]+)\}")
ADDPLOT = re.compile(r"\\addplot3?\+?" + OPT + r"table" + OPT + r"\{([^{}]+)\}")
DATA = [ADDPLOT] + [re.compile(p) for p in (
    r"\\pgfplotstableread" + OPT + r"\{([^{}]+)\}",
    r"\\includestandalone" + OPT + r"\{([^{}]+)\}",
    r"\\lstinputlisting" + OPT + r"\{([^{}]+)\}",
    r"\\verbatiminput\*?\s*\{([^{}]+)\}",
    r"\\csv(?:autotabular|autolongtable|autobooktabular|autobooklongtable|reader)\*?" + OPT + r"\{([^{}]+)\}",
    r"\\DTLloaddb" + OPT + r"\{[^{}]*\}\s*\{([^{}]+)\}")]
TABLEREAD = re.compile(r"\\pgfplotstableread" + OPT + r"\{([^{}]+)\}\s*\{?\s*\\([A-Za-z@]+)")
GPATH = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\})+)\s*\}")
LABEL = re.compile(r"\\label\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
CAPTIONOF = re.compile(r"\\captionof\s*\{(figure|table)\}")
DOC = re.compile(r"\\begin\s*\{document\}")
NEWENV = re.compile(r"\\(?:re)?newenvironment\s*\{([A-Za-z@]+\*?)\}(?:\s*\[[^\]]*\])*\s*\{[^{}]*?\\begin\s*\{([^{}]+)\}")
NEWIF = re.compile(r"\\newif\s*\\(if[A-Za-z@]+)")
PRIMITIVE_IFS = {"if", "ifcat", "ifnum", "ifdim", "ifodd", "ifvmode", "ifhmode", "ifmmode", "ifinner", "ifvoid",
                 "ifhbox", "ifvbox", "ifx", "ifeof", "iftrue", "iffalse", "ifcase", "ifdefined", "ifcsname",
                 "iffontchar", "ifincsname", "ifpdfprimitive", "ifpdfabsnum", "ifpdfabsdim", "ifprimitive"}
WRAPPERS = r"center|minipage|flushleft|flushright"
VERBATIM = re.compile(r"\\begin\s*\{(verbatim\*?|Verbatim\*?|BVerbatim|LVerbatim|lstlisting|minted|alltt)\}(.*?)"
                      r"\\end\s*\{\1\}", re.S)
INLINE_DATA = re.compile(r"(\\addplot3?\+?" + OPT + r"table" + OPT + r"|\\pgfplotstableread" + OPT + r")\{([^{}]*\n[^{}]*)\}")
FILECONTENTS = re.compile(r"\\begin\s*\{(filecontents\*?)\}(.*?)\\end\s*\{\1\}", re.S)
BRACED = r"(?:[^{}]|\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})*"
NEWLABEL = re.compile(r"\\newlabel\{([^{}]+)\}\{\{(" + BRACED + r")\}\{([^{}]*)\}(?:\{(" + BRACED + r")\}\{([^{}]*)\})?")
AUX_INPUT = re.compile(r"\\@input\{([^{}]+)\}")
IMAGE_EXT = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".mps", ".jbig2", ".jb2", ".svg", "")
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


def strip_dead(text):
    """Drop what TeX never typesets: comment and filecontents environments, and each \\iffalse that starts a line
    through its matching \\fi. Conditionals counted are TeX's and the ones a \\newif declares; a \\iffalse with no
    matching \\fi is left alone (a dead float counted is noise, a live one dropped is a false pass)."""
    text = re.sub(r"\\begin\s*\{comment\}.*?\\end\s*\{comment\}", "", text, flags=re.S)
    ifs = PRIMITIVE_IFS | set(NEWIF.findall(text))
    opener = re.compile(r"(?m)^[ \t]*\\iffalse(?![A-Za-z@])")
    token = re.compile(r"(\\newif\s*)?\\(if[A-Za-z@]*|fi|else)(?![A-Za-z@])")
    out, i = [], 0
    while True:
        m = opener.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        depth, j, closed = 1, m.end(), False
        while True:
            t = token.search(text, j)
            if not t:
                break
            j = t.end()
            if t.group(1):
                continue  # \newif\ifname declares a conditional; it opens nothing
            if t.group(2) == "fi":
                depth -= 1
                if depth == 0:
                    closed = True
                    break
            elif t.group(2) == "else" and depth == 1:
                break  # an \else makes part of the block live: keep all of it rather than guess which part
            elif t.group(2) in ifs:
                depth += 1
        if closed:
            out.append(text[i:m.start()])
        else:
            out.append(text[i:m.end()])
            j = m.end()
        i = j


def _sealed(kind, raw):
    return f"\\sealed{kind}{{{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}}}"


def seal(text):
    """Text TeX does not read as prose is kept as written: verbatim-like environments and inline plot data (a line
    break separates rows there, a % is a character) and filecontents blocks (their content is a file) are each
    replaced by a token carrying the hash of their raw text, so any change to them counts and none of it is read as
    document text."""
    text = VERBATIM.sub(lambda m: _sealed("verbatim", m.group(0)), text)
    text = FILECONTENTS.sub(lambda m: _sealed("filecontents", m.group(0)), text)
    return INLINE_DATA.sub(lambda m: m.group(1) + "{" + _sealed("data", m.group(2)) + "}", text)


def plain(text):
    """Text as TeX reads it: whole-line comments and inline comment text dropped, dead blocks dropped, a line break a
    space, a line ending in % joined to the next with nothing, spaces collapsed, one paragraph per line with a blank
    line between. Verbatim, inline plot data and filecontents are sealed first (see seal)."""
    text = seal(text)
    lines = [strip_comment(l, keep_mark=True) for l in text.splitlines() if not l.lstrip().startswith("%")]
    text = strip_dead("\n".join(lines))
    paras, cur = [], []
    for line in text.splitlines():
        s = re.sub(r"[ \t]+", " ", line).strip()
        if s:
            cur.append(s)
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)
    out = []
    for p in paras:
        acc = ""
        for s in p:
            if acc.endswith("%") and not acc.endswith("\\%"):
                acc = acc[:-1] + s
            else:
                acc = f"{acc} {s}" if acc else s
        out.append(acc)
    return "\n\n".join(out)


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
        """A .tex-like file by its text read as TeX reads it, anything else by its bytes."""
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


_TEX_TREE = {}


def in_tex_tree(name):
    """True when the TeX distribution provides the file (\\input{glyphtounicode}): not the project's to track."""
    if name not in _TEX_TREE:
        k = shutil.which("kpsewhich")
        _TEX_TREE[name] = bool(k) and subprocess.run([k, name], capture_output=True, text=True).returncode == 0
    return _TEX_TREE[name]


def graphic_exts(name):
    return ("",) if posixpath.splitext(name)[1].lower() in KNOWN_EXT else IMAGE_EXT


class Ctx:
    """What every float of one draft shares: \\graphicspath directories and the files \\pgfplotstableread put in a
    table macro."""

    def __init__(self, gpath=(), tables=None):
        self.gpath, self.tables = list(gpath), dict(tables or {})


def pulled(tree, text, here, acc, missing, unfollowed, ctx, depth=0):
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
        if "#" in name:
            continue  # a macro's parameter: the file is named where the macro is used, which is not followed
        if "\\" in name:
            unfollowed.append(name)
            continue
        got = resolve(tree, posixpath.join(sub, name) if sub else name, here, ("",))
        if not got:
            if not in_tex_tree(name):
                missing.append(name)
        elif add(got) and depth < DEPTH:
            # \input is found from the main file's directory first, as LaTeX finds it; \import puts its own first
            child = ([posixpath.normpath(posixpath.join(h, sub)) if h else posixpath.normpath(sub) for h in here]
                     + here) if sub else here + [posixpath.dirname(got)]
            pulled(tree, plain(tree.text(got) or ""), child, acc, missing, unfollowed, ctx, depth + 1)
    for name in GRAPHICS.findall(text):
        name = name.strip()
        if "#" in name:
            continue
        if "\\" in name:
            unfollowed.append(name)
            continue
        got = resolve(tree, name, here + [posixpath.join(here[0], g) if here[0] else g for g in ctx.gpath],
                      graphic_exts(name))
        if not got:
            missing.append(name)
        else:
            add(got)
    for rx in DATA:
        for name in rx.findall(text):
            name = name.strip()
            if name.startswith("\\"):
                # a table held in a macro: the file \pgfplotstableread filled it from, wherever that was
                src = ctx.tables.get(name[1:]) if rx is ADDPLOT else None
                if src:
                    got = resolve(tree, src, here, ("",))
                    if got:
                        add(got)
                    else:
                        missing.append(src)
                continue
            got = resolve(tree, name, here, ("", ".tex"))
            if got:
                add(got)
            elif not re.search(r"\s", name):
                missing.append(name)  # a name with spaces or line breaks in it is inline data, not a file
    return acc


def fingerprint(body, files):
    h = hashlib.sha256(body.encode("utf-8"))
    for path, digest in files:
        h.update(("\0" + path + "\0" + digest).encode())
    return h.hexdigest()[:16]


def reach(tree, main):
    """(body files {rel: (here, text)}, preamble item or None, custom float environments, ctx, problems) for one
    main file."""
    main = posixpath.normpath(main)
    root = posixpath.dirname(main)
    text = plain(tree.text(main) or "")
    m = DOC.search(text)
    pre_text, body_text = (text[:m.start()], text[m.end():]) if m else ("", text)
    pre_files, pre_missing, pre_unf, problems = [], [], [], []
    ctx = Ctx()
    pulled(tree, pre_text, [root, ""], pre_files, pre_missing, pre_unf, ctx)
    for name in pre_unf:
        problems.append({"kind": "unfollowed", "float": f"preamble:{main}",
                         "detail": f"{name} names a macro: what it pulls in is not seen"})
    for name in pre_missing:
        problems.append({"kind": "unfollowed", "float": f"preamble:{main}", "detail": f"{name} is not there"})
    pre_sources = [pre_text] + [plain(tree.text(p) or "") for p, _ in pre_files if p.endswith(".tex")]
    ctx.gpath = [d for src in pre_sources for group in GPATH.findall(src) for d in re.findall(r"\{([^{}]*)\}", group)]
    envs = {name for src in pre_sources for name, inner in NEWENV.findall(src) if inner in BASE_ENVS}
    preamble = None
    if m:
        preamble = {"id": f"preamble:{main}", "env": "preamble", "file": main, "labels": [], "caption": "",
                    "pulled": [p for p, _ in pre_files], "missing": [],
                    "fingerprint": fingerprint(pre_text, pre_files)}
    body = {main: ([root, ""], body_text)}

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
    for src in pre_sources + [t for _, t in body.values()]:
        for f, macro in TABLEREAD.findall(src):
            if not re.search(r"\s", f.strip()) and "sealed" not in f:
                ctx.tables.setdefault(macro, f.strip())
    return body, preamble, envs, ctx, problems


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


def around(text, pos, found):
    """The span of a \\captionof: the outermost center, minipage or flush environment around it (an image often sits
    in a sibling minipage of the one holding the caption), or else its paragraph; never reaching into a float
    environment beside it."""
    for m in re.finditer(r"\\begin\s*\{(" + WRAPPERS + r")\}", text[:pos]):
        depth, j = 0, m.end()
        rx = re.compile(r"\\(begin|end)\s*\{" + m.group(1) + r"\}")
        while True:
            t = rx.search(text, j)
            if not t:
                break
            j = t.end()
            if t.group(1) == "begin":
                depth += 1
            elif depth:
                depth -= 1
            else:
                break
        if t and t.group(1) == "end" and t.start() >= pos:
            return m.start(), t.end()
    a = text.rfind("\n\n", 0, pos)
    a = max([a + 2 if a >= 0 else 0] + [e for _, _, e in found if e <= pos])
    b = text.find("\n\n", pos)
    b = min([b if b >= 0 else len(text)] + [s for _, s, _ in found if s >= pos])
    return a, b


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
    return re.sub(r"\s+", " ", body[i + 1:j]).strip()


def collect(tree, mains):
    """(floats, preambles, problems). Mains with a document environment go first, so a section file listed before
    its main still belongs to that main."""
    order = sorted(mains, key=lambda m: 0 if DOC.search(plain(tree.text(posixpath.normpath(m)) or "")) else 1)
    owner, problems, preambles = {}, [], []
    for m in order:
        body, pre, envs, ctx, probs = reach(tree, m)
        problems += probs
        if pre and pre["id"] not in [p["id"] for p in preambles]:
            preambles.append(pre)
        for rel, (here, text) in body.items():
            owner.setdefault(rel, (here, text, envs, ctx))
    floats = []
    for rel, (here, text, envs, ctx) in owner.items():
        found = spans(text, envs)
        pieces = [(env, text[a:b], 0) for env, a, b in found]
        for m in CAPTIONOF.finditer(text):
            if not any(a <= m.start() < b for _, a, b in found):
                a, b = around(text, m.start(), found)
                pieces.append(("captionof " + m.group(1), text[a:b], m.start() - a))
        for n, (env, body, at) in enumerate(pieces, 1):
            acc, missing, unfollowed = [], [], []
            pulled(tree, body, here, acc, missing, unfollowed, ctx)
            # a \captionof names the label that follows it
            labels = LABEL.findall(body[at:]) or LABEL.findall(body)
            if not labels:
                for p, _ in acc:
                    if p.endswith(".tex"):
                        labels = LABEL.findall(plain(tree.text(p) or ""))
                        if labels:
                            break
            floats.append({"id": labels[0] if labels else f"{rel}#{n}", "env": env, "file": rel, "labels": labels,
                           "caption": caption_of(body), "pulled": [p for p, _ in acc],
                           "missing": missing + [f"{u} (a macro)" for u in unfollowed],
                           "fingerprint": fingerprint(body, acc)})
    return floats, preambles, problems


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


def judge(item, rows, findings):
    current = [r for r in rows if r["label"].strip() == item["id"] and r["fingerprint"].strip() == item["fingerprint"]]
    item["review"] = ({k: current[-1][k] for k in ("reviewer", "date", "verdict", "note")} if current else None)
    older = [r for r in rows if r["label"].strip() == item["id"] and r["fingerprint"].strip() != item["fingerprint"]]
    if item["missing"]:
        findings.append({"kind": "missing-file", "float": item["id"], "detail": "pulls in " + ", ".join(item["missing"])})
    if not current:
        item["status"] = "unreviewed"
        what = ("the preamble changed since; look again at the pages its macros, lengths or fonts reach"
                if item["env"] == "preamble" else "changed since")
        findings.append({"kind": "unreviewed", "float": item["id"],
                         "detail": (f"reviewed at an older version ({older[-1]['fingerprint'].strip()}); {what}"
                                    if older else "no review")})
    elif current[-1]["verdict"].strip().lower().startswith("fix"):
        item["status"] = "open"
        findings.append({"kind": "review-open", "float": item["id"],
                         "detail": f"{current[-1]['reviewer']}: {current[-1]['note'][:160]}"})
    else:
        item["status"] = "reviewed"


def check(a):
    base = Path(a.base_dir)
    tree = Tree(base)
    floats, preambles, problems = collect(tree, a.main)
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
    for item in floats + preambles:
        judge(item, rows, findings)
    ids = {f["id"] for f in floats + preambles}
    for r in rows:
        if r["label"].strip() not in ids:
            findings.append({"kind": "stale-row", "prompt": True, "float": r["label"].strip(),
                             "detail": f"line {r['line']} names nothing in the draft"})
    hard = [x for x in findings if not x.get("prompt")]
    n_rev = sum(1 for f in floats if f["status"] == "reviewed")
    n_open = sum(1 for f in floats if f["status"] == "open")
    parts = [f"图表 {len(floats)} 个：看过这一版 {n_rev}"]
    if n_open:
        parts.append(f"看过但待改 {n_open}")
    unrev = [f["id"] for f in floats if f["status"] == "unreviewed"]
    if unrev:
        parts.append(f"没人看过这一版 {len(unrev)}（{'、'.join(unrev[:3])}{' 等' if len(unrev) > 3 else ''}）")
    pre_unrev = sum(1 for p in preambles if p["status"] == "unreviewed")
    pre_open = sum(1 for p in preambles if p["status"] == "open")
    if pre_unrev:
        parts.append(f"导言区 {pre_unrev} 份没人看过这一版")
    if pre_open:
        parts.append(f"导言区 {pre_open} 份待改")
    miss = sum(1 for x in findings if x["kind"] == "missing-file")
    if miss:
        parts.append(f"引用的文件找不到 {miss}")
    unf = sum(1 for x in findings if x["kind"] == "unfollowed")
    if unf:
        parts.append(f"跟不进去的引入 {unf} 处")
    keys = ("id", "env", "file", "labels", "caption", "fingerprint", "pulled", "missing", "status", "review")
    reviewers = sorted({f["review"]["reviewer"] for f in floats + preambles if f.get("review")})
    payload = {"schema_version": 3, "base": str(base), "reviews": str(rpath),
               "summary_zh": "；".join(parts),
               "floats": [{k: f[k] for k in keys} for f in floats],
               "preambles": [{k: p[k] for k in keys} for p in preambles],
               "reviewers": reviewers, "findings": findings, "hard_finding_count": len(hard),
               "limits": "whether a figure is right is the reviewer's call; this records who looked at which "
                         "version. Not followed: what a macro expands to, packages and classes."}
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
        fl, pre, _ = collect(Tree(a.base_dir, a.built_from), a.main)
        then = {f["id"]: f["fingerprint"] for f in fl + pre}
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
            pre = [x for p in payload["preambles"] for x in [p["file"]] + p["pulled"]]
            files = [Path(a.base_dir) / q for q in [f["file"]] + f["pulled"] + pre]
            newest = max((p.stat().st_mtime for p in files if p.is_file()), default=0)
            if newest > Path(pdf).stat().st_mtime:
                notes.append("a file of this float is newer than the PDF: rebuild before reviewing")
        rows.append((f, number, page, png, notes))
    pre_rows = []
    for p in payload["preambles"]:
        notes = []
        if then is not None and then.get(p["id"]) != p["fingerprint"]:
            notes.append(f"PDF built from {a.built_from}, where the preamble was a different version: rebuild first")
        pre_rows.append((p, notes))
    lines = ["# Figure and table review sheet", "",
             f"Built from: {a.built_from or 'unknown (mtime compared)'}. PDFs: "
             + ", ".join(f"{p} (sha256 {hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]})" for p in a.pdf), "",
             "Look at each page; then add a row to the review record (verdict ok, or fix with a note).", ""]
    for f, number, page, png, notes in rows:
        kind = "Figure" if "figure" in f["env"].lower() else "Table"
        cap = re.sub(r"(?<!\\)%", "", f["caption"])
        lines += [f"## {kind} {number or '?'} · `{f['id']}` · PDF page {page or '-'}", "",
                  f"- PNG: {png.name if png else '-'}", f"- fingerprint: `{f['fingerprint']}` · now: {f['status']}",
                  f"- caption: {cap[:400] or '(none)'}"]
        lines += [f"- **{n}**" for n in notes]
        lines += ["", "```", f"{f['id']}\t{f['fingerprint']}\t<reviewer>\t<date>\t<ok|fix>\t<note>", "```", ""]
    for p, notes in pre_rows:
        lines += [f"## Preamble · `{p['id']}`", "",
                  "- A preamble change can alter every float it reaches (a macro, a length, a font); a review of it "
                  "means the float pages above were looked at under this preamble.",
                  f"- fingerprint: `{p['fingerprint']}` · now: {p['status']}",
                  f"- pulls in: {', '.join(p['pulled']) or '(nothing)'}"]
        lines += [f"- **{n}**" for n in notes]
        lines += ["", "```", f"{p['id']}\t{p['fingerprint']}\t<reviewer>\t<date>\t<ok|fix>\t<note>", "```", ""]
    (out / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    n = sum(1 for *_, png, _ in rows if png)
    print(f"rendered {len(set(p for *_, p, _ in rows if p))} page(s) for {n} of {len(rows)} float(s) -> "
          f"{out / 'REVIEW.md'}")
    for f, number, page, png, notes in rows:
        for note in notes:
            print(f"  {f['id']}: {note}")
    for p, notes in pre_rows:
        for note in notes:
            print(f"  {p['id']}: {note}")
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
