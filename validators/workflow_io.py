"""Fail-closed local workflow I/O and apply-copy authority contract.

The workflow result is supplied by a registered AWT capability.  This module
does not choose a paper's research identity; it only binds inputs, proposals,
and an explicitly authorised new-copy write to exact bytes and paths.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Callable, Dict

MODES = {"inspect", "propose", "apply-copy"}
READ_ONLY_MODES = {"inspect", "propose"}


class WorkflowAuthorityError(ValueError):
    """Raised when a workflow request lacks exact authority or byte binding."""


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _nonempty(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise WorkflowAuthorityError(f"{label} must be a non-empty string")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WorkflowAuthorityError(f"{label} must be an object")
    return value


def _safe_regular_file(path: Path, label: str) -> Path:
    absolute = path.absolute()
    if not absolute.is_file() or absolute.is_symlink():
        raise WorkflowAuthorityError(f"{label} must be a regular non-symlink file")
    return absolute


def _source(request: Mapping[str, object]) -> tuple[Path, bytes, str]:
    source = _mapping(request.get("source"), "source")
    path = _safe_regular_file(Path(_nonempty(source.get("path"), "source.path")), "source.path")
    expected = _nonempty(source.get("sha256"), "source.sha256")
    data = path.read_bytes()
    observed = _digest(data)
    if observed != expected:
        raise WorkflowAuthorityError("source SHA-256 mismatch")
    return path, data, observed


def _proposal(request: Mapping[str, object]) -> tuple[str, bytes, str]:
    proposal = _mapping(request.get("proposal"), "proposal")
    replacement = _nonempty(proposal.get("replacement_text"), "proposal.replacement_text")
    data = replacement.encode("utf-8")
    observed = _digest(data)
    expected = _nonempty(proposal.get("sha256"), "proposal.sha256")
    if observed != expected:
        raise WorkflowAuthorityError("proposal SHA-256 mismatch")
    return replacement, data, observed


def _validate_authorisation(
    request: Mapping[str, object],
    *,
    mode: str,
    source_hash: str,
    proposal_hash: str,
    target: Path,
) -> Mapping[str, object]:
    authority = _mapping(request.get("authorisation"), "authorisation")
    required = {
        "authorised",
        "author_id",
        "authorised_at",
        "mode",
        "source_sha256",
        "proposal_sha256",
        "target_path",
    }
    if set(authority) != required:
        raise WorkflowAuthorityError("authorisation fields must match the write contract")
    if authority.get("authorised") is not True:
        raise WorkflowAuthorityError("write requires explicit authorisation")
    _nonempty(authority.get("author_id"), "authorisation.author_id")
    _nonempty(authority.get("authorised_at"), "authorisation.authorised_at")
    if authority.get("mode") != mode:
        raise WorkflowAuthorityError("authorisation mode mismatch")
    if authority.get("source_sha256") != source_hash:
        raise WorkflowAuthorityError("authorisation source hash mismatch")
    if authority.get("proposal_sha256") != proposal_hash:
        raise WorkflowAuthorityError("authorisation proposal hash mismatch")
    authorised_target = Path(
        _nonempty(authority.get("target_path"), "authorisation.target_path")
    ).absolute()
    if authorised_target != target:
        raise WorkflowAuthorityError("authorisation target path mismatch")
    return authority


def _atomic_write(path: Path, data: bytes) -> None:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise WorkflowAuthorityError("target parent must be an existing regular directory")
    descriptor, temporary = tempfile.mkstemp(prefix=".awt-write-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def run_workflow(
    request: Mapping[str, object],
    analyse: Callable[[str, Mapping[str, object]], Mapping[str, object]] | None = None,
) -> Dict[str, object]:
    """Execute one byte-bound workflow request.

    ``inspect`` and ``propose`` call ``analyse`` and cannot write. ``apply-copy``
    applies an already reviewed full-text proposal to a new path. The public
    runtime intentionally has no source-overwrite mode.
    """

    request = _mapping(request, "request")
    if request.get("schema_version") != 1:
        raise WorkflowAuthorityError("schema_version must be 1")
    request_id = _nonempty(request.get("request_id"), "request_id")
    mode = _nonempty(request.get("mode"), "mode")
    if mode not in MODES:
        raise WorkflowAuthorityError("invalid workflow mode")
    _nonempty(request.get("workflow_id"), "workflow_id")
    source_path, source_bytes, source_hash = _source(request)

    if mode in READ_ONLY_MODES:
        if request.get("target_path") is not None or request.get("authorisation") is not None:
            raise WorkflowAuthorityError("read-only modes cannot include write authority")
        if analyse is None:
            raise WorkflowAuthorityError("read-only workflow requires an analyser")
        result = dict(_mapping(analyse(source_bytes.decode("utf-8"), request), "result"))
        result.setdefault("status", "warn")
        _nonempty(request.get("requested_at"), "requested_at")
        after = source_path.read_bytes()
        if after != source_bytes:
            raise WorkflowAuthorityError("read-only workflow modified source bytes")
        return {
            "schema_version": 1,
            "request_id": request_id,
            "mode": mode,
            "source": {"path": str(source_path), "sha256": source_hash},
            "source_unchanged": True,
            "write_performed": False,
            "target": None,
            "result": result,
        }

    _replacement, replacement_bytes, proposal_hash = _proposal(request)
    target = Path(_nonempty(request.get("target_path"), "target_path")).absolute()
    if target == source_path:
        raise WorkflowAuthorityError("apply-copy target must differ from source")
    if target.exists() or target.is_symlink():
        raise WorkflowAuthorityError("apply-copy target must be a new file")
    authority = _validate_authorisation(
        request,
        mode=mode,
        source_hash=source_hash,
        proposal_hash=proposal_hash,
        target=target,
    )
    _atomic_write(target, replacement_bytes)
    observed_target_hash = _digest(target.read_bytes())
    if observed_target_hash != proposal_hash:
        raise WorkflowAuthorityError("written target hash mismatch")
    if source_path.read_bytes() != source_bytes:
        raise WorkflowAuthorityError("apply-copy modified source bytes")
    return {
        "schema_version": 1,
        "request_id": request_id,
        "mode": mode,
        "source": {"path": str(source_path), "sha256": source_hash},
        "source_unchanged": True,
        "write_performed": True,
        "target": {"path": str(target), "sha256": observed_target_hash},
        "authority": {
            "status": "validated",
            "author_id": authority["author_id"],
            "authorised_at": authority["authorised_at"],
            "scope": [str(target)],
            "source_sha256": source_hash,
            "proposal_sha256": proposal_hash,
        },
    }
