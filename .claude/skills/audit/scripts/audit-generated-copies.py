#!/usr/bin/env python3
r"""Check that each table or figure a manuscript copies from a generator is what the generator emits now.

    python3 audit-generated-copies.py --base-dir <manuscript> --manifest <generated.json> [--json] [--timeout 240]

The gap this closes. A data repository holds the analysis artifacts and the
scripts that turn them into LaTeX tables and TikZ figures; the manuscript holds
copies of what those scripts wrote. The number ledger binds the prose to the
copies, so a copy is treated as the truth. Nothing asked whether the copy is
still what its generator emits: a cell edited by hand, a copy left behind when
an artifact was rerun, or a fix made in the copy and never in the generator
(the next regeneration undoes it) all passed.

A presence test ("is each cell's number somewhere in the artifact") was the
first idea and is not used: a two-decimal value in [0, 1] turns up by chance in
any artifact holding a few hundred floats, so it passes almost everything.
Rerunning the generator is exact.

The manifest (JSON, in the manuscript repository):

    {"covers": ["tables/*.tex", "figures/*.tex"],
     "hand": {"tables/stats.tex": "written by hand; cells checked by the number ledger only"},
     "generators": [
       {"name": "tables", "repo": "~/data-repo",
        "export": ["scripts", "outputs/*.json"],
        "run": ["{repo}/.venv/bin/python", "scripts/make_tables.py", "{out}"],
        "copies": {"tables/main.tex": "{out}/main.tex"}}]}

For each generator the repository's HEAD commit (never its working tree) is
archived, `export` pathspecs only, into a temporary directory; `run` is run
there with `{tree}` (the archive) and `{out}` (an empty directory)
substituted, and `{repo}` only in the first word (the interpreter: a virtual
environment usually lives in the repository). A relative `repo` is read from
the manuscript directory, which the loop replaces with a copy: give an absolute
or ~ path there. Links in the archive are not extracted. A produced
path must resolve inside the archive or `{out}`; any file already there is
removed before the run, so a generator that writes nothing is caught instead
of the committed copy being read back.

The working tree can still reach a run through the interpreter: PYTHONPATH,
user site-packages and an editable install that points into the repository.
The first two are removed from the environment; the third is looked for in
the interpreter's .pth and editable-finder files, and a hit fails the
generator. Uncommitted changes under the export paths are then reported as
not used, which is only true after these steps.

Copies are read before any generator runs and read again after; a copy that
changed during the run (a generator that syncs into the manuscript) fails.

Comparison is line by line, bytes kept (an invalid UTF-8 byte is not folded
into another), trailing spaces and blank lines ignored, and only whole-line
comments dropped: a provenance comment added to a copy is not a difference,
while a trailing `%` (which joins lines in LaTeX, or sits in a URL) is
compared as written. Output with no content line is not a match for anything.

  differs          the copy is not what the generator emits; the first
                   differing lines are shown
  generator-failed the archive, the run or its timeout failed
  output-missing   the generator ran and did not write a listed file
  copy-missing     a listed copy is not in the manuscript
  unlisted         a file under `covers` that no generator and no `hand`
                   entry names: nobody said where it comes from (matched
                   without regard to case: the disk may not care either)
  hand-missing     a `hand` entry names a file that is not there
  covers-empty     a `covers` pattern that matches no file (a typo turns the
                   unlisted check off)
  listed-twice     one copy named by two generators
  empty-output     the generator wrote a file with no content line
  copy-changed     a copy changed while the generators ran

A `hand` file is listed, not checked. The manifest's commands run on this
machine with the user's rights, as a project check does; they come from the
manuscript repository, which the author controls.

What this does NOT do: decide whether a generator computes the right thing, or
whether the artifact it reads is the right one; nor sandbox the generator,
which runs with the user's rights and could read or write anything it names by
absolute path. It checks that the copy is what the committed generator and
artifacts produce.

Exit: 1 on any finding above, 2 when the manifest is missing or unreadable or
nothing was compared, 0 otherwise. Timeouts kill the generator's whole process
group.
"""
import argparse
import difflib
import io
import json
import os
import posixpath
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

HARD = ("differs", "generator-failed", "output-missing", "copy-missing", "unlisted", "hand-missing", "covers-empty",
        "listed-twice", "empty-output", "copy-changed")
SCRUB = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE")


