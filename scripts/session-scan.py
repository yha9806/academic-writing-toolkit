#!/usr/bin/env python3
"""What other sessions did to this repository while you were not looking.

    python3 scripts/session-scan.py [--repo DIR] [--since TS | --transcript PATH]
                                    [--transcripts-dir DIR] [--json]

Why this exists. Two sessions of the same agent worked on the same repositories
on one evening, and twice the second one changed what the first should do
next without either noticing:

  - one session committed in a manuscript checkout and swept the other's
    uncommitted edits into its commit. The other session then staged a file
    and found no diff. Both sessions were running from the same working tree.
  - one session merged a branch to main, pushed, and deleted the remote
    branch. The other session, in a separate worktree, was still carrying a
    push plan for that branch, built on remote-tracking refs that no longer
    described the remote.

Nothing in git stops either. Nothing in this toolkit noticed either; both were
caught by hand. This scan asks the questions that would have caught them,
against the remote as it is now, not as the local tracking refs remember it.

Hard findings (exit 1):

  upstream-gone                 the branch's upstream is not on the remote
  foreign-commit-in-push-range  a commit a push would carry was not made in
                                this worktree
  staged-before-session         a staged file was last modified before this
                                session began, so the change may be another
                                session's

Prompts (printed, exit 0):

  behind-remote           the remote branch has commits HEAD lacks
  branch-not-on-remote    the branch exists only on this disk
  branch-on-other-remote  a second remote has the branch, and how far behind
  stale-tracking-ref      a remote-tracking ref names a branch the remote
                          no longer has; ahead/behind counts built on it
                          are fiction until `git fetch --prune`
  other-worktree          another worktree of this repository, with its
                          branch and its dirty-file count
  dirty-before-session    an unstaged or untracked file last modified before
                          this session began
  foreign-commit-since    a commit on any ref, made since the session began,
                          not made in this worktree
  session-mentioning-repo a transcript under --transcripts-dir, modified
                          since the session began, that names this
                          repository's path

"Made in this worktree" is read from this worktree's own HEAD reflog: commit,
cherry-pick, rebase, revert and merge entries, not checkouts or fast-forwards.
Two limits, stated in the output: a session that shares this working tree
writes to the same reflog, so "here" means "here, by any session using this
tree"; and a rebase rewrites foreign commits into local ones.

The session's start is `--since` or the first user record in `--transcript`.
Without either, the three time-bound checks are not run, and the output says
so. A transcript's file birth time is not its start: on this machine one file
was born three hours after its first user message.

Exit: 1 on a hard finding; 2 when the target is not a repository, has no
remote, or the remote cannot be reached (a scan that cannot see the remote
has not scanned); 0 otherwise.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE_PREFIXES = ("commit", "cherry-pick", "rebase", "revert", "am")


def die(message):
    """A scan that could not scan exits 2, so it cannot be read as a pass."""
    print(message, file=sys.stderr)
    sys.exit(2)


def git(repo, *args, timeout=10):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_SSH_COMMAND="ssh -o BatchMode=yes", LC_ALL="C")
    try:
        r = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timed out after %ss" % timeout
    except OSError as e:
        return 127, "", str(e)


def parse_since(text):
    """'2026-09-20 21:00', '2026-09-20T21:00:00', or ISO with Z; naive means local time."""
    text = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt).astimezone().timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        die("SINCE_UNREADABLE: %r is not a time this scan can read" % text)


def transcript_start(path):
    """The first user record's timestamp. Not the file's birth time (see docstring)."""
    stamp = re.compile(rb'"timestamp"\s*:\s*"([^"]+)"')
    with open(path, "rb") as fh:
        for line in fh:
            if b'"type":"user"' in line or b'"type": "user"' in line:
                m = stamp.search(line)
                if m:
                    return datetime.fromisoformat(m.group(1).decode().replace("Z", "+00:00")).timestamp()
    die("TRANSCRIPT_NO_START: no user record with a timestamp in %s" % path)


def here_commits(repo):
    """SHAs this worktree's HEAD reflog says were made here."""
    rc, out, _ = git(repo, "reflog", "show", "HEAD", "--format=%H%x09%gs")
    made = set()
    if rc != 0:
        return made
    for line in out.splitlines():
        sha, _, subject = line.partition("\t")
        s = subject.strip().lower()
        if s.startswith(HERE_PREFIXES) or ((s.startswith("merge") or s.startswith("pull")) and "fast-forward" not in s):
            made.add(sha)
    return made


