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

A float is a figure or table environment in the files reachable from --main
through \input, \include, \subfile and \import (a float environment inside an
input file counts). Its id is its first \label, or <file>#<n> without one. Its
fingerprint is sha256 over its environment text (comments dropped, spaces
collapsed) and the path and bytes of every file it pulls in (\input and
\includegraphics, recursively through .tex files), first 16 hex digits. A
change to the caption, the layout commands around it, a table source, a TikZ
file or an included image changes it; a change elsewhere in the draft does
not. \graphicspath is not read: an image found only through it is reported
missing.

The review record is a TSV with a header:

    label<TAB>fingerprint<TAB>reviewer<TAB>date<TAB>verdict<TAB>note

Only rows whose fingerprint is the float's current one count; the last such
row decides. A verdict that starts with "fix" keeps the float open.

  unreviewed    no row for the float's current fingerprint
  review-open   the latest current row says fix
  missing-file  the float pulls in a file that is not there
  stale-row     PROMPT: a row whose label no longer names a float

--render writes one PNG per page that holds a float (pdftoppm), found through
\newlabel in each .aux, and a REVIEW.md sheet listing each float's number,
page, PNG, fingerprint and caption, with a row to fill in. With --built-from,
each float's fingerprint at that commit is compared with the current one, and
a float whose rendered page shows an older version is marked so; without it
the PDF's modification time is compared with the float's files. A float whose
label is in no .aux is listed as not rendered.

Exit: 1 on unreviewed, review-open or missing-file; 2 when no float is found,
or the review record is unreadable; 0 otherwise. --render exits 2 when it
renders nothing.
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

ENVS = r"figure\*?|table\*?|sidewaysfigure\*?|sidewaystable\*?|wrapfigure|wraptable|SCfigure|SCtable"
BEGIN = re.compile(r"\\begin\{(" + ENVS + r")\}")
INPUTS = re.compile(r"\\(?:input|include|subfile)\s*\{([^{}]+)\}|\\input\s+([^\s{}\\]+)"
                    r"|\\(?:sub)?import\*?\{([^{}]*)\}\{([^{}]+)\}")
GRAPHICS = re.compile(r"\\includegraphics\*?(?:\[[^\]]*\])*\{([^{}]+)\}")
LABEL = re.compile(r"\\label\{([^{}]+)\}")
NEWLABEL = re.compile(r"\\newlabel\{([^{}]+)\}\{\{((?:[^{}]|\{[^{}]*\})*)\}\{([^{}]*)\}")
IMAGE_EXT = ("", ".pdf", ".png", ".jpg", ".jpeg", ".eps")
COLUMNS = ["label", "fingerprint", "reviewer", "date", "verdict", "note"]
DEPTH = 6


def strip_comment(line):
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k = j
        while k > 0 and line[k - 1] == "\\":
            k -= 1
        if (j - k) % 2 == 0:
            return line[:j]
        i = j + 1


def uncomment(text):
    return "\n".join(strip_comment(l) for l in text.splitlines())


class Tree:
    """Files as the working tree has them, or as a commit has them (--built-from)."""

    def __init__(self, base, commit=None):
        self.base, self.commit, self._cache = Path(base), commit, {}

    def read(self, rel):
        if rel not in self._cache:
            if self.commit:
                r = subprocess.run(["git", "-C", str(self.base), "show", f"{self.commit}:{rel}"], capture_output=True)
                self._cache[rel] = r.stdout if r.returncode == 0 else None
            else:
                p = self.base / rel
                self._cache[rel] = p.read_bytes() if p.is_file() else None
        return self._cache[rel]

    def text(self, rel):
        b = self.read(rel)
        return None if b is None else b.decode("utf-8", "replace")


def resolve(tree, name, here, exts):
    for base in here:
        for ext in exts:
            cand = posixpath.normpath(posixpath.join(base, name + ext) if base else name + ext)
            if not cand.startswith("../") and tree.read(cand) is not None:
                return cand
    return None


