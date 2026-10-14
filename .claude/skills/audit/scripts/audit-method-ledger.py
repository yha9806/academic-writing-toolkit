#!/usr/bin/env python3
r"""Bind the sentences that say what was done to where it was done.

    python3 audit-method-ledger.py --base-dir <manuscript tree> --ledger <method-ledger.tsv>
        [--repo NAME=PATH[@COMMIT]] [--repo-commit-file NAME=FILE] [--repo-prefix NAME=PREFIX]
        [--manuscript-prefix PREFIX] [--full FILE] [--note-flags REGEX] [--git <manuscript repository>]
        [--state <ids.json>] [--json] [--migrate-headings]

The gap this closes (spec docs/specs/2026-09-29-method-ledger.md). A sentence about methods, data, design, what a
figure shows or a result judged without a value carries no claim, number or citation, so the other ledgers never
read it. On one manuscript every check was current while a figure drew two independent controls as nested, and the
methods named the wrong scoring function. A method ledger binds each such sentence to the code, config or output
that shows it. It is a TSV:

    id  loc  sentence  claim_type  pointer  evidence  verdict  note  checked

This script keeps it true after it is written. It reports:

  sentence-changed          the row's sentence is no longer in the file `loc` names (headings are ignored both sides)
  pointer-missing           a pointer names a file, line range, JSON/YAML key, verbatim fragment, \label or commit
                            that is not there
  pointer-by-line           a pointer gives a line number into the manuscript's own .tex (line numbers drift with
                            every edit; point by \label, heading or a fragment instead)
  no-pointer                a row with a claim has nothing checkable in its pointer
  open-verdict              mismatch / unlocated, or partial without `checked`
  bad-verdict               a verdict the ledger does not define
  retired-but-present       a row retired for a deleted sentence whose sentence is back
  row-dropped               a row id seen on an earlier run is gone without having been retired (needs --state)
  duplicate-id              two rows share an id
  note-contradicts-verdict  a `match` row whose note says the sentence is unmarked or says too much
  unledgered                a sentence of a --full file with no row

Pointers are read out of the cell's text, as the ledger writes them: `;` or `；` between them, prose around them.
A path is looked up in the pinned repositories (at their commit) and then in the manuscript tree. Line numbers into a
pinned repository are allowed, since a locked commit does not move.

Exit 0 when nothing is reported, 1 when anything is, 2 when nothing could be examined: the ledger is missing, empty
or has no row with a pointer, or a pinned repository or commit is not there.
"""
import argparse
import csv
import difflib
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

VERDICTS = ("match", "partial", "mismatch", "unlocated", "author", "none", "retired")
OPEN = ("mismatch", "unlocated")
NOTE_FLAGS = r"未标|没标|说过头|not marked|unlabell?ed|overclaim|post[- ]hoc"
MANUSCRIPT_PREFIXES = ("overleaf:", "manuscript:", "ms:")
EXT = r"jsonld|jsonl|json|ya?ml|py|mjs|js|md|tsv|csv|tex|txt|npy|npz|lock|sh|bib|zip|html|pdf|png|jpg|R|ipynb|toml|cfg"
PATH_RX = re.compile(r"(?<![\w/.~-])((?:[A-Za-z][\w-]*:)?(?:~/)?(?:[\w\-.*]+/)*[\w\-.*]+\.(?:" + EXT + r")(?![\w.])"
                     r"|\bLICENSE\b)"
                     r"(?::(\d+(?:[-–]\d+)?(?:,\d+(?:[-–]\d+)?)*))?"
                     r"(?:#([^\s;；（(、]+))?"
                     r"(?:@(?:\"([^\"]+)\"|「([^」]+)」))?")
LABEL_RX = re.compile(r"\\label\{([^}]*)\}")
COMMIT_RX = re.compile(r"\bcommit:([0-9a-f]{7,40})\b")
HEADING = re.compile(r"\\(?:(?:sub)*section|(?:sub)?paragraph|chapter)\*?\s*")


class Stop(Exception):
    """Nothing could be examined: exit 2 with the reason."""


