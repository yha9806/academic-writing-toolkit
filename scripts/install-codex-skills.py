#!/usr/bin/env python3
"""Install/update the nine advisory skills from this checkout into user scope.

No network is used unless --install-deps is requested (pip in a private venv).
Install the locked Node build dependencies first: npm ci --prefix guards.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile

SOURCE = Path(__file__).resolve().parents[1]
NAMES = ("audit", "edit-contract", "export", "integrate", "map", "note", "read", "review", "verify-refs")
FORMAT = 1
OWNER = "yha9806/academic-writing-toolkit"
HELPERS = {
    "audit": ("audit-claim-positioning.py", "audit-citation-fidelity.mjs", "audit-prose-fingerprint.py"),
    "edit-contract": ("scaffold-author-control.py", "check-author-control.py"),
    "export": ("audit-claim-positioning.py",),
    "verify-refs": ("verify-refs.py",),
}


class InstallError(RuntimeError):
    pass


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n")


def linked(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def plain_path(path):
    """Reject links/junctions in managed paths, including dangling links."""
    for part in (path, *path.parents):
        if linked(part):
            raise InstallError("Refusing a symlink/junction in installation path: {}".format(part))


def child(root, name):
    target = root / name
    plain_path(target)
    if target.resolve().parent != root.resolve():
        raise InstallError("Installation target escaped its directory")
    return target


def files(root):
    """Inspect before recursing; never follow a Windows junction."""
    if linked(root) or not root.is_dir():
        raise InstallError("Expected an ordinary directory: {}".format(root))
    for entry in sorted(root.iterdir()):
        if linked(entry):
            raise InstallError("Refusing a linked skill resource: {}".format(entry))
        if entry.name == "__pycache__":
            continue
        if entry.is_dir():
            yield from files(entry)
        elif entry.is_file():
            yield entry
        else:
            raise InstallError("Unsupported skill resource: {}".format(entry))


def manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files(root)}


def copy_resource(src, dst):
    if linked(src):
        raise InstallError("Refusing a linked source resource: {}".format(src))
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for p in files(src):
            copy_resource(p, dst / p.relative_to(src))
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        raise InstallError("Missing bundled resource: {}".format(src))


def run(argv, cwd=None, expected=0, timeout=120):
    try:
        result = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError("Cannot run {}: {}".format(argv[0], exc)) from exc
    if result.returncode != expected:
        raise InstallError("Command failed: {}\n{}".format(argv[0], (result.stderr or result.stdout)[-4000:]))
    return result.stdout


def state_dir(dest):
    return dest.parent / ("." + dest.name + "-awt")


@contextmanager
def install_lock(state):
    plain_path(state)
    state.mkdir(parents=True, exist_ok=True)
    lock = child(state, "install.lock")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise InstallError("Another install may be active. Inspect {} before removing a stale lock.".format(lock)) from exc
    try:
        yield
    finally:
        lock.rmdir()


def check_runtime(python):
    run([python, "-I", "-c", "import yaml, markdown; from docx import Document"])


def private_runtime(source, state):
    requirements = source / "scripts/codex-skills-requirements.txt"
    key = hashlib.sha256(requirements.read_bytes()).hexdigest()[:12]
    folder = state / "runtimes" / ("py{}{}-{}".format(*sys.version_info[:2], key))
    python = folder / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # venv executables may legitimately be symlinks on POSIX; the managed
    # folder itself must not be a link. Never resolve a venv executable to
    # its base interpreter, which would lose the environment.
    plain_path(folder)
    marker = folder / "awt-ready.json"
    if marker.is_file():
        check_runtime(python)
        return python
    if folder.exists():
        raise InstallError("An incomplete runtime exists at {}. Inspect/move it before retrying.".format(folder))
    print("Creating a private Python environment and installing the declared dependencies…", file=sys.stderr)
    run([sys.executable, "-m", "venv", folder])
    run([python, "-m", "pip", "install", "--disable-pip-version-check", "-r", requirements], timeout=300)
    check_runtime(python)
    write_json(marker, {"requirementsSha256": hashlib.sha256(requirements.read_bytes()).hexdigest()})
    return python


def build_guards(source):
    node = shutil.which("node")
    if not node:
        raise InstallError("Node.js 22.12+ is required. Install Node, then run npm ci --prefix guards.")
    version = json.loads(run([node, "-p", "JSON.stringify(process.versions.node.split('.').map(Number))"]))
    if not (version[0] == 22 and version[1] >= 12 or version[0] >= 24):
        raise InstallError("Use Node.js ^22.12 or >=24, as declared by guards/package.json.")
    compiler = source / "guards/node_modules/typescript/bin/tsc"
    if not compiler.is_file():
        raise InstallError("Build dependencies are missing. Run npm ci --prefix guards, then retry.")
    # Fresh compilation prevents a stale dist from being labelled with a
    # new source commit. Direct Node invocation also works on Windows.
    run([node, compiler, "-p", source / "guards/tsconfig.json"], cwd=source)


def prepare(source, stage, dest, python):
    import yaml

    for name in NAMES:
        folder = stage / name
        copy_resource(source / ".claude/skills" / name, folder)
        text = (folder / "SKILL.md").read_text(encoding="utf-8")
        # Reference paths in canonical instructions, including future
        # argument-licence references after their separate PR is merged.
        for rel in set(re.findall(r"`(references/[A-Za-z0-9/._-]+)`", text)):
            resource = source / rel
            copy_resource(resource, folder / rel)
            if resource.parent.name == "argument-licence":
                copy_resource(resource.parent, folder / "references/argument-licence")
        for helper in HELPERS.get(name, ()):
            copy_resource(source / "scripts" / helper, folder / "scripts" / helper)
        if name == "audit":
            for rel in ("e1/graders.mjs", "guards/package.json"):
                copy_resource(source / rel, folder / rel)
            for module in ("decisions", "projections", "notes-lint", "vocabulary"):
                rel = "guards/dist/{}.js".format(module)
                copy_resource(source / rel, folder / rel)
            # This dependency is added by the independent Windows/E1 PR.
            if (source / "profiles/awt-headless/pdf-pages.mjs").is_file():
                copy_resource(source / "profiles/awt-headless/pdf-pages.mjs", folder / "profiles/awt-headless/pdf-pages.mjs")
        if name in HELPERS:
            text = re.sub(r"python3 scripts/([\w.-]+)", r'"{python}" "{skill_dir}/scripts/\1"', text)
            text = text.replace("node scripts/audit-citation-fidelity.mjs", 'node "{skill_dir}/scripts/audit-citation-fidelity.mjs"')
            text = text.replace("python .claude/skills/export/scripts/convert_to_docx.py", '"{python}" "{skill_dir}/scripts/convert_to_docx.py"')
            text = text.replace("(needs the guards built once: `npm --prefix guards install && npm --prefix guards run build`.)",
                                "(the installer has bundled the compiled audit dependencies.)")
            index = text.index("\n## ")
            text = text[:index] + (
                "\n## Installed helper paths\n\n"
                "Resolve `{skill_dir}` to the directory containing this SKILL.md. Read\n"
                "`references/local-runtime.md` for `{python}`. All bundled reference paths\n"
                "are relative to this skill directory. Run helpers from the user's target\n"
                "project root, retaining its relative input paths. In PowerShell, prefix\n"
                "a quoted executable with `&`.\n"
            ) + text[index:]
            write_text(folder / "references/local-runtime.md",
                       "# Installed helper runtime\n\nPython (`{python}`): `" + str(python) + "`\n\n" +
                       "Node.js and `pdftotext` (Poppler) are resolved from PATH. Install\n"
                       "Poppler before PDF reading or PDF-based audits. The bundled checks\n"
                       "are Advisory; they do not enforce the AWT dsh app's guards.\n")
        # Preserve local UI metadata/assets; the original whole skill is
        # also retained in the backup. Never silently relax invocation policy.
        for rel in ("agents", "assets"):
            old = dest / name / rel
            if old.is_dir():
                copy_resource(old, folder / rel)
        if name == "export":
            text = text.replace("disable-model-invocation: true\n", "", 1)
            text = text.replace("`disable-model-invocation: true`", "`policy.allow_implicit_invocation: false` in `agents/openai.yaml`")
            metadata = folder / "agents/openai.yaml"
            data = yaml.safe_load(metadata.read_text(encoding="utf-8")) if metadata.exists() else {}
            data = data or {}
            if not isinstance(data, dict) or not isinstance(data.get("policy", {}), dict):
                raise InstallError("export agents/openai.yaml must contain mapping metadata")
            data.setdefault("policy", {})["allow_implicit_invocation"] = False
            write_text(metadata, yaml.safe_dump(data, sort_keys=False))
        write_text(folder / "SKILL.md", text)
        if not text.startswith("---\n"):
            raise InstallError("Missing skill frontmatter: " + name)
        front = yaml.safe_load(text.split("---", 2)[1])
        if front.get("name") != name or not front.get("description") or "disable-model-invocation" in front:
            raise InstallError("Invalid Codex skill frontmatter: " + name)
        for rel in re.findall(r"\{skill_dir\}/([A-Za-z0-9/._-]+)", text):
            if not (folder / rel).is_file():
                raise InstallError("Missing installed helper: " + rel)


def smoke(skills, python):
    """Real helpers, fictional text, no provider calls or user manuscripts."""
    with tempfile.TemporaryDirectory(prefix="awt-skill-check-") as temporary:
        root = Path(temporary) / "project with spaces and 文本"
        write_text(root / "chapters/ch01.md", "# Chapter\n\nJones (2021) discusses evidence in an academic manuscript.\n")
        (root / "literature/reading_notes").mkdir(parents=True)
        audit = json.loads(run(["node", skills / "audit/scripts/audit-citation-fidelity.mjs", "--base-dir", root, "--json"]))
        if audit["citations_checked"] != 1 or not any(f["kind"] == "notes-missing" for f in audit["findings"]):
            raise InstallError("Installed citation audit missed the first paragraph after a heading")
        write_text(root / "references.bib", "@article{test,author={Jones, Alex},title={Fixture},year={2021},journal={Fixture},doi={invalid-doi}}")
        refs = json.loads(run([python, "-I", skills / "verify-refs/scripts/verify-refs.py", "--bib", root / "references.bib", "--json"], expected=1))
        if refs["issue_count"] < 1 or refs["online_sources"]:
            raise InstallError("Installed offline reference checker did not detect the fixture")
        run([python, "-I", skills / "edit-contract/scripts/scaffold-author-control.py", root, "--json"])
        run([python, "-I", skills / "edit-contract/scripts/check-author-control.py", root, "--strict", "--json"], expected=1)
        write_text(root / "chapters/ch01.md", "# Fixture\n\nAWT portable skill installation fixture.\n")
        run([python, "-I", skills / "export/scripts/convert_to_docx.py", "--base-dir", root, "--output-dir", root / "output", "--scope", "chapters"])
        documents = list((root / "output").rglob("*.docx"))
        if len(documents) != 1 or not list((root / "output").glob("*.zip")):
            raise InstallError("Installed exporter did not produce DOCX and ZIP")
        with zipfile.ZipFile(documents[0]) as archive:
            if b"AWT portable skill installation fixture." not in archive.read("word/document.xml"):
                raise InstallError("Installed DOCX is missing fixture content")


def read_receipt(state):
    path = state / "current.json"
    if not path.exists():
        return None
    plain_path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != FORMAT or data.get("owner") != OWNER or set(data.get("files", {})) != set(NAMES):
        raise InstallError("Unrecognised installation receipt: {}".format(path))
    return data


def snapshot(dest):
    plain_path(dest)
    result = {}
    for name in NAMES:
        path = child(dest, name)
        result[name] = manifest(path) if path.exists() else None
    return result


def verify(dest, receipt):
    if not receipt or receipt.get("destination") != str(dest) or snapshot(dest) != receipt["files"]:
        raise InstallError("Installed files differ from the saved hashes, or no matching receipt exists")
    smoke(dest, receipt["python"])


def promote(stage, dest, transaction, before, after, receipt, current):
    """Same-filesystem renames; preserve old and rejected files on failure."""
    backup = child(transaction, "backup")
    backup.mkdir()
    dest.mkdir(parents=True, exist_ok=True)
    moved, installed = [], []
    write_json(transaction / "before.json", before)
    write_json(transaction / "installation.json", receipt)
    if current.exists():
        copy_resource(current, transaction / "previous-installation.json")
    try:
        if snapshot(dest) != before:
            raise InstallError("Installed skills changed during preparation; retry after inspecting them")
        for name in NAMES:
            target = child(dest, name)
            saved = child(backup, name)
            if before[name] is not None:
                target.rename(saved)
                moved.append(name)
                if manifest(saved) != before[name]:
                    raise InstallError("Backup hash mismatch: " + name)
            child(stage, name).rename(target)
            installed.append(name)
            if manifest(target) != after[name]:
                raise InstallError("Installed hash mismatch: " + name)
        # Publish the new receipt only after all nine folders are present.
        temporary = transaction / "current.next.json"
        write_json(temporary, receipt)
        os.replace(temporary, current)
    except BaseException:
        rejected = transaction / "rejected"
        rejected.mkdir(exist_ok=True)
        for name in reversed(installed):
            child(dest, name).rename(child(rejected, name))
        for name in reversed(moved):
            child(backup, name).rename(child(dest, name))
        raise


def install(source, dest, python, replace_existing=False):
    state = state_dir(dest)
    with install_lock(state):
        previous = read_receipt(state)
        before = snapshot(dest)
        for name, actual in before.items():
            if actual is None:
                continue
            owned = previous and previous.get("destination") == str(dest) and actual == previous["files"][name]
            if not owned and not replace_existing:
                raise InstallError("{} exists outside this installer's unchanged files. Inspect it, then use --replace-existing to back it up and replace it.".format(dest / name))
        check_runtime(python)
        build_guards(source)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        transaction = state / "transactions" / stamp
        plain_path(transaction)
        stage = transaction / "staged"
        stage.mkdir(parents=True)
        prepare(source, stage, dest, python)
        after = {name: manifest(stage / name) for name in NAMES}
        smoke(stage, python)
        if before == after:
            # Keep the validated staging outside skill discovery. No installed
            # file is rewritten, and no extra backup is created on a no-op.
            return {"status": "unchanged", "skills": len(NAMES), "destination": str(dest)}
        commit = run(["git", "-C", source, "rev-parse", "HEAD"]).strip()
        dirty = bool(run(["git", "-C", source, "status", "--porcelain", "--untracked-files=normal"]).strip())
        receipt = {"schemaVersion": FORMAT, "owner": OWNER, "sourceCommit": commit,
                   "sourceDirty": dirty, "destination": str(dest), "python": str(python),
                   "files": after, "backup": str(transaction / "backup"), "installedAt": stamp}
        promote(stage, dest, transaction, before, after, receipt, state / "current.json")
        return {"status": "installed", "skills": len(NAMES), "sourceCommit": commit,
                "sourceDirty": dirty, "destination": str(dest), "backup": receipt["backup"],
                "receipt": str(state / "current.json"), "filesVerified": sum(len(m) for m in after.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path.home() / ".agents/skills", help="user skill directory (default: ~/.agents/skills)")
    parser.add_argument("--install-deps", action="store_true", help="create/reuse a private Python venv; pip requires network on first use")
    parser.add_argument("--python", type=Path, help="use an existing Python with the declared dependencies")
    parser.add_argument("--replace-existing", action="store_true", help="back up and replace colliding/unmanaged or locally edited AWT skill names")
    parser.add_argument("--dry-run", action="store_true", help="show scope/collisions without writing or downloading")
    parser.add_argument("--verify", action="store_true", help="verify saved hashes and exercise the installed helpers")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 9):
        parser.error("Python 3.9+ is required")
    if args.install_deps and args.python:
        parser.error("Choose --install-deps or --python")
    # abspath preserves junctions for inspection, unlike resolve().
    dest = Path(os.path.abspath(args.dest.expanduser()))
    plain_path(dest)
    for canonical in (SOURCE / ".claude/skills", SOURCE / ".agents/skills"):
        if dest == canonical or dest in canonical.parents or canonical in dest.parents:
            raise InstallError("Choose a user installation directory outside the canonical skill tree")
    state = state_dir(dest)
    if args.dry_run:
        print(json.dumps({"destination": str(dest), "skills": NAMES,
                          "existing": [n for n, value in snapshot(dest).items() if value is not None]}, indent=2))
        return 0
    if args.verify:
        receipt = read_receipt(state)
        verify(dest, receipt)
        print(json.dumps({"status": "verified", "skills": len(NAMES), "destination": str(dest)}))
        return 0
    if args.install_deps:
        with install_lock(state):
            python = private_runtime(SOURCE, state)
        forwarded = [str(SOURCE / "scripts/install-codex-skills.py"), "--dest", str(dest), "--python", str(python)]
        if args.replace_existing:
            forwarded.append("--replace-existing")
        return subprocess.call([str(python), *forwarded])
    python = Path(os.path.abspath(args.python.expanduser())) if args.python else Path(sys.executable).absolute()
    if python != Path(sys.executable).absolute():
        forwarded = [str(SOURCE / "scripts/install-codex-skills.py"), "--dest", str(dest)]
        if args.replace_existing:
            forwarded.append("--replace-existing")
        return subprocess.call([str(python), *forwarded])
    try:
        check_runtime(python)
    except InstallError as exc:
        raise InstallError("Python dependencies are missing. Retry with --install-deps, or --python pointing at a prepared environment.\n" + str(exc)) from exc
    print(json.dumps(install(SOURCE, dest, python, args.replace_existing), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallError, OSError, ValueError) as exc:
        print("AWT_SKILL_INSTALL: {}".format(exc), file=sys.stderr)
        raise SystemExit(1)