def input_names(text):
    out = []
    for a, b, d, f in INPUTS.findall(text):
        name = (a or b or (posixpath.join(d, f) if f else "")).strip()
        if name:
            out.append(name if posixpath.splitext(name)[1] else name + ".tex")
    return out


def reachable(tree, mains):
    """Files reachable from the main files, in the order first met; unresolved \\input names are skipped here (a
    float that pulls in a missing file is reported by the float)."""
    seen, order = set(), []

    def walk(rel, root_dir, depth):
        if rel in seen or depth > DEPTH:
            return
        text = tree.text(rel)
        if text is None:
            return
        seen.add(rel)
        order.append(rel)
        here = [root_dir, posixpath.dirname(rel), ""]
        for name in input_names(uncomment(text)):
            got = resolve(tree, name, here, ("",))
            if got:
                walk(got, root_dir, depth + 1)
    for m in mains:
        walk(posixpath.normpath(m), posixpath.dirname(posixpath.normpath(m)), 0)
    return order


def balanced(text, i):
    """The {...} group starting at text[i] == '{', without its braces, and the index after it."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return text[i + 1:], len(text)


def caption_of(body):
    m = re.search(r"\\caption\*?\s*(?:\[[^\]]*\])?\s*\{", body)
    if not m:
        return ""
    cap, _ = balanced(body, m.end() - 1)
    return re.sub(r"\s+", " ", cap).strip()


def floats_in(tree, rel):
    text = uncomment(tree.text(rel) or "")
    out = []
    for n, m in enumerate(BEGIN.finditer(text), 1):
        end = text.find("\\end{" + m.group(1) + "}", m.end())
        body = text[m.start():(end + len(m.group(1)) + 6) if end >= 0 else len(text)]
        labels = LABEL.findall(body)
        out.append({"id": labels[0] if labels else f"{rel}#{n}", "env": m.group(1), "file": rel, "labels": labels,
                    "caption": caption_of(body), "body": body})
    return out


def pulled(tree, body, rel, root_dir, depth=0, acc=None, missing=None):
    """Files a float pulls in: [(path, sha256)] and the names that resolve to nothing."""
    acc = [] if acc is None else acc
    missing = [] if missing is None else missing
    here = [root_dir, posixpath.dirname(rel), ""]
    for name in input_names(body):
        got = resolve(tree, name, here, ("",))
        if not got:
            missing.append(name)
        elif got not in [p for p, _ in acc] and depth < DEPTH:
            acc.append((got, hashlib.sha256(tree.read(got)).hexdigest()))
            pulled(tree, uncomment(tree.text(got) or ""), got, root_dir, depth + 1, acc, missing)
    for name in GRAPHICS.findall(body):
        got = resolve(tree, name.strip(), here, IMAGE_EXT)
        if not got:
            missing.append(name.strip())
        elif got not in [p for p, _ in acc]:
            acc.append((got, hashlib.sha256(tree.read(got)).hexdigest()))
    return acc, missing


def fingerprint(body, files):
    h = hashlib.sha256(re.sub(r"\s+", " ", body).strip().encode("utf-8"))
    for path, digest in files:
        h.update(("\0" + path + "\0" + digest).encode())
    return h.hexdigest()[:16]


def collect(tree, mains):
    out = []
    root_dirs = {}
    for m in mains:
        for rel in reachable(tree, [m]):
            root_dirs.setdefault(rel, posixpath.dirname(posixpath.normpath(m)))
    for rel, root_dir in root_dirs.items():
        for f in floats_in(tree, rel):
            files, missing = pulled(tree, f["body"], rel, root_dir)
            f.update({"pulled": [p for p, _ in files], "missing": missing, "fingerprint": fingerprint(f["body"], files)})
            out.append(f)
    return out


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
    floats = collect(tree, a.main)
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
    findings = []
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
    reviewers = sorted({f["review"]["reviewer"] for f in floats if f.get("review")})
    payload = {"schema_version": 1, "base": str(base), "reviews": str(rpath),
               "summary_zh": "；".join(parts),
               "floats": [{k: f[k] for k in ("id", "env", "file", "labels", "caption", "fingerprint", "pulled",
                                             "missing", "status", "review")} for f in floats],
               "reviewers": reviewers, "findings": findings, "hard_finding_count": len(hard),
               "limits": "whether a figure is right is the reviewer's call; this records who looked at which "
                         "version. \\graphicspath is not read."}
    return (1 if hard else 0), payload


def aux_pages(aux_files):
    out = {}
    for pdf, aux in aux_files:
        for label, number, page in NEWLABEL.findall(Path(aux).read_text(encoding="utf-8", errors="replace")):
            out.setdefault(label, (pdf, re.sub(r"[{}]|\\relax\s*", "", number).strip(), page.strip()))
    return out


def render(a, payload):
    if len(a.pdf) != len(a.aux) or not a.pdf:
        print("RENDER: give --pdf and --aux in pairs", file=sys.stderr)
        return 2
    if not shutil.which("pdftoppm"):
        print("RENDER: pdftoppm is not installed", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = aux_pages(list(zip(a.pdf, a.aux)))
    then = {f["id"]: f["fingerprint"] for f in collect(Tree(a.base_dir, a.built_from), a.main)} if a.built_from else None
    rendered, rows = {}, []
    for f in payload["floats"]:
        hit = next((pages[l] for l in f["labels"] if l in pages), None)
        if not hit:
            rows.append((f, None, None, None, "not in any .aux given: not rendered"))
            continue
        pdf, number, page = hit
        key = (pdf, page)
        if key not in rendered:
            stem = f"{Path(pdf).stem}-p{int(page):03d}" if page.isdigit() else f"{Path(pdf).stem}-p{page}"
            r = subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", page, "-l", page, "-png", "-singlefile", pdf,
                                str(out / stem)], capture_output=True, text=True)
            rendered[key] = (out / (stem + ".png")) if r.returncode == 0 else None
        png = rendered[key]
        note = ""
        if png is None:
            note = "pdftoppm failed"
        elif then is not None:
            if then.get(f["id"]) != f["fingerprint"]:
                note = f"PDF built from {a.built_from}, where this float was a different version: rebuild before reviewing"
        else:
            files = [Path(a.base_dir) / f["file"]] + [Path(a.base_dir) / p for p in f["pulled"]]
            newest = max((p.stat().st_mtime for p in files if p.is_file()), default=0)
            if newest > Path(pdf).stat().st_mtime:
                note = "a file of this float is newer than the PDF: rebuild before reviewing"
        rows.append((f, number, page, png, note))
    lines = ["# Figure and table review sheet", "",
             f"Built from: {a.built_from or 'unknown (mtime compared)'}. PDFs: "
             + ", ".join(f"{p} (sha256 {hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]})" for p in a.pdf), "",
             "Look at each page; then add a row to the review record (verdict ok, or fix with a note).", ""]
    for f, number, page, png, note in rows:
        kind = "Figure" if "figure" in f["env"].lower() else "Table"
        lines += [f"## {kind} {number or '?'} · `{f['id']}` · page {page or '-'}", "",
                  f"- PNG: {png.name if png else '-'}", f"- fingerprint: `{f['fingerprint']}` · now: {f['status']}",
                  f"- caption: {f['caption'][:400] or '(none)'}"]
        if note:
            lines.append(f"- **{note}**")
        lines += ["", "```", f"{f['id']}\t{f['fingerprint']}\t<reviewer>\t<date>\t<ok|fix>\t<note>", "```", ""]
    (out / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    n = sum(1 for _, _, _, png, _ in rows if png)
    print(f"rendered {len(set(p for *_, p, _ in rows if p))} page(s) for {n} of {len(rows)} float(s) -> {out / 'REVIEW.md'}")
    for f, number, page, png, note in rows:
        if note:
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
