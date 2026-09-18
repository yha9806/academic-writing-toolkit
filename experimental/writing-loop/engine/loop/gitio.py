"""Read-only git access. Nothing in the engine writes to the manuscript repository."""
import contextlib
import re
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


class _Objects:
    """One `git cat-file --batch-command` answering object questions for the length of a `batch` block.

    Load report F3 (2026-09-18): a warm update took 1.2 s, and 0.79 s of it was starting 86 git processes, most of
    them one per file read. Scoped to a block rather than kept for the life of the process, so a resident producer
    never holds a git process open against a repository that is being committed to."""

    HEADER = re.compile(rb"^([0-9a-f]{40}|[0-9a-f]{64}) (\S+) (\d+)$")

    def __init__(self, repo):
        self.proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch-command"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def ask(self, command, name):
        """(oid, type, body or None) for the object, None when git says it is missing or ambiguous.
        Raises OSError if the process cannot answer; callers then fall back to a single call."""
        if "\n" in name:
            raise OSError("a name with a line break cannot go through --batch-command")
        self.proc.stdin.write(f"{command} {name}\n".encode("utf-8"))
        self.proc.stdin.flush()
        head = self.proc.stdout.readline()
        if not head:
            raise OSError("cat-file ended")
        m = self.HEADER.match(head.rstrip(b"\n"))
        if not m:
            return None
        body = None
        if command == "contents":
            body = self.proc.stdout.read(int(m.group(3)))
            self.proc.stdout.read(1)
        return m.group(1).decode(), m.group(2).decode(), body

    def close(self):
        with contextlib.suppress(OSError):
            self.proc.stdin.close()
        self.proc.wait()


_batches = {}


@contextlib.contextmanager
def batch(repo):
    """Within the block, show() and blob_id() on this repository go through one cat-file process."""
    key = str(repo)
    if key in _batches:
        yield _batches[key]
        return
    b = _batches[key] = _Objects(repo)
    try:
        yield b
    finally:
        _batches.pop(key, None)  # already gone if it broke mid-block
        b.close()


def _batched(repo, command, commit, path):
    """The batch's answer, or "unanswered" when there is no batch or it could not answer."""
    b = _batches.get(str(repo))
    if b is None:
        return "unanswered"
    try:
        return b.ask(command, f"{commit}:{path}")
    except OSError:
        _batches.pop(str(repo), None)
        return "unanswered"


def show(repo, commit, path):
    got = _batched(repo, "contents", commit, path)
    if got is None:
        return None
    if got != "unanswered" and got[1] == "blob":
        return got[2].decode("utf-8", errors="replace")
    # no batch, or not a blob (git show prints a tree as a listing): ask git show itself
    r = _run(repo, "show", f"{commit}:{path}", check=False)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def blob_id(repo, commit, path):
    got = _batched(repo, "info", commit, path)
    if got != "unanswered":
        return got[0] if got else None
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