def content_lines(data):
    """Lines to compare: bytes kept through surrogateescape, trailing space stripped, blank lines and whole-line
    comments dropped."""
    out = []
    for line in data.decode("utf-8", "surrogateescape").splitlines():
        line = line.rstrip()
        if line.strip() and not line.lstrip().startswith("%"):
            out.append(line)
    return out


def first_differences(copy_lines, gen_lines, limit=6):
    """The first changed lines, as the copy has them (-) and as the generator emits them (+)."""
    out = []
    for line in difflib.unified_diff(copy_lines, gen_lines, lineterm="", n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        out.append(line.encode("utf-8", "backslashreplace").decode("utf-8")[:200])
        if len(out) >= limit:
            break
    return out


def git(repo, *args, binary=False):
    """(output, None) or (None, [last error line]). Text output keeps its leading spaces: porcelain status puts the
    first line's status in column one, and stripping it cut the first path short."""
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    if r.returncode:
        return None, r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["git failed"]
    return (r.stdout if binary else r.stdout.decode("utf-8", "replace").rstrip("\n")), None


def export(repo, specs, dest):
    """Archive HEAD's export paths into dest: regular files and directories only (a link could point anywhere).
    Returns (commit, error)."""
    head, err = git(repo, "rev-parse", "HEAD")
    head = head.strip() if head else head
    if err:
        return None, f"not a repository with a commit: {err[0]}"
    tar, err = git(repo, "archive", "--format=tar", "HEAD", "--", *specs, binary=True)
    if err:
        return head, f"git archive: {err[0]}"
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        members = [m for m in t.getmembers() if (m.isfile() or m.isdir())
                   and not (m.name.startswith("/") or ".." in Path(m.name).parts)]
        t.extractall(dest, members=members)
    return head, None


def dirty(repo, specs):
    out, err = git(repo, "status", "--porcelain", "--", *specs)
    return [] if err or not out else [l[3:] for l in out.splitlines()]


def inside(path, dirs):
    real = os.path.realpath(path)
    return any(real == d or real.startswith(d + os.sep) for d in dirs)


def editable_hits(python, repo, env):
    """Files through which this interpreter imports code from the repository's working tree: .pth lines and
    editable-install finders naming a path inside it."""
    probe = "import site,sys;print('\\n'.join(site.getsitepackages()+[site.getusersitepackages()]))"
    try:
        r = subprocess.run([python, "-c", probe], capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return []
    hits, real = [], os.path.realpath(repo)
    for d in (r.stdout or "").splitlines():
        p = Path(d)
        if not p.is_dir():
            continue
        for f in sorted(list(p.glob("*.pth")) + list(p.glob("__editable__*finder*.py"))):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Paths are compared resolved: a temporary directory or a home path is often written through a link.
            if any(inside(m, [real]) for m in re.findall(r"/[^\s'\"\],;)]+", text)):
                hits.append(str(f))
    return hits


def run_argv(argv, cwd, timeout, env):
    """(returncode, stdout, stderr) or raises TimeoutError; on timeout the whole process group is killed."""
    p = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.communicate()
        raise TimeoutError
    return p.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def run_generator(g, base, timeout):
    """Run one generator. Returns (info, {copy: produced bytes or None}, error)."""
    raw = os.path.expanduser(g.get("repo") or "") if isinstance(g.get("repo"), str) else ""
    repo = str((base / raw).resolve()) if raw else ""
    info = {"name": g.get("name") or "?", "repo": repo, "commit": None, "dirty": [], "seconds": None}
    specs = [str(s) for s in g.get("export") or []]
    run = [str(a) for a in g.get("run") or []]
    if not repo or not specs or not run or not isinstance(g.get("copies"), dict):
        return info, {}, "generator needs repo, export, run and copies"
    if any("{repo}" in a for a in run[1:]):
        return info, {}, "{repo} is allowed only in the interpreter: anywhere else the run reads the working tree"
    env = {k: v for k, v in os.environ.items() if k not in SCRUB}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    with tempfile.TemporaryDirectory(prefix="gen-tree-") as tree, tempfile.TemporaryDirectory(prefix="gen-out-") as out:
        commit, err = export(repo, specs, tree)
        info["commit"] = commit
        if err:
            return info, {}, err
        info["dirty"] = dirty(repo, specs)
        subst = lambda s: os.path.expanduser(s).replace("{repo}", repo).replace("{tree}", tree).replace("{out}", out)
        argv = [subst(run[0])] + [subst(a) for a in run[1:]]
        hits = editable_hits(argv[0], repo, env) if os.path.basename(argv[0]).startswith("python") else []
        if hits:
            return info, {}, "the interpreter imports the working tree of the repository through " + ", ".join(hits[:3])
        roots = [os.path.realpath(tree), os.path.realpath(out)]
        produced = {}
        for copy, target in g["copies"].items():
            p = Path(subst(str(target)))
            p = p if p.is_absolute() else Path(tree) / p
            if not inside(p, roots):
                # A file outside the archive and the output directory would be read as it already is, and removing
                # it would remove someone's file.
                return info, {}, f"{copy}: the produced path {target} resolves outside {{tree}} and {{out}}"
            if p.is_dir():
                return info, {}, f"{copy}: the produced path {target} is a directory"
            if p.exists() or p.is_symlink():
                p.unlink()
            produced[copy] = p
        t0 = time.time()
        try:
            code, so, se = run_argv(argv, tree, timeout, env)
        except TimeoutError:
            return info, {}, f"timed out after {timeout} s"
        except OSError as e:
            return info, {}, f"could not start: {e}"
        info["seconds"] = round(time.time() - t0, 2)
        if code:
            tail = (se or so or "").strip().splitlines()[-1:] or ["no output"]
            return info, {}, f"exit {code}: {tail[0][:200]}"
        data = {c: (p.read_bytes() if p.is_file() and inside(p, roots) else None) for c, p in produced.items()}
    return info, data, None


def covered_files(base, patterns):
    """{pattern: [paths]} under base: * and ? within a segment, ** across segments, case ignored."""
    def rx(pat):
        out, i = "", 0
        while i < len(pat):
            if pat.startswith("**/", i):
                out, i = out + "(?:.*/)?", i + 3
            elif pat.startswith("**", i):
                out, i = out + ".*", i + 2
            elif pat[i] == "*":
                out, i = out + "[^/]*", i + 1
            elif pat[i] == "?":
                out, i = out + "[^/]", i + 1
            else:
                out, i = out + re.escape(pat[i]), i + 1
        return re.compile(out, re.I)
    files = []
    for d, dirs, names in os.walk(base):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        rel = os.path.relpath(d, base)
        files += [posixpath.normpath(posixpath.join("" if rel == "." else rel.replace(os.sep, "/"), n)) for n in names]
    return {pat: sorted(f for f in files if rx(posixpath.normpath(str(pat))).fullmatch(f)) for pat in patterns}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--timeout", type=int, default=240, help="seconds per generator")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.base_dir).resolve()
    mpath = Path(a.manifest) if Path(a.manifest).is_absolute() else base / a.manifest
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as e:
        print(f"MANIFEST: cannot read {mpath}: {e}", file=sys.stderr)
        return 2
    gens = manifest.get("generators") or []
    hand = manifest.get("hand") or {}
    covers = manifest.get("covers") or []
    if not isinstance(gens, list) or not isinstance(hand, dict) or not isinstance(covers, list):
        print("MANIFEST: generators must be a list, hand an object, covers a list", file=sys.stderr)
        return 2
    norm = lambda c: posixpath.normpath(str(c))
    hand = {norm(c): r for c, r in hand.items()}
    findings, same, generators, owner = [], [], [], {}
    for g in gens:
        for c in (g.get("copies") or {}) if isinstance(g, dict) and isinstance(g.get("copies"), dict) else {}:
            if norm(c) in owner:
                findings.append({"kind": "listed-twice", "copy": norm(c), "generator": g.get("name") or "?",
                                 "detail": f"also named by {owner[norm(c)]}"})
            owner.setdefault(norm(c), g.get("name") or "?")
    if not owner and not covers:
        print("NOTHING CHECKED: the manifest lists no copy and covers no path. This is not a pass.", file=sys.stderr)
        return 2
    before = {c: ((base / c).read_bytes() if (base / c).is_file() else None) for c in owner}
    compared = set()
    for g in gens:
        if not isinstance(g, dict):
            findings.append({"kind": "generator-failed", "copy": "-", "generator": "?", "detail": "not an object"})
            continue
        info, data, err = run_generator(g, base, a.timeout)
        generators.append(info)
        copies = g.get("copies") if isinstance(g.get("copies"), dict) else {}
        for key in copies:
            copy = norm(key)
            if owner.get(copy) != (g.get("name") or "?") or copy in compared:
                continue
            compared.add(copy)
            if err:
                findings.append({"kind": "generator-failed", "copy": copy, "generator": info["name"], "detail": err})
            elif before.get(copy) is None:
                findings.append({"kind": "copy-missing", "copy": copy, "generator": info["name"],
                                 "detail": "listed in the manifest, not in the manuscript"})
            elif data.get(key) is None:
                findings.append({"kind": "output-missing", "copy": copy, "generator": info["name"],
                                 "detail": f"{info['name']} ran and did not write {copies[key]}"})
            else:
                cl, gl = content_lines(before[copy]), content_lines(data[key])
                if not gl:
                    findings.append({"kind": "empty-output", "copy": copy, "generator": info["name"],
                                     "detail": f"{info['name']} wrote {copies[key]} with no content line"})
                elif cl == gl:
                    same.append(copy)
                else:
                    findings.append({"kind": "differs", "copy": copy, "generator": info["name"],
                                     "detail": f"{info['name']} at {(info['commit'] or '')[:7]} emits something else",
                                     "lines": first_differences(cl, gl)})
    for c, b in before.items():
        now = (base / c).read_bytes() if (base / c).is_file() else None
        if now != b:
            findings.append({"kind": "copy-changed", "copy": c, "generator": owner[c],
                             "detail": "the manuscript copy changed while the generators ran; compared as it was before"})
    hand_out = []
    for copy, reason in hand.items():
        if (base / copy).is_file():
            hand_out.append({"copy": copy, "reason": str(reason)})
        else:
            findings.append({"kind": "hand-missing", "copy": copy, "generator": "-",
                             "detail": "the manifest says it is made by hand; it is not in the manuscript"})
    listed_lower = {c.lower() for c in list(owner) + list(hand)}
    for pat, files in covered_files(base, covers).items():
        if not files:
            findings.append({"kind": "covers-empty", "copy": str(pat), "generator": "-",
                             "detail": "this covers pattern matches no file, so nothing under it is checked"})
        for f in files:
            if f.lower() not in listed_lower and not any(x["copy"] == f for x in findings if x["kind"] == "unlisted"):
                findings.append({"kind": "unlisted", "copy": f, "generator": "-",
                                 "detail": "under covers, named by no generator and no hand entry"})
    checked = len(same) + sum(1 for f in findings if f["kind"] == "differs")
    hard = [f for f in findings if f["kind"] in HARD]
    parts = [f"{checked} 份副本重跑对照：一致 {len(same)}"]
    diff = [f["copy"] for f in findings if f["kind"] == "differs"]
    if diff:
        parts.append(f"不一致 {len(diff)}（{'、'.join(diff[:3])}{' 等' if len(diff) > 3 else ''}）")
    other = [f for f in hard if f["kind"] != "differs"]
    if other:
        parts.append("另有 " + "、".join(f"{k} {sum(1 for f in other if f['kind'] == k)}"
                                          for k in HARD if any(f["kind"] == k for f in other)))
    if hand_out:
        parts.append(f"手做 {len(hand_out)} 份不查")
    payload = {
        "schema_version": 1,
        "base": str(base),
        "manifest": str(mpath),
        "summary_zh": "；".join(parts),
        "copies_checked": checked,
        "same": same,
        "findings": findings,
        "hand": hand_out,
        "generators": generators,
        "hard_finding_count": len(hard),
        "limits": "not decided here: whether a generator computes the right thing or reads the right artifact; the "
                  "generator is not sandboxed. A copy is checked against what the committed generator and artifacts "
                  "produce",
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload["summary_zh"])
        for g in generators:
            print(f"  {g['name']}: {g['repo']} @ {(g['commit'] or '?')[:7]}"
                  + (f", {g['seconds']} s" if g["seconds"] is not None else "")
                  + (f"; uncommitted, not used: {', '.join(g['dirty'][:5])}" if g["dirty"] else ""))
        for f in findings:
            print(f"\n{f['kind']}  {f['copy']}  [{f['generator']}]\n    {f['detail']}")
            for line in f.get("lines") or []:
                print(f"    {line}")
        for h in hand_out:
            print(f"\nhand  {h['copy']}: {h['reason']}")
        print(f"\n{payload['limits'][0].upper()}{payload['limits'][1:]}")
    if hard:
        return 1
    if not checked:
        print("NOTHING CHECKED: no copy was compared with a generator's output. This is not a pass.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