def worktrees(repo):
    rc, out, _ = git(repo, "worktree", "list", "--porcelain")
    items, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val if val else True
    return items if rc == 0 else []


def mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return None


def fmt_ts(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--since", help="session start, local time unless a zone is given")
    ap.add_argument("--transcript", help="this session's transcript; its first user record is the start")
    ap.add_argument("--transcripts-dir", default=os.path.expanduser("~/.claude/projects"),
                    help="where other sessions' transcripts live; scanned for this repository's path")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.since and a.transcript:
        die("SINCE_TWICE: give --since or --transcript, not both")

    rc, top, err = git(a.repo, "rev-parse", "--show-toplevel")
    if rc != 0:
        die("NOT_A_REPOSITORY: %s (%s)" % (Path(a.repo).resolve(), err.strip()[:120]))
    repo = Path(top.strip()).resolve()
    rc, branch, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip() if rc == 0 else "HEAD"
    detached = branch == "HEAD"
    rc, head_sha, _ = git(repo, "rev-parse", "HEAD")
    head_sha = head_sha.strip()

    rc, remotes, _ = git(repo, "remote")
    remotes = remotes.split()
    if not remotes:
        die("NO_REMOTE: %s has no remote, so nothing here can be checked against one (no remote = no backup)" % repo)
    remote = None
    if not detached:
        rc, out, _ = git(repo, "config", "--get", "branch.%s.remote" % branch)
        remote = out.strip() if rc == 0 and out.strip() else None
    remote = remote or ("origin" if "origin" in remotes else remotes[0])

    rc, out, err = git(repo, "ls-remote", "--heads", remote, timeout=15)
    if rc != 0:
        die("REMOTE_UNREACHABLE: git ls-remote %s failed (%s); local tracking refs are not a substitute" % (
            remote, (err.strip() or "exit %d" % rc)[:160]))
    remote_heads = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            remote_heads[ref[len("refs/heads/"):]] = sha

    since = None
    if a.since:
        since = parse_since(a.since)
    elif a.transcript:
        since = transcript_start(a.transcript)

    findings, not_checked = [], []
    here = here_commits(repo)

    # --- upstream and push range ------------------------------------------
    upstream = None
    if not detached:
        rc, out, _ = git(repo, "config", "--get", "branch.%s.merge" % branch)
        if rc == 0 and out.strip().startswith("refs/heads/"):
            upstream = out.strip()[len("refs/heads/"):]
    if upstream and upstream not in remote_heads:
        findings.append({"kind": "upstream-gone", "hard": True,
                         "detail": "%s tracks %s/%s, which the remote no longer has; a plan built on that branch is stale" % (
                             branch, remote, upstream)})
    push_target = upstream if upstream in remote_heads else (branch if branch in remote_heads else None)
    if push_target:
        remote_sha = remote_heads[push_target]
        if git(repo, "cat-file", "-e", remote_sha + "^{commit}")[0] != 0:
            not_checked.append("push range: the remote's %s (%s) is not in the local object store; git fetch first" % (
                push_target, remote_sha[:7]))
            rng = None
        else:
            rng = ["%s..HEAD" % remote_sha]
            rc, behind, _ = git(repo, "rev-list", "--count", "HEAD..%s" % remote_sha)
            if rc == 0 and behind.strip() not in ("", "0"):
                findings.append({"kind": "behind-remote", "hard": False,
                                 "detail": "%s/%s has %s commit(s) HEAD lacks: someone pushed since this branch last saw the remote" % (
                                     remote, push_target, behind.strip())})
    else:
        # The branch is not on the remote: a push would carry what no remote
        # branch has. That is measured against the remote's heads when they are
        # all in the local store, and otherwise against the local tracking refs,
        # which is an estimate and said to be one.
        missing = [n for n, s in remote_heads.items() if git(repo, "cat-file", "-e", s + "^{commit}")[0] != 0]
        if remote_heads and not missing:
            rng = ["HEAD", "--not"] + list(remote_heads.values())
        else:
            rng = ["HEAD", "--not", "--remotes=%s" % remote]
            if missing:
                not_checked.append("push range measured against local tracking refs, an estimate: the remote's %s not fetched" % (
                    ", ".join(sorted(missing)[:5]) + (" and %d more" % (len(missing) - 5) if len(missing) > 5 else "")))
    push_range = []
    if rng is not None:
        rc, out, _ = git(repo, "log", "--format=%H%x09%h %ci %s", *rng)
        for line in out.splitlines() if rc == 0 else []:
            sha, _, desc = line.partition("\t")
            push_range.append({"sha": sha, "desc": desc[:110], "here": sha in here})
        for c in push_range:
            if not c["here"]:
                findings.append({"kind": "foreign-commit-in-push-range", "hard": True,
                                 "detail": "a push of %s would carry %s, which this worktree's reflog did not make" % (
                                     branch, c["desc"])})

    # --- the same branch on the other remotes ------------------------------
    # A manuscript mirrored to an editor and to a host has two remotes, and
    # "not on the remote" must say which. Each other remote is asked too.
    for other in remotes:
        if other == remote or detached:
            continue
        rc, out, err = git(repo, "ls-remote", "--heads", other, "refs/heads/" + branch, timeout=15)
        if rc != 0:
            not_checked.append("remote %s unreachable (%s)" % (other, (err.strip() or "exit %d" % rc)[:80]))
            continue
        sha = out.split()[0] if out.strip() else None
        if sha is None:
            findings.append({"kind": "branch-not-on-remote", "hard": False,
                             "detail": "%s is not on %s either" % (branch, other)})
        elif git(repo, "cat-file", "-e", sha + "^{commit}")[0] == 0:
            rc, ahead, _ = git(repo, "rev-list", "--count", "%s..HEAD" % sha)
            findings.append({"kind": "branch-on-other-remote", "hard": False,
                             "detail": "%s is on %s at %s, %s commit(s) behind HEAD" % (branch, other, sha[:7], ahead.strip() or "?")})
        else:
            findings.append({"kind": "branch-on-other-remote", "hard": False,
                             "detail": "%s is on %s at %s, which is not in the local store; git fetch %s" % (branch, other, sha[:7], other)})
    if not push_target and not detached and len(remotes) == 1:
        findings.append({"kind": "branch-not-on-remote", "hard": False,
                         "detail": "%s is not on %s: %d commit(s) exist only on this disk" % (branch, remote, len(push_range))})

    # --- stale remote-tracking refs -----------------------------------------
    rc, out, _ = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/remotes/%s" % remote)
    for ref in out.split() if rc == 0 else []:
        name = ref[len(remote) + 1:]
        if name and name != "HEAD" and name not in remote_heads:
            findings.append({"kind": "stale-tracking-ref", "hard": False,
                             "detail": "%s names a branch the remote no longer has; git fetch --prune" % ref})

    # --- this worktree's dirt ----------------------------------------------
    def paths(*args):
        rc, out, _ = git(repo, *args)
        return [p for p in out.split("\n") if p] if rc == 0 else []
    staged = paths("diff", "--cached", "--name-only")
    unstaged = paths("diff", "--name-only")
    untracked = paths("ls-files", "--others", "--exclude-standard")
    if since is None:
        not_checked.append("files changed before this session began: session start unknown (pass --since or --transcript)")
    else:
        for p in staged:
            m = mtime(repo / p)
            if m is not None and m < since:
                findings.append({"kind": "staged-before-session", "hard": True,
                                 "detail": "%s is staged but was last modified %s, before this session began %s; another session's change?" % (
                                     p, fmt_ts(m), fmt_ts(since))})
        for p in unstaged + untracked:
            m = mtime(repo / p)
            if m is not None and m < since:
                findings.append({"kind": "dirty-before-session", "hard": False,
                                 "detail": "%s was modified %s, before this session began; do not stage it as yours" % (
                                     p, fmt_ts(m))})

    # --- other worktrees ----------------------------------------------------
    others = []
    for wt in worktrees(repo):
        path = wt.get("worktree")
        if not path or Path(path).resolve() == repo:
            continue
        if not Path(path).is_dir():
            others.append({"path": path, "branch": "(missing on disk)", "dirty": None, "newest": None})
            continue
        rc, st, _ = git(path, "status", "--porcelain", "--untracked-files=normal")
        dirty = [ln[3:] for ln in st.splitlines()] if rc == 0 else []
        newest = max((mtime(os.path.join(path, p)) or 0 for p in dirty), default=None)
        label = wt.get("branch", "").replace("refs/heads/", "") or "detached %s" % wt.get("HEAD", "")[:7]
        others.append({"path": path, "branch": label, "dirty": len(dirty), "newest": newest})
        findings.append({"kind": "other-worktree", "hard": False,
                         "detail": "%s on %s: %d dirty file(s)%s" % (
                             path, label, len(dirty), (", newest %s" % fmt_ts(newest)) if newest else "")})

    # --- foreign commits since the session began ---------------------------
    if since is not None:
        rc, out, _ = git(repo, "log", "--all", "--since=%d" % int(since), "--format=%H%x09%h %ci %s")
        for line in out.splitlines() if rc == 0 else []:
            sha, _, desc = line.partition("\t")
            if sha not in here:
                findings.append({"kind": "foreign-commit-since", "hard": False,
                                 "detail": "%s (not made in this worktree)" % desc[:110]})

    # --- other sessions' transcripts ---------------------------------------
    transcripts = []
    tdir = Path(a.transcripts_dir).expanduser()
    if since is None:
        not_checked.append("transcripts naming this repository: session start unknown")
    elif not tdir.is_dir():
        not_checked.append("transcripts naming this repository: %s is not a directory" % tdir)
    else:
        # The path as a session may have written it: resolved, without the
        # macOS /private prefix, or under ~. A following path character means
        # a sibling repository (…-toolkit-fidelity), not this one.
        spellings = {str(repo)}
        if str(repo).startswith("/private/"):
            spellings.add(str(repo)[len("/private"):])
        home = os.path.expanduser("~")
        spellings.update("~" + sp[len(home):] for sp in list(spellings) if sp.startswith(home + "/"))
        needle = re.compile(b"(?:" + b"|".join(re.escape(sp.encode()) for sp in sorted(spellings)) + rb")(?![A-Za-z0-9_.-])")
        own = Path(a.transcript).resolve() if a.transcript else None
        for f in tdir.rglob("*.jsonl"):
            if "memory" in f.parts or (own and f.resolve() == own):
                continue
            m = mtime(f)
            if m is None or m < since:
                continue
            try:
                hit = needle.search(f.read_bytes()) is not None
            except OSError:
                continue
            if hit:
                transcripts.append({"path": str(f), "modified": fmt_ts(m)})
                findings.append({"kind": "session-mentioning-repo", "hard": False,
                                 "detail": "%s (modified %s) names %s" % (f.name, fmt_ts(m), repo)})

    hard = [f for f in findings if f["hard"]]
    payload = {
        "schema_version": 1,
        "repo": str(repo), "branch": branch, "head": head_sha[:7],
        "remote": remote, "remote_heads": len(remote_heads),
        "since": fmt_ts(since) if since else None,
        "push_target": push_target,
        "push_range": push_range,
        "staged": staged, "unstaged": unstaged, "untracked": untracked,
        "other_worktrees": others,
        "transcripts": transcripts,
        "findings": findings,
        "hard_finding_count": len(hard),
        "not_checked": not_checked,
        "limits": {
            "here": "a commit counts as made here when this worktree's HEAD reflog made it; a session sharing this working tree writes the same reflog, and a rebase turns foreign commits into local ones",
            "transcripts": "a session that never wrote this repository's absolute path (relative cd, alias) is invisible to the transcript scan",
            "mtime": "a file this session edited after another session did carries this session's mtime; the older change is then invisible",
        },
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        n_here = sum(1 for c in push_range if c["here"])
        where = ("%s at %s" % (push_target, remote_heads[push_target][:7])) if push_target else "%s not on the remote" % branch
        print("session scan: %s on %s (%s); remote %s: %s (ls-remote, %d branch(es))" % (
            repo, branch, head_sha[:7], remote, where, len(remote_heads)))
        print("coverage: push range %d commit(s) [%d here / %d elsewhere]; %d staged, %d unstaged, %d untracked; "
              "%d other worktree(s); %s" % (
                  len(push_range), n_here, len(push_range) - n_here, len(staged), len(unstaged), len(untracked),
                  len(others), ("%d transcript(s) since %s" % (len(transcripts), fmt_ts(since))) if since else "no session start"))
        for item in not_checked:
            print("NOT checked: %s" % item)
        order = ["upstream-gone", "foreign-commit-in-push-range", "staged-before-session", "behind-remote",
                 "branch-not-on-remote", "branch-on-other-remote", "stale-tracking-ref", "dirty-before-session",
                 "foreign-commit-since", "other-worktree", "session-mentioning-repo"]
        for kind in order:
            group = [f for f in findings if f["kind"] == kind]
            if not group:
                continue
            print("\n%s%s (%d)" % (kind, "" if group[0]["hard"] else " (prompt, not a finding)", len(group)))
            for f in group[:40]:
                print("  " + f["detail"])
            if len(group) > 40:
                print("  … %d more" % (len(group) - 40))
        print("\nLimits: %s." % payload["limits"]["here"])
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
