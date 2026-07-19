#!/usr/bin/env python3
"""Build immutable source/plugin ZIPs and SHA256SUMS from one Git ref."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class ReleaseBuildError(RuntimeError):
    """Raised when a release artifact cannot be built safely."""


def run_git(repo_root: Path, *args: str, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise ReleaseBuildError(f"git {' '.join(args)} failed: {stderr}")
    return (result.stdout or "").strip()


def read_manifest_at_ref(repo_root: Path, ref: str) -> dict[str, object]:
    raw = run_git(
        repo_root,
        "show",
        f"{ref}:plugins/academic-writing-toolkit/.codex-plugin/plugin.json",
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseBuildError(f"plugin manifest at {ref} is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseBuildError("plugin manifest root must be an object")
    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_plugin_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    required = {
        "academic-writing-toolkit/.codex-plugin/plugin.json",
        "academic-writing-toolkit/assets/icon.png",
        "academic-writing-toolkit/assets/logo.png",
        "academic-writing-toolkit/assets/screenshot-workflow.png",
        "academic-writing-toolkit/assets/screenshot-progress.png",
    }
    missing = sorted(required - names)
    if missing:
        raise ReleaseBuildError(
            "plugin ZIP is missing required files: " + ", ".join(missing)
        )
    skill_files = {
        name
        for name in names
        if re.fullmatch(
            r"academic-writing-toolkit/skills/[^/]+/SKILL\.md",
            name,
        )
    }
    if len(skill_files) != 21:
        raise ReleaseBuildError(
            f"plugin ZIP must contain 21 top-level SKILL.md files, "
            f"found {len(skill_files)}"
        )


def build(
    repo_root: Path,
    ref: str,
    version: str,
    out_dir: Path,
    force: bool,
) -> list[Path]:
    if not VERSION_RE.fullmatch(version):
        raise ReleaseBuildError(f"invalid release version: {version}")
    commit = run_git(repo_root, "rev-parse", f"{ref}^{{commit}}")
    manifest = read_manifest_at_ref(repo_root, ref)
    if manifest.get("version") != version:
        raise ReleaseBuildError(
            f"manifest version at {ref} is {manifest.get('version')!r}, "
            f"expected {version!r}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    source_zip = out_dir / f"academic-writing-toolkit-v{version}.zip"
    plugin_zip = (
        out_dir / f"academic-writing-toolkit-openai-plugin-v{version}.zip"
    )
    sums = out_dir / "SHA256SUMS"
    outputs = [source_zip, plugin_zip, sums]
    existing = [path for path in outputs if path.exists()]
    if existing and not force:
        raise ReleaseBuildError(
            "refusing to overwrite existing artifact(s): "
            + ", ".join(path.name for path in existing)
        )

    run_git(
        repo_root,
        "archive",
        "--format=zip",
        f"--prefix=academic-writing-toolkit-v{version}/",
        f"--output={source_zip}",
        ref,
        capture=False,
    )
    run_git(
        repo_root,
        "archive",
        "--format=zip",
        "--prefix=academic-writing-toolkit/",
        f"--output={plugin_zip}",
        f"{ref}:plugins/academic-writing-toolkit",
        capture=False,
    )
    verify_plugin_zip(plugin_zip)
    sums.write_text(
        "\n".join(
            f"{sha256(path)}  {path.name}" for path in (source_zip, plugin_zip)
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "ref": ref,
                "commit": commit,
                "version": version,
                "artifacts": [
                    {
                        "path": str(path),
                        "sha256": sha256(path),
                    }
                    for path in (source_zip, plugin_zip)
                ],
                "checksums": str(sums),
            },
            indent=2,
        )
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build source/plugin release ZIPs from one Git ref."
    )
    parser.add_argument("--ref", required=True, help="immutable Git ref to archive")
    parser.add_argument("--version", required=True, help="release version without v")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("dist"),
        help="artifact output directory (default: dist)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace existing named artifacts",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    out_dir = (
        args.out_dir
        if args.out_dir.is_absolute()
        else (repo_root / args.out_dir)
    ).resolve()
    try:
        build(repo_root, args.ref, args.version, out_dir, args.force)
    except ReleaseBuildError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
