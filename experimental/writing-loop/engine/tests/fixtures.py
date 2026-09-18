"""Hermetic fixtures: a throwaway manuscript repo and a fake transcripts directory."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from loop import config as C



def git(repo, *args, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if env:
        e.update(env)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=e).stdout.decode().strip()


def draft_md(title, abstract, intro_pars):
    return f"# Draft\n\n## Title candidate\n\n{title}\n\n## Abstract\n\n{abstract}\n\n## 1 Introduction\n\n" + "\n\n".join(intro_pars) + "\n\n## Reference keys\n\n- x\n"


def make_repo(root, commits, branch="main"):
    """commits: [(files: {path: plan or None}, message, unix_time)] applied in order."""
    repo = Path(root) / "ms"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", branch)
    for files, msg, t in commits:
        for path, txt in files.items():
            p = repo / path
            if txt is None:
                git(repo, "rm", "-q", path)
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(txt, encoding="utf-8")
            git(repo, "add", path)
        d = f"@{t} +0000"
        git(repo, "commit", "-q", "--allow-empty", "-m", msg, env={"GIT_AUTHOR_DATE": d, "GIT_COMMITTER_DATE": d})
    return repo


def make_transcripts(root, cwd, branch, records):
    """surveys: list of dicts merged over a base user/assistant survey."""
    proj = Path(root) / "projects" / C.escaped_project_dir(cwd)
    proj.mkdir(parents=True, exist_ok=True)
    for r in records:
        r = dict(r)
        name = r.pop("_file", "s1")
        base = {"cwd": str(cwd), "gitBranch": branch, "sessionId": name, "isSidechain": False}
        with open(proj / f"{name}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**base, **r}, ensure_ascii=False, separators=(",", ":")) + "\n")
    return Path(root) / "projects"


def workspace(root, repo, branch, glob="drafts/DRAFT-v*.md", projects=None, ledger=None):
    ws = Path(root) / "ws"
    for sub in C.SUBDIRS:
        (ws / sub).mkdir(parents=True, exist_ok=True)
    cfg = C.default_config("t", repo, branch, glob)
    cfg["transcripts"]["projects_dir"] = str(projects) if projects else str(Path(root) / "projects")
    cfg["ledger"] = ledger
    C.save(ws, cfg)
    return ws


class TempDir:
    def __enter__(self):
        self._t = tempfile.TemporaryDirectory()
        return Path(self._t.name)

    def __exit__(self, *exc):
        self._t.cleanup()