def git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True)
    if r.returncode:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def _group(text, i):
    """The end of the {...} group starting at text[i] == '{', or -1."""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "\\":
            continue
        if c == "{" and (j == 0 or text[j - 1] != "\\"):
            depth += 1
        elif c == "}" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def strip_headings(text):
    """Sectioning commands and the \\label right after them, removed: a run-in \\paragraph{...} stored in front of a
    paragraph's first sentence is not part of that sentence (FOR-AWT: inserting a sentence after the heading broke the
    row)."""
    out, i = [], 0
    for m in HEADING.finditer(text):
        if m.start() < i:
            continue
        j = m.end()
        if j < len(text) and text[j] == "[":
            k = text.find("]", j)
            j = k + 1 if k >= 0 else j
        if j >= len(text) or text[j] != "{":
            continue
        end = _group(text, j)
        if end < 0:
            continue
        lab = re.match(r"\s*\\label\{[^}]*\}", text[end:])
        out.append(text[i:m.start()])
        out.append(" ")
        i = end + (lab.end() if lab else 0)
    out.append(text[i:])
    return "".join(out)


def norm(t):
    t = re.sub(r"(?m)(?<!\\)%.*$", "", t or "")
    return re.sub(r"\s+", " ", t).strip()


def body(t):
    return norm(strip_headings(norm(t)))


def split_sentences(t):
    t = re.sub(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", " ", t, flags=re.S)
    t = body(t)
    return [s for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\\])", t) if len(s.split()) >= 4]


