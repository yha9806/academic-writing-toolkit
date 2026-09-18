"""Read-only git access. Nothing in the engine writes to the manuscript repository."""
import subprocess


class GitError(RuntimeError):
    pass


def _run(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r


def rev_parse(repo, ref):
    return _run(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.decode().strip()


def is_repo(repo):
    try:
        return _run(repo, "rev-parse", "--git-dir", check=False).returncode == 0
    except (FileNotFoundError, NotADirectoryError):
        return False


def show(repo, commit, path):
    r = _run(repo, "show", f"{commit}:{path}", check=False)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def blob_id(repo, commit, path):
    r = _run(repo, "rev-parse", f"{commit}:{path}", check=False)
    return r.stdout.decode().strip() if r.returncode == 0 else None


def ls_tree(repo, commit, path):
    r = _run(repo, "ls-tree", "-r", "--name-only", commit, "--", path, check=False)
    return [x for x in r.stdout.decode("utf-8", "replace").splitlines() if x]


def log_touching(repo, ref, pathspecs):
    """Commits on the first-parent history of ref that touch any pathspec, oldest first.
    Returns [{"sha", "time", "subject", "body"}]."""
    fmt = "%H%x1f%ct%x1f%s%x1f%b%x1e"
    r = _run(repo, "log", "--first-parent", "--reverse", f"--format={fmt}", ref, "--", *pathspecs)
    out = []
    for rec in r.stdout.decode("utf-8", "replace").split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, t, subj, body = rec.split("\x1f")
        out.append({"sha": sha, "time": int(t), "subject": subj, "body": body.strip()})
    return out


def parent(repo, sha):
    r = _run(repo, "rev-parse", f"{sha}^", check=False)
    return r.stdout.decode().strip() if r.returncode == 0 else None


def tree_blobs(repo, commit, path):
    """{path: blob id} for every file under path at commit, in one call."""
    r = _run(repo, "ls-tree", "-r", commit, "--", path, check=False)
    out = {}
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        meta, _, name = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            out[name] = parts[2]
    return out


def count_between(repo, old, new):
    """Commits reachable from new but not from old; None if either is unknown (e.g. history was rewritten)."""
    if not old or not new:
        return None
    r = _run(repo, "rev-list", "--count", f"{old}..{new}", check=False)
    out = r.stdout.decode().strip()
    return int(out) if r.returncode == 0 and out.isdigit() else None
