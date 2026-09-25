#!/usr/bin/env python3
r"""Check that each table or figure a manuscript copies from a generator is what the generator emits now.

    python3 audit-generated-copies.py --base-dir <manuscript> --manifest <generated.json> [--json] [--timeout 300]

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
there with `{repo}`, `{tree}` (the archive) and `{out}` (an empty directory)
substituted. A produced path that is relative is read from the archive; any
file already at a produced path is removed before the run, so a generator that
writes nothing is caught instead of the committed copy being read back.
Uncommitted changes under the export paths are reported and not used.

Comparison ignores LaTeX comments (an escaped \% is text), trailing spaces and
blank lines: a provenance comment added to a copy is not a difference.

  differs          the copy is not what the generator emits; the first
                   differing lines are shown
  generator-failed the archive, the run or its timeout failed
  output-missing   the generator ran and did not write a listed file
  copy-missing     a listed copy is not in the manuscript
  unlisted         a file under `covers` that no generator and no `hand`
                   entry names: nobody said where it comes from
  hand-missing     a `hand` entry names a file that is not there

A `hand` file is listed, not checked. The manifest's commands run on this
machine with the user's rights, as a project check does; they come from the
manuscript repository, which the author controls.

What this does NOT do: decide whether a generator computes the right thing, or
whether the artifact it reads is the right one. It checks that the copy is what
the committed generator and artifacts produce.

Exit: 1 on any finding above, 2 when the manifest is missing or unreadable or
lists nothing to check, 0 otherwise.
"""
import argparse
import difflib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

HARD = ("differs", "generator-failed", "output-missing", "copy-missing", "unlisted", "hand-missing")


def strip_comment(line):
    """The line without its LaTeX comment: a % preceded by an even number of backslashes starts one."""
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


def content_lines(text):
    out = []
    for line in text.splitlines():
        line = strip_comment(line).rstrip()
        if line.strip():
            out.append(line)
    return out