class GitSource:
    """A repository at a commit, read through one `git cat-file --batch` process."""

    def __init__(self, path, commit):
        self.path, self.commit = Path(path).expanduser(), commit
        self._files, self._proc, self._cache = None, None, {}

    def files(self):
        if self._files is None:
            out = git(self.path, "ls-tree", "-r", "--name-only", self.commit)
            self._files = out.split("\n") if out else []
        return self._files

    def read(self, rel):
        if rel in self._cache:
            return self._cache[rel]
        if self._proc is None:
            self._proc = subprocess.Popen(["git", "-C", str(self.path), "cat-file", "--batch"],
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._proc.stdin.write(f"{self.commit}:{rel}\n".encode())
        self._proc.stdin.flush()
        head = self._proc.stdout.readline().split()
        out = None
        if len(head) == 3 and head[1] == b"blob":
            out = self._proc.stdout.read(int(head[2]))
            self._proc.stdout.read(1)
        elif len(head) == 3:
            self._proc.stdout.read(int(head[2]) + 1)
        self._cache[rel] = out
        return out


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache"}


class DiskSource:
    """Files on disk: the manuscript tree the loop extracted, or a working copy (tracked or not)."""

    def __init__(self, base):
        self.base = Path(base).expanduser()
        self._files = None

    def files(self):
        if self._files is None:
            import os
            out = []
            for root, dirs, names in os.walk(self.base):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                rel = Path(root).relative_to(self.base).as_posix()
                out += [n if rel == "." else f"{rel}/{n}" for n in names]
            self._files = out
        return self._files

    def read(self, rel):
        p = self.base / rel
        try:
            return p.read_bytes() if p.is_file() else None
        except OSError:
            return None


class Repo:
    """A named repository: pinned (its commit, with its working copy kept only to say a file is outside the pin) or
    not (its working copy)."""

    def __init__(self, name, path, commit):
        self.name, self.path, self.commit = name, Path(path).expanduser(), commit
        self.git = GitSource(self.path, commit) if commit else None
        self.disk = DiskSource(self.path)
        self.prefixes = []


def _key_tokens(expr):
    out = []
    for name, br in re.findall(r"([^.\[\]]+)|\[([^\]]*)\]", expr):
        out.append(("name", name) if name else ("index", br))
    return out


def _resolve(obj, toks):
    if not toks:
        return True
    (kind, v), rest = toks[0], toks[1:]
    if kind == "index":
        rng = re.match(r"^(\w+)\.\.(\w+)$", v)
        if rng:  # [c01..c18]: both ends are there, and the rest holds at each
            ends = [rng.group(1), rng.group(2)]
            if isinstance(obj, dict):
                # an end names a key, or a whole word inside one (c01 in "pool/c01.name.jpg")
                def at(e):
                    return [k for k in obj if k == e or re.search(r"(?<![A-Za-z0-9])" + re.escape(e) + r"(?![A-Za-z0-9])", str(k))]
                return all(at(e) and any(_resolve(obj[k], rest) for k in at(e)) for e in ends)
            if isinstance(obj, list) and all(e.isdigit() for e in ends):
                return all(int(e) < len(obj) and _resolve(obj[int(e)], rest) for e in ends)
            return False
        sel = re.match(r"^([^=]+)=(.*)$", v)
        if sel:  # [model=x]: an element whose field has that value
            k, want = sel.group(1).strip(), sel.group(2).strip()
            items = obj if isinstance(obj, list) else (list(obj.values()) if isinstance(obj, dict) else [])
            return any(isinstance(x, dict) and str(x.get(k)) == want and _resolve(x, rest) for x in items)
        if v in ("*", ""):
            items = list(obj.values()) if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
            return any(_resolve(x, rest) for x in items)
        if isinstance(obj, list):
            if v.lstrip("-").isdigit():
                i = int(v)
                return -len(obj) <= i < len(obj) and _resolve(obj[i], rest)
            return any(_resolve(x, rest) for x in obj
                       if isinstance(x, dict) and any(str(y) == v for y in x.values()) or x == v)
        return isinstance(obj, dict) and v in obj and _resolve(obj[v], rest)
    if isinstance(obj, dict):
        return v in obj and _resolve(obj[v], rest)
    if isinstance(obj, list):
        return any(_resolve(x, toks) for x in obj if isinstance(x, (dict, list)))
    return False


def key_found(obj, expr):
    """A key path resolves; in a JSON Schema, a field is found by name among its properties and definitions."""
    if _resolve(obj, _key_tokens(expr)):
        return True
    if isinstance(obj, dict) and "$schema" in obj:
        names = [v for k, v in _key_tokens(expr) if k == "name"]

        def props(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("properties", "$defs", "definitions") and isinstance(v, dict):
                        yield from v.keys()
                    yield from props(v)
            elif isinstance(o, list):
                for v in o:
                    yield from props(v)
        return bool(names) and names[-1] in set(props(obj))
    return False


def key_alternatives(expr):
    """`a.b[*].c,d` is a.b[*].c and a.b[*].d."""
    expr = expr.rstrip(".,，。")
    parts = [p for p in re.split(r",(?![^\[]*\])", expr) if p]
    head = parts[0]
    stem = head.rsplit(".", 1)[0] + "." if "." in head else ""
    # each later part is a sibling of the first key's last segment, or a key of its own: either reading will do
    return [head] + [[stem + p, p] if stem else [p] for p in parts[1:]]


def parse_structured(rel, raw):
    """(object, None) or (None, why it cannot be read)."""
    text = raw.decode("utf-8", "replace")
    if rel.endswith((".json", ".jsonld", ".ipynb")):
        try:
            return json.loads(text), None
        except ValueError as e:
            return None, f"不是合法 JSON（{e}）"
    if rel.endswith(".jsonl"):
        try:
            return [json.loads(x) for x in text.splitlines() if x.strip()], None
        except ValueError as e:
            return None, f"不是合法 JSONL（{e}）"
    if rel.endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            return None, "unverifiable"
        try:
            return yaml.safe_load(text), None
        except Exception as e:  # yaml's errors share no public base worth naming here
            return None, f"不是合法 YAML（{e}）"
    return None, "text"


class Checker:
    def __init__(self, a):
        self.tree = DiskSource(a.base_dir)
        self.repos = []
        prefixes = {}
        for spec in a.repo_prefix:
            name, _, pre = spec.partition("=")
            prefixes.setdefault(name, []).append(pre)
        commit_files = dict(x.split("=", 1) for x in a.repo_commit_file)
        for spec in a.repo:
            name, _, rest = spec.partition("=")
            path, _, commit = rest.partition("@")
            if name in commit_files:
                raw = self.tree.read(commit_files[name])
                if raw is None:
                    raise Stop(f"仓 {name} 的锁定提交文件读不到：{commit_files[name]}")
                commit = raw.decode().strip()
            if not Path(path).expanduser().is_dir():
                raise Stop(f"仓 {name} 不在：{path}")
            if commit and git(path, "cat-file", "-e", f"{commit}^{{commit}}") is None:
                raise Stop(f"仓 {name} 里没有锁定的提交 {commit}")
            r = Repo(name, path, commit or None)
            r.prefixes = prefixes.get(name, [])
            self.repos.append(r)
        self.tree = DiskSource(a.base_dir)
        self.working = DiskSource(a.git) if a.git else None
        self.ms_prefixes = tuple(a.manuscript_prefix or MANUSCRIPT_PREFIXES)
        self.git = a.git
        self.notes, self.outside, self.keys_checked = [], [], 0
        self._labels = None
        self._text = {}

    def labels(self):
        if self._labels is None:
            found = set()
            for f in self.tree.files():
                if f.endswith(".tex"):
                    found |= set(LABEL_RX.findall(self.tree.read(f).decode("utf-8", "replace")))
            self._labels = found
        return self._labels

    def sources(self, path):
        """(relative path, [(source, outside the pin?)]) to try, in order: pinned repositories at their commit, the
        manuscript at the index commit, unpinned working copies, the manuscript's working copy, and last the pinned
        repositories' working copies (found there is said: the file is not in the locked commit)."""
        for pre in self.ms_prefixes:
            if path.startswith(pre):
                return path[len(pre):], [(self.tree, False)] + ([(self.working, False)] if self.working else [])
        for r in self.repos:
            for pre in [r.name + ":"] + r.prefixes:
                if path.startswith(pre):
                    return path[len(pre):], ([(r.git, False), (r.disk, True)] if r.git else [(r.disk, False)])
        m = re.match(r"([0-9a-f]{7,40}):(.+)$", path)
        if m:
            return m.group(2), [(GitSource(p, m.group(1)), False)
                                for p in [r.path for r in self.repos] + ([self.working.base] if self.working else [])
                                if git(p, "cat-file", "-e", f"{m.group(1)}^{{commit}}") is not None]
        if path.startswith("~/"):
            return path, [(DiskSource("/"), False)]
        out = [(r.git, False) for r in self.repos if r.git] + [(self.tree, False)]
        out += [(r.disk, False) for r in self.repos if not r.git]
        out += [(self.working, False)] if self.working else []
        out += [(r.disk, True) for r in self.repos if r.git]
        return path, out

    @staticmethod
    def lookup(src, rel):
        if rel.startswith("~/"):
            rel = str(Path(rel).expanduser()).lstrip("/")
            return rel if src.read(rel) is not None else None  # an absolute path is read, never searched for
        if any(ch in rel for ch in "*?"):
            pat = "*/" + rel
            return next((f for f in src.files() if fnmatch.fnmatch(f, rel) or fnmatch.fnmatch(f, pat)), None)
        if src.read(rel) is not None:
            return rel
        if "/" not in rel:
            return next((f for f in src.files() if f.split("/")[-1] == rel), None)
        return next((f for f in src.files() if f.endswith("/" + rel)), None)  # a path given from a subdirectory

    def find(self, path, cell=""):
        """(source, relative path, bytes) or None. A bare file name is also looked for inside the zip archives the
        same cell names."""
        rel, srcs = self.sources(path)
        for src, outside in srcs:
            if src is None:
                continue
            if isinstance(src, DiskSource) and src.base == Path("/") and not rel.startswith("~/"):
                continue
            hit = self.lookup(src, rel)
            if hit is not None:
                raw = src.read(hit)
                if raw is not None:
                    if outside:
                        self.outside.append(path)
                    return src, hit, raw
        if "/" not in rel:
            import io
            import zipfile
            for z in re.findall(r"((?:~/)?[\w\-./]+\.zip)", cell):
                if z == path:
                    continue
                got = self.find(z)
                if got is None:
                    continue
                try:
                    names = zipfile.ZipFile(io.BytesIO(got[2])).namelist()
                except zipfile.BadZipFile:
                    continue
                if any(fnmatch.fnmatch(n.split("/")[-1], rel) for n in names):
                    return got[0], f"{z}!{rel}", b""
        return None

    def check_pointer(self, rid, m, cell=""):
        """Errors for one path pointer."""
        path, lines, key, frag = m.group(1).rstrip("."), m.group(2), m.group(3), m.group(4) or m.group(5)
        got = self.find(path, cell)
        if got is None:
            return [("pointer-missing", rid, path)]
        src, rel, raw = got
        errs = []
        if lines:
            if src is self.tree and rel.endswith(".tex") and "!" not in rel:
                errs.append(("pointer-by-line", rid, f"{rel}:{lines}"))
            n = raw.count(b"\n") + (0 if raw.endswith(b"\n") else 1)
            top = max(int(x) for x in re.findall(r"\d+", lines))
            if top > n:
                errs.append(("pointer-missing", rid, f"{rel}:{lines} 超出 {n} 行"))
        if key:
            obj, why = parse_structured(rel, raw)
            if why == "unverifiable":
                self.notes.append(f"{rid} {rel}#{key}：没法核（缺 PyYAML）")
            elif why == "text":
                if key.rstrip(".,，。") not in raw.decode("utf-8", "replace"):
                    errs.append(("pointer-missing", rid, f"{rel}#{key}（文件里没有这个词）"))
            elif why:
                errs.append(("pointer-missing", rid, f"{rel}#{key}：{why}"))
            else:
                self.keys_checked += 1
                for alt in key_alternatives(key):
                    readings = alt if isinstance(alt, list) else [alt]
                    if not any(key_found(obj, r) for r in readings):
                        errs.append(("pointer-missing", rid, f"{rel}#{readings[0]}（没有这个键）"))
        if frag and norm(frag) not in norm(raw.decode("utf-8", "replace")):
            errs.append(("pointer-missing", rid, f"{rel}@「{frag[:40]}」（文件里没有这段）"))
        return errs

    def file_body(self, rel):
        if rel not in self._text:
            raw = None
            for pre in self.ms_prefixes:
                if rel.startswith(pre):
                    rel = rel[len(pre):]
            raw = self.tree.read(rel)
            self._text[rel] = None if raw is None else (norm(raw.decode("utf-8", "replace")),
                                                         body(raw.decode("utf-8", "replace")))
        return self._text[rel]

    def sentence_present(self, loc, sentence):
        got = self.file_body(loc.split(":")[0])
        if got is None:
            return False
        raw, stripped = got
        s = body(sentence)
        # a row can hold a heading's own words (a run-in \paragraph{...} that is a sentence): found as written too
        return bool(s) and s in stripped or norm(sentence) in raw

    def commit_exists(self, sha):
        repos = [r.path for r in self.repos] + ([self.git] if self.git else [])
        return any(git(p, "cat-file", "-e", f"{sha}^{{commit}}") is not None for p in repos)


def read_ledger(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
    except (OSError, UnicodeDecodeError) as e:
        raise Stop(f"台账读不了：{path}（{e}）")
    if not rows:
        raise Stop(f"台账为空：{path}")
    need = {"id", "loc", "sentence", "claim_type", "pointer", "verdict"}
    missing = need - set(rows[0].keys())
    if missing:
        raise Stop(f"台账缺列：{', '.join(sorted(missing))}")
    return rows


def migrate(path, rows):
    """A diff that removes heading prefixes from sentence cells. Printed, never written."""
    old = Path(path).read_text(encoding="utf-8").splitlines(keepends=True)
    fields = list(rows[0].keys())
    new_rows = []
    for r in rows:
        s = r["sentence"] or ""
        stripped = norm(strip_headings(s))
        if stripped and stripped != norm(s) and HEADING.match(s.lstrip()):
            r = dict(r, sentence=stripped)
        new_rows.append(r)
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(new_rows)
    new = buf.getvalue().splitlines(keepends=True)
    sys.stdout.writelines(difflib.unified_diff(old, new, fromfile=str(path), tofile=str(path) + "（去掉标题前缀）"))


def audit(a):
    ledger = Path(a.ledger) if Path(a.ledger).is_absolute() else Path(a.base_dir) / a.ledger
    rows = read_ledger(ledger)
    if a.migrate_headings:
        migrate(ledger, rows)
        return None
    ck = Checker(a)
    flags = re.compile(a.note_flags or NOTE_FLAGS, re.I)
    errors, pending, seen, with_pointer = [], 0, {}, 0
    # The sentences rows vouch for, for the --full sweep. A retired row vouches for none: its sentence was deleted, and
    # counting it let a new sentence that is part of it pass as ledgered. One whose sentence is back stays in, since
    # retired-but-present already names that sentence and saying it again as unledgered adds nothing.
    vouching = []
    for r in rows:
        rid = (r.get("id") or "").strip()
        if rid in seen:
            errors.append(("duplicate-id", rid, f"与第 {seen[rid]} 行同号"))
        seen.setdefault(rid, len(seen) + 2)
        verdict = (r.get("verdict") or "").strip()
        vkind = verdict.split()[0] if verdict else ""
        sentence, loc = r.get("sentence") or "", r.get("loc") or ""
        if vkind == "retired":
            parts = verdict.split()
            if len(parts) < 2 or not ck.commit_exists(parts[1]):
                errors.append(("bad-verdict", rid, f"retired 要带删去它的提交号，且提交要在仓里：{verdict[:40]}"))
            if sentence and ck.sentence_present(loc, sentence):
                errors.append(("retired-but-present", rid, loc))
                vouching.append(sentence)
            continue
        vouching.append(sentence)
        if not ck.sentence_present(loc, sentence):
            errors.append(("sentence-changed", rid, loc))
        if (r.get("claim_type") or "").strip() == "none":
            continue
        if vkind not in VERDICTS:
            errors.append(("bad-verdict", rid, verdict[:30] or "（空）"))
        if vkind in OPEN:
            errors.append(("open-verdict", rid, vkind))
        if vkind == "partial":
            pending += 1
            if not (r.get("checked") or "").strip():
                errors.append(("open-verdict", rid, "partial 没写 checked"))
        if vkind == "match" and flags.search(r.get("note") or ""):
            errors.append(("note-contradicts-verdict", rid, (r.get("note") or "")[:60]))
        pointer = r.get("pointer") or ""
        paths = list(PATH_RX.finditer(pointer))
        labels = LABEL_RX.findall(pointer)
        commits = COMMIT_RX.findall(pointer)
        if not (paths or labels or commits):
            errors.append(("no-pointer", rid, pointer[:60] or "（空）"))
            continue
        with_pointer += 1
        for m in paths:
            errors += ck.check_pointer(rid, m, pointer)
        for lab in labels:
            if lab not in ck.labels():
                errors.append(("pointer-missing", rid, "\\label{" + lab + "}"))
        for sha in commits:
            if not ck.commit_exists(sha):
                errors.append(("pointer-missing", rid, "commit:" + sha))
    if not with_pointer:
        raise Stop("台账里没有一行带可检查的出处，不把这当成通过")
    ledgered = [body(s) for s in vouching]
    for f in a.full:
        raw = ck.tree.read(f)
        if raw is None:
            raise Stop(f"要全覆盖的文件不在：{f}")
        for s in split_sentences(raw.decode("utf-8", "replace")):
            if not any(x and (s in x or x in s) for x in ledgered):
                errors.append(("unledgered", f, s[:70]))
    if a.state:
        sp = Path(a.state)
        try:
            known = set(json.loads(sp.read_text(encoding="utf-8")).get("ids") or [])
        except (OSError, ValueError, AttributeError):
            known = None
        now = set(seen)
        if known is not None:
            for rid in sorted(known - now):
                errors.append(("row-dropped", rid, "上次还在，现在没了；删句要写 retired <提交号>，不删行"))
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps({"ids": sorted((known or set()) | now)}, ensure_ascii=False), encoding="utf-8")
    kinds = {}
    for k, _, _ in errors:
        kinds[k] = kinds.get(k, 0) + 1
    claims = sum(1 for r in rows if (r.get("claim_type") or "").strip() != "none")
    summary = (f"台账 {len(rows)} 行（有主张 {claims}）；报错 {len(errors)}"
               + ("（" + "、".join(f"{k} {n}" for k, n in sorted(kinds.items())) + "）" if kinds else "")
               + f"；待定（partial）{pending} 行")
    summary += f"；核了 {ck.keys_checked} 个 JSON/YAML 键"
    if ck.notes:
        summary += f"，{len(ck.notes)} 个没法核"
    if ck.outside:
        summary += f"；{len(set(ck.outside))} 个出处只在磁盘上、不在锁定的提交里"
    return {"rows": len(rows), "claims": claims, "pending": pending, "kinds": kinds,
            "errors": [{"kind": k, "id": i, "detail": d} for k, i, d in errors], "notes": ck.notes,
            "outside_pin": sorted(set(ck.outside)), "keys_checked": ck.keys_checked,
            "pinned": {r.name: r.commit for r in ck.repos}, "summary_zh": summary}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-dir", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--repo", action="append", default=[], help="NAME=PATH[@COMMIT]")
    ap.add_argument("--repo-commit-file", action="append", default=[], help="NAME=FILE in the manuscript tree")
    ap.add_argument("--repo-prefix", action="append", default=[], help="NAME=PREFIX that routes a pointer to NAME")
    ap.add_argument("--manuscript-prefix", action="append", default=[])
    ap.add_argument("--full", action="append", default=[])
    ap.add_argument("--note-flags")
    ap.add_argument("--git", help="the manuscript repository, for retired and commit: pointers")
    ap.add_argument("--state", help="row ids seen on earlier runs (kept, never pruned)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--migrate-headings", action="store_true")
    a = ap.parse_args(argv)
    try:
        out = audit(a)
    except Stop as e:
        print(f"audit-method-ledger: {e}", file=sys.stderr)
        return 2
    if out is None:
        return 0
    if a.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(out["summary_zh"])
        for e in out["errors"]:
            print(f"  {e['kind']}\t{e['id']}\t{e['detail']}")
        for n in out["notes"]:
            print(f"  注：{n}")
        for n in out["outside_pin"]:
            print(f"  注：{n} 只在磁盘上找到，不在锁定的提交里")
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