def first_differences(copy_lines, gen_lines, limit=6):
    """The first changed lines, as the copy has them (-) and as the generator emits them (+)."""
    out = []
    for line in difflib.unified_diff(copy_lines, gen_lines, lineterm="", n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        out.append(line[:200])
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
    """Archive HEAD's export paths into dest. Returns (commit, error)."""
    head, err = git(repo, "rev-parse", "HEAD")
    head = head.strip() if head else head
    if err:
        return None, f"not a repository with a commit: {err[0]}"
    tar, err = git(repo, "archive", "--format=tar", "HEAD", "--", *specs, binary=True)
    if err:
        return head, f"git archive: {err[0]}"
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        members = [m for m in t.getmembers() if not (m.name.startswith("/") or ".." in Path(m.name).parts)]
        t.extractall(dest, members=members)
    return head, None


def dirty(repo, specs):
    out, err = git(repo, "status", "--porcelain", "--", *specs)
    return [] if err or not out else [l[3:] for l in out.splitlines()]


def subst(s, repo, tree, out):
    return os.path.expanduser(s).replace("{repo}", repo).replace("{tree}", tree).replace("{out}", out)


def run_generator(g, timeout):
    """Run one generator. Returns (info, {copy: produced text or None}, error)."""
    repo = str(Path(os.path.expanduser(g.get("repo") or "")).resolve()) if g.get("repo") else ""
    info = {"name": g.get("name") or "?", "repo": repo, "commit": None, "dirty": [], "seconds": None}
    specs = [str(s) for s in g.get("export") or []]
    if not repo or not specs or not g.get("run") or not isinstance(g.get("copies"), dict):
        return info, {}, "generator needs repo, export, run and copies"
    with tempfile.TemporaryDirectory(prefix="gen-tree-") as tree, tempfile.TemporaryDirectory(prefix="gen-out-") as out:
        commit, err = export(repo, specs, tree)
        info["commit"] = commit
        if err:
            return info, {}, err
        info["dirty"] = dirty(repo, specs)
        produced = {}
        for copy, target in g["copies"].items():
            p = Path(subst(str(target), repo, tree, out))
            p = p if p.is_absolute() else Path(tree) / p
            if not any(str(p).startswith(d + os.sep) for d in (tree, out)):
                # A file outside the archive and the output directory would be read as it already is: a committed,
                # possibly stale copy, never what this run produced.
                return info, {}, f"{copy}: the produced path {target} is outside {{tree}} and {{out}}"
            produced[copy] = p
            if p.exists():
                p.unlink()
        argv = [subst(str(a), repo, tree, out) for a in g["run"]]
        t0 = time.time()
        try:
            r = subprocess.run(argv, cwd=tree, capture_output=True, text=True, timeout=timeout,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        except subprocess.TimeoutExpired:
            return info, {}, f"timed out after {timeout} s"
        except OSError as e:
            return info, {}, f"could not start: {e}"
        info["seconds"] = round(time.time() - t0, 2)
        if r.returncode:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["no output"]
            return info, {}, f"exit {r.returncode}: {tail[0][:200]}"
        texts = {c: (p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None)
                 for c, p in produced.items()}
    return info, texts, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--timeout", type=int, default=300, help="seconds per generator")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.base_dir)
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
    listed = {c for g in gens if isinstance(g, dict) and isinstance(g.get("copies"), dict) for c in g["copies"]}
    if not listed and not covers:
        print("NOTHING CHECKED: the manifest lists no copy and covers no path. This is not a pass.", file=sys.stderr)
        return 2

    findings, same, generators = [], [], []
    for g in gens:
        if not isinstance(g, dict):
            findings.append({"kind": "generator-failed", "copy": "-", "generator": "?", "detail": "not an object"})
            continue
        info, texts, err = run_generator(g, a.timeout)
        generators.append(info)
        copies = g.get("copies") if isinstance(g.get("copies"), dict) else {}
        for copy in copies:
            cpath = base / copy
            if err:
                findings.append({"kind": "generator-failed", "copy": copy, "generator": info["name"], "detail": err})
                continue
            if not cpath.is_file():
                findings.append({"kind": "copy-missing", "copy": copy, "generator": info["name"],
                                 "detail": "listed in the manifest, not in the manuscript"})
                continue
            gen = texts.get(copy)
            if gen is None:
                findings.append({"kind": "output-missing", "copy": copy, "generator": info["name"],
                                 "detail": f"{info['name']} ran and did not write {copies[copy]}"})
                continue
            cl, gl = content_lines(cpath.read_text(encoding="utf-8", errors="replace")), content_lines(gen)
            if cl == gl:
                same.append(copy)
            else:
                findings.append({"kind": "differs", "copy": copy, "generator": info["name"],
                                 "detail": f"{info['name']} at {(info['commit'] or '')[:7]} emits something else",
                                 "lines": first_differences(cl, gl)})
    hand_out = []
    for copy, reason in hand.items():
        if (base / copy).is_file():
            hand_out.append({"copy": copy, "reason": str(reason)})
        else:
            findings.append({"kind": "hand-missing", "copy": copy, "generator": "-",
                             "detail": "the manifest says it is made by hand; it is not in the manuscript"})
    try:
        covered = sorted({p.relative_to(base).as_posix() for pat in covers for p in base.glob(str(pat)) if p.is_file()})
    except (ValueError, NotImplementedError) as e:
        print(f"MANIFEST: covers has a pattern that cannot be matched under the manuscript: {e}", file=sys.stderr)
        return 2
    for copy in covered:
        if copy not in listed and copy not in hand:
            findings.append({"kind": "unlisted", "copy": copy, "generator": "-",
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
        "limits": "not decided here: whether a generator computes the right thing or reads the right artifact; "
                  "a copy is checked against what the committed generator and artifacts produce",
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
