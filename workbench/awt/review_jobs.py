"""Durable local batch reviews. No network request is made by import or restore."""

from __future__ import annotations

import base64
import copy
import difflib
import io
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from awt.cross_review import (CHECK_SCHEMA, INSTRUCTIONS, block_map, budget_settings, claim_index,
    chapter_steps, completed_steps, coverage_table, cross_steps, input_estimate, source_payload,
    step_cache_key, step_materials, text_steps, validate_review, grounded_request,
    decode_grounded_review, SOURCE_SCHEMA, GROUNDING_PROTOCOL)
from awt.documents import (DocumentError, MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, decode_upload,
    digest, import_document, render_pdf_page)
from awt.providers import ModelResult, ProviderConfig, ProviderError, load_provider_config, run_api
from awt.review_index import block_identity, chapter_nodes, fingerprint, remap_result

ID_RE = re.compile(r"^[0-9a-f]{32}$")
ACTIVE = {"running", "pause_requested", "cancel_requested"}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    envelope = json.dumps({"sha256": digest(encoded), "data": value}, ensure_ascii=False).encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, prefix=".checkpoint-") as temporary:
        temporary.write(envelope)
        temporary.flush()
        os.fsync(temporary.fileno())
        name = Path(temporary.name)
    try:
        os.replace(name, path)
    finally:
        if name.exists():
            name.unlink()


def read_json(path: Path):
    try:
        if path.stat().st_size > 90_000_000:
            raise ValueError()
        envelope = json.loads(path.read_text(encoding="utf-8"))
        value = envelope["data"]
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if digest(encoded) != envelope["sha256"]:
            raise ValueError()
        return value
    except (OSError, ValueError, KeyError, TypeError):
        raise DocumentError("任务检查点缺失或校验失败；没有重新发起模型请求") from None


def _root_lock(root: Path):
    handle = (root / ".worker.lock").open("a+b")
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise DocumentError("该任务目录已被另一个工作台使用；请回到原工作台或选择不同的会话目录") from None
    return handle


def default_call(config, instructions, context, schema, images):
    sources = None
    if not images:
        instructions, context, sources = grounded_request(context)
        schema = SOURCE_SCHEMA
    elif config.provider != "codex":
        # Keep the existing image contract on its portable prompt transport.
        config = replace(config, response_format="prompt")

    def record_wire(response):
        response.review_wire = dict(response)
        response.metadata.update(review_protocol=GROUNDING_PROTOCOL,
            source_map_sha256=fingerprint(sources), wire_response_sha256=fingerprint(dict(response)))
    if config.provider == "codex":
        from awt.mvp import codex_json_runner
        started = time.monotonic()
        value = codex_json_runner(instructions + "\n<source>\n" + context + "\n</source>", schema,
                                 model=config.model or None, timeout=config.timeout_seconds)
        response = ModelResult(value, {**config.public_metadata(), "elapsed_seconds": round(time.monotonic() - started, 3),
                                  "usage": {}, "returned_model": None, "output_limit_enforced_by_transport": False})
    else:
        try:
            response = run_api(config, instructions, context, schema, images=images)
        except ProviderError as error:
            if sources is not None and isinstance(getattr(error, "model_result", None), ModelResult):
                if getattr(error.model_result, "complete_json_object", False):
                    record_wire(error.model_result)
                else:
                    error.model_result.metadata.update(review_protocol=GROUNDING_PROTOCOL,
                        source_map_sha256=fingerprint(sources), rejected_response_parseable=False)
            raise
    if sources is None:
        return response
    record_wire(response)
    try:
        decoded = decode_grounded_review(response, sources)
    except ProviderError as error:
        error.model_result = response  # Retain measured usage and the rejected choices.
        raise
    result = ModelResult(decoded, response.metadata)
    result.review_wire = response.review_wire
    return result


class JobManager:
    def __init__(self, root: Path, *, call=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._file_lock = _root_lock(self.root)
        self.lock = threading.RLock()
        self.workers = {}
        self.materials_cache = {}
        self.call = call or default_call
        self.closed = False
        # A process restart never retries an in-flight, potentially charged call.
        for directory in self.root.iterdir():
            if directory.is_dir() and ID_RE.fullmatch(directory.name):
                try:
                    job = self._load(directory.name)
                except DocumentError:
                    continue
                if job["state"] in ACTIVE:
                    job["state"] = "interrupted"
                    for step in job["steps"]:
                        if step["status"] == "running":
                            step["status"] = "uncertain"
                            step["attempts"][-1]["status"] = "outcome_unknown"
                    if "pending_goal" in job:
                        self._apply_steering(job)
                    self._save(job)
                elif "pending_goal" in job:
                    self._apply_steering(job)
                    self._save(job)
                if any(r.get("state") in {"preparing", "running", "pause_requested", "cancel_requested"} for r in job["layouts"]):
                    for report in job["layouts"]:
                        if report.get("state") in {"preparing", "running", "pause_requested", "cancel_requested"}:
                            report.update(state="interrupted", updated_at=now())
                    self._save(job)
                if job.get("submission", {}).get("state") in {"running", "cancel_requested"}:
                    job["submission"].update(state="interrupted", progress="上次本地校验中断，可重新运行；不会调用模型")
                    self._save(job)
        from awt.layout_jobs import LayoutManager
        self.layout_manager = LayoutManager(self)
        from awt.submission_jobs import SubmissionManager
        self.submission_manager = SubmissionManager(self)

    def _directory(self, identifier):
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
            raise DocumentError("任务 ID 无效")
        path = self.root / identifier
        if path.is_symlink() or path.resolve().parent != self.root.resolve():
            raise DocumentError("任务路径无效")
        return path

    def _load(self, identifier):
        value = read_json(self._directory(identifier) / "job.json")
        if value.get("schema_version") not in {1, 2} or value.get("id") != identifier:
            raise DocumentError("任务版本或 ID 不匹配")
        if value.get("materials_ref"):
            ref = value["materials_ref"]
            if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{64}", ref):
                raise DocumentError("材料索引无效")
            key = (identifier, ref)
            if key not in self.materials_cache:
                materials = read_json(self._directory(identifier) / ("materials-" + ref + ".json"))
                if fingerprint(materials) != ref:
                    raise DocumentError("材料索引哈希不匹配")
                if len(self.materials_cache) >= 4:
                    self.materials_cache.pop(next(iter(self.materials_cache)))
                self.materials_cache[key] = materials
            value["documents"] = self.materials_cache[key]
        return value

    def _save(self, job):
        job["updated_at"] = now()
        if not job.get("materials_ref"):
            ref = fingerprint(job["documents"])
            atomic_json(self._directory(job["id"]) / ("materials-" + ref + ".json"), job["documents"])
            job["materials_ref"] = ref
            key = (job["id"], ref)
            if key not in self.materials_cache and len(self.materials_cache) >= 4:
                self.materials_cache.pop(next(iter(self.materials_cache)))
            self.materials_cache[key] = job["documents"]
        job["schema_version"] = 2
        atomic_json(self._directory(job["id"]) / "job.json", {key: value for key, value in job.items()
            if key != "documents" and not key.startswith("_")})

    def _plan(self, job):
        calls = tokens = 0
        reused = 0
        for step in job["steps"]:
            if step["status"] == "completed":
                reused += bool(step.get("reused_from"))
                continue
            calls += 1
            if "estimated_reservation" not in step or step.get("reservation_protocol") != GROUNDING_PROTOCOL:
                step["estimated_reservation"] = input_estimate(step_materials(job, step), job["goal"], step["phase"]) + job["budget"]["output_tokens"] + 1024 * len(step.get("image_ids", []))
                step["reservation_protocol"] = GROUNDING_PROTOCOL
            tokens += step["estimated_reservation"]
        job["plan"] = {"pending_calls": calls, "pending_token_reservation": tokens, "reused_batches": reused,
            "future_stages_pending": not job.get("cross_built", False),
            "note": "此处为已规划批次估算；章节汇总和跨章节检索在前序结果保存后规划，仍受同一总预算约束。"}

    def _source(self, job, document):
        path = self._directory(job["id"]) / (document["id"] + ".bin")
        data = path.read_bytes()
        if digest(data) != document["sha256"]:
            raise DocumentError("材料哈希已改变；停止任务以防跨版本混用")
        return data

    def _upload_path(self, identifier):
        if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
            raise DocumentError("上传 ID 无效")
        root = self.root / "_uploads"
        root.mkdir(exist_ok=True, mode=0o700)
        path = root / identifier
        if path.is_symlink() or path.resolve().parent != root.resolve():
            raise DocumentError("上传路径无效")
        return path

    def upload_start(self, payload):
        name, _ = decode_upload({"filename": payload.get("filename"), "content_base64": "eA=="})
        size = payload.get("size")
        if type(size) is not int or not 1 <= size <= MAX_FILE_BYTES:
            raise DocumentError("单份材料需为 1 字节至 80 MB")
        identifier = os.urandom(16).hex()
        path = self._upload_path(identifier)
        path.write_bytes(b"")
        atomic_json(path.with_suffix(".json"), {"filename": name, "size": size, "created_at": now()})
        return {"upload_id": identifier, "offset": 0, "chunk_bytes": 1_000_000}

    def upload_chunk(self, payload):
        with self.lock:
            path = self._upload_path(payload.get("upload_id"))
            meta = read_json(path.with_suffix(".json"))
            offset, encoded = payload.get("offset"), payload.get("content_base64")
            if type(offset) is not int or offset < 0 or not isinstance(encoded, str) or len(encoded) > 1_400_000:
                raise DocumentError("上传分段或偏移无效")
            try:
                data = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise DocumentError("上传分段不是有效 base64") from None
            if not data or len(data) > 1_000_000 or offset + len(data) > meta["size"]:
                raise DocumentError("上传分段超过声明大小")
            size = path.stat().st_size
            with path.open("r+b") as handle:
                if offset < size:
                    handle.seek(offset)
                    if handle.read(len(data)) != data:
                        raise DocumentError("重复上传的分段内容不一致")
                elif offset == size:
                    handle.seek(size)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                else:
                    raise DocumentError("上传缺少前序分段")
            return {"upload_id": payload["upload_id"], "offset": path.stat().st_size, "complete": path.stat().st_size == meta["size"]}

    def decode_material(self, payload):
        if isinstance(payload, dict) and "upload_id" in payload:
            path = self._upload_path(payload["upload_id"])
            meta = read_json(path.with_suffix(".json"))
            if not path.is_file() or path.stat().st_size != meta["size"]:
                raise DocumentError("文件尚未上传完整")
            return meta["filename"], path.read_bytes()
        return decode_upload(payload)

    def discard_uploads(self, uploads):
        """Remove only temporary upload copies after durable source copies exist."""
        for item in uploads:
            if isinstance(item, dict) and "upload_id" in item:
                path = self._upload_path(item["upload_id"])
                for target in (path, path.with_suffix(".json")):
                    if target.is_file():
                        target.unlink()

    def page(self, payload):
        """Bounded detail fetch; ordinary progress polling never returns the source."""
        with self.lock:
            job = self._load(payload.get("job_id"))
            offset, limit = payload.get("offset", 0), payload.get("limit", 30)
            if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
                raise DocumentError("分页参数无效")
            kind = payload.get("kind", "blocks")
            documents = {d["id"]: d for d in job["documents"]}
            blocks = block_map(job)
            checked = {i for s in completed_steps(job) if s["phase"] == "text" for i in s["block_ids"]}
            nodes = chapter_nodes(job)
            selected_node = next((n for n in nodes if n["id"] == payload.get("chapter_id")), None)
            selected_ids = set(selected_node["block_ids"]) if selected_node else None
            if payload.get("chapter_id") and selected_node is None:
                raise DocumentError("章节定位无效")
            if kind in {"blocks", "unchecked", "locator"}:
                items = list(blocks.values())
                if kind == "unchecked":
                    items = [b for b in items if b["id"] not in checked]
                if kind == "locator":
                    items = [b for b in items if b["id"] == payload.get("locator")]
                if selected_ids is not None:
                    items = [b for b in items if b["id"] in selected_ids]
                if payload.get("document_id"):
                    items = [b for b in items if b["document_id"] == payload["document_id"]]
                if payload.get("section"):
                    items = [b for b in items if b["section"] == payload["section"]]
                if payload.get("cross_pair") is not None:
                    rows = job["cross_coverage"]
                    index = payload["cross_pair"]
                    if type(index) is not int or not 0 <= index < len(rows):
                        raise DocumentError("跨章节范围无效")
                    omitted = set(rows[index]["omitted"])
                    items = [b for b in items if b["id"] in omitted]
                search = payload.get("search", "")
                if not isinstance(search, str) or len(search) > 200:
                    raise DocumentError("搜索内容过长")
                if search:
                    items = [b for b in items if search.casefold() in b["text"].casefold() or search.casefold() in b["locator"].casefold()]
                total = len(items)
                items = [{**{k:v for k,v in b.items() if k != "source_spans" or kind == "locator"},
                          "text": b["text"] if kind == "locator" else b["text"][:500],
                          "location": documents[b["document_id"]]["filename"] + " · " + b["locator"],
                          "status": "text_reviewed" if b["id"] in checked else "not_checked",
                          "preview_asset_id": b["document_id"] + f":page{b['page']}" if b["page"] else None}
                         for b in items[offset:offset + limit]]
            elif kind == "assets":
                image_checked = {i for s in completed_steps(job) if s["phase"] == "vision" for i in s["image_ids"]}
                all_items = [{**{k:v for k,v in a.items() if k not in {"blob", "data_base64"}}, "filename": d["filename"],
                    "location": d["filename"] + " · " + a["locator"], "status": "image_reviewed" if a["id"] in image_checked else "not_checked",
                    "selected": a["id"] in job["selected_image_ids"]} for d in job["documents"] for a in d["assets"]
                    if not payload.get("document_id") or d["id"] == payload["document_id"]]
                total, items = len(all_items), all_items[offset:offset + limit]
            elif kind in {"coverage", "cross"}:
                all_items = coverage_table(job) if kind == "coverage" else copy.deepcopy(job["cross_coverage"])
                done_ids = {s["id"] for s in completed_steps(job)}
                for index, item in enumerate(all_items):
                    if kind == "coverage":
                        item["unchecked_count"] = len(item["unchecked"])
                        item["unchecked"] = []
                    else:
                        ids = item.get("step_ids", [item["step_id"]] if item.get("step_id") else [])
                        item["pair_index"] = index
                        item["included_count"], item["omitted_count"] = len(item["included"]), len(item["omitted"])
                        item["completed_batches"], item["total_batches"] = sum(i in done_ids for i in ids), len(ids)
                        if ids:
                            item["status"] = "anchors_reviewed" if all(i in done_ids for i in ids) else "partial" if any(i in done_ids for i in ids) else "pending"
                        item["included"], item["omitted"] = [], []
                total, items = len(all_items), all_items[offset:offset + limit]
            elif kind == "chapters":
                total = len(nodes)
                items = [{k:v for k,v in node.items() if k not in {"block_ids", "pages", "content_hash"}} for node in nodes[offset:offset + limit]]
                for item in items:
                    item["summaries"] = [{"step_id": s["id"], "summary": s["result"]["summary"]} for s in completed_steps(job)
                        if s["phase"] == "chapter" and item["id"] in s.get("scope_chapters", [])]
            elif kind in {"claims", "findings", "steps", "history"}:
                if kind == "claims":
                    all_items = claim_index(job)
                elif kind == "findings":
                    all_items = [{**finding, "step_id": s["id"]} for s in completed_steps(job) for finding in s["result"]["findings"]]
                else:
                    all_items = [{k:s[k] for k in ("id", "phase", "label", "status", "attempts", "revision", "reused_from") if k in s}
                                 for s in job["history"] if kind == "history"] if kind == "history" else [
                        {k:s[k] for k in ("id", "phase", "label", "status", "attempts", "revision", "reused_from") if k in s} for s in job["steps"]]
                if selected_ids is not None and kind in {"claims", "findings"}:
                    all_items = [item for item in all_items if item.get("locator") in selected_ids or
                        any(a["locator"] in selected_ids for a in item.get("anchors", []))]
                total, items = len(all_items), copy.deepcopy(all_items[offset:offset + limit])
                def annotate(value):
                    if isinstance(value, dict):
                        if value.get("locator") in blocks:
                            b = blocks[value["locator"]]
                            value["location"] = documents[b["document_id"]]["filename"] + " · " + b["locator"]
                        for child in list(value.values()):
                            annotate(child)
                    elif isinstance(value, list):
                        for child in value:
                            annotate(child)
                annotate(items)
            else:
                raise DocumentError("未知的分页内容")
            return {"items": items, "total": total, "offset": offset, "limit": limit,
                    "revision": job["revision"], "updated_at": job["updated_at"], "job_id": job["id"], "kind": kind}

    def create(self, payload):
        uploads = payload.get("files")
        if not isinstance(uploads, list) or not 1 <= len(uploads) <= MAX_FILES:
            raise DocumentError("请选择 1–20 份材料")
        decoded = [self.decode_material(item) for item in uploads]
        if sum(len(data) for _, data in decoded) > MAX_TOTAL_BYTES:
            raise DocumentError("材料总大小上限为 160 MB")
        if len({name for name, _ in decoded}) != len(decoded):
            raise DocumentError("材料文件名必须唯一，便于跨文件定位")
        goal = payload.get("goal", "检查摘要、方法、结果、讨论及图表之间的一致性")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 1500:
            raise DocumentError("审阅要求需要 1–1500 个字符")
        budget = budget_settings(payload.get("budget", {}))
        config = load_provider_config()
        # Local Ollama can constrain the new source-choice schema at generation.
        # Explicit transport configuration remains authoritative; older API models
        # keep the portable prompt default and no fallback request is made.
        response_format = config.response_format if "AWT_RESPONSE_FORMAT" in os.environ else (
            "json_schema" if config.provider in {"codex", "ollama"} else "prompt")
        config = replace(config, max_output_tokens=min(config.max_output_tokens, budget["output_tokens"]),
                         response_format=response_format)
        budget["output_tokens"] = config.max_output_tokens
        documents = [import_document(name, data) for name, data in decoded]
        steps = text_steps(documents, budget, goal, 1)
        identifier = os.urandom(16).hex()
        directory = self._directory(identifier)
        directory.mkdir(mode=0o700)
        for document, (_, data) in zip(documents, decoded):
            (directory / (document["id"] + ".bin")).write_bytes(data)
            for asset in document["assets"]:
                value = asset.pop("data_base64", None)
                if value:
                    asset["blob"] = digest(asset["id"].encode()) + ".image"
                    (directory / asset["blob"]).write_bytes(base64.b64decode(value))
        job = {"schema_version": 2, "planning_version": 3, "id": identifier, "created_at": now(), "updated_at": now(), "state": "draft", "revision": 1,
            "goal": goal.strip(), "budget": budget, "config": asdict(config), "documents": documents, "steps": steps, "history": [],
            "cross_built": False, "chapter_built": False, "cross_coverage": [], "selected_image_ids": [], "events": [], "layouts": [],
            "calls_reserved": 0, "tokens_reserved": 0, "error": None, "source_unchanged": True}
        self._plan(job)
        with self.lock:
            self._save(job)
            self.discard_uploads(uploads)
        return self.snapshot(identifier, compact=payload.get("compact") is True)

    def list_jobs(self):
        with self.lock:
            rows = []
            for path in self.root.iterdir():
                if path.is_dir() and ID_RE.fullmatch(path.name):
                    try:
                        job = self._load(path.name)
                        rows.append({"id": job["id"], "state": job["state"], "goal": job["goal"], "updated_at": job["updated_at"],
                                     "filenames": [doc["filename"] for doc in job["documents"]]})
                    except DocumentError:
                        rows.append({"id": path.name, "state": "corrupt", "goal": "检查点不可读", "updated_at": "", "filenames": []})
            return {"jobs": sorted(rows, key=lambda row: row["updated_at"], reverse=True)[:100]}

    def snapshot(self, identifier, *, compact=False):
        with self.lock:
            job = self._load(identifier)
            value = {key: copy.deepcopy(job[key]) for key in ("id", "state", "goal", "revision", "budget", "updated_at", "error", "events", "layouts", "source_unchanged", "calls_reserved", "tokens_reserved")}
            value["model"] = ProviderConfig(**job["config"]).public_metadata()
            value["compact"] = compact
            value["plan"] = {**job.get("plan", {}),
                "pending_calls": sum(s["status"] != "completed" for s in job["steps"]),
                "pending_token_reservation": sum(s.get("estimated_reservation", 0) for s in job["steps"] if s["status"] != "completed"),
                "reused_batches": sum(bool(s.get("reused_from")) for s in job["steps"]),
                "future_stages_pending": not job["cross_built"]}
            value["revision_change"] = copy.deepcopy(job.get("revision_change", {}))
            value["selection_open"] = job["state"] == "draft"
            value["submission"] = self.submission_manager.summary(job)
            value["coverage"] = coverage_table(job)
            value["claims"] = claim_index(job)
            value["cross_coverage"] = copy.deepcopy(job["cross_coverage"])
            done = completed_steps(job)
            completed_ids = {step["id"] for step in done}
            for row in value["cross_coverage"]:
                if row.get("step_id") in completed_ids:
                    row["status"] = "anchors_reviewed"
                if row.get("step_ids"):
                    done_count = sum(i in completed_ids for i in row["step_ids"])
                    row["completed_batches"], row["total_batches"] = done_count, len(row["step_ids"])
                    row["status"] = "anchors_reviewed" if done_count == len(row["step_ids"]) else "partial" if done_count else "pending"
            value["findings"] = [{**finding, "step_id": step["id"]} for step in done for finding in step["result"]["findings"]]
            value["limitations"] = list(dict.fromkeys(item for step in done for item in step["result"]["limitations"]))
            value["steps"] = [{**{key: step[key] for key in ("id", "phase", "label", "status")},
                "attempts": [{key: item for key, item in attempt.items() if key != "review_wire"}
                             for attempt in step["attempts"]]} for step in job["steps"]]
            value["progress"] = {"completed": len(done), "planned": len(job["steps"]), "cross_pending_planning": not job["cross_built"],
                                 "active": next((step["label"] for step in job["steps"] if step["status"] == "running"), None)}
            image_checked = {image for step in done if step["phase"] == "vision" for image in step["image_ids"]}
            value["documents"] = []
            for document in job["documents"]:
                public = {key: copy.deepcopy(document[key]) for key in ("id", "filename", "format", "warnings", "sha256", "size_bytes")}
                public["pages"] = [] if compact else copy.deepcopy(document["pages"])
                public["blocks"] = [] if compact else [{**block, "text": block["text"][:300]} for block in document["blocks"]]
                public["assets"] = [{**{key: item for key, item in asset.items() if key != "blob"},
                    "selected": asset["id"] in job["selected_image_ids"], "status": "image_reviewed" if asset["id"] in image_checked else "not_checked"} for asset in document["assets"]] if not compact else []
                public.update(block_count=len(document["blocks"]), asset_count=len(document["assets"]), page_count=len(document["pages"]))
                value["documents"].append(public)
            attempts = [attempt for step in job["steps"] + job["history"] for attempt in step["attempts"]]
            value["usage"] = [attempt.get("model_run", {}) for attempt in attempts if attempt.get("model_run")]
            value["uncertain_requests"] = sum(step["status"] == "uncertain" for step in job["steps"])
            rates = job["budget"]
            value["estimated_cost_reserved"] = None
            if rates["input_price_per_million"] is not None and rates["output_price_per_million"] is not None:
                value["estimated_cost_reserved"] = round(sum(attempt["input_estimate"] * rates["input_price_per_million"] + attempt["output_limit"] * rates["output_price_per_million"] for attempt in attempts) / 1_000_000, 6)
            value["cost_note"] = "调用次数包含失败或结果不明的请求；token 为本地预算估算，单价由作者填写，图像估算和 CLI 额外上下文可能有偏差。实际费用以服务商账单为准。"
            if compact:
                value["totals"] = {"claims": len(value["claims"]), "findings": len(value["findings"]), "steps": len(value["steps"]),
                    "blocks": sum(len(d["blocks"]) for d in job["documents"]), "assets": sum(len(d["assets"]) for d in job["documents"]),
                    "chapters": len(chapter_nodes(job)), "coverage": len(value["coverage"]), "cross": len(value["cross_coverage"])}
                for name in ("claims", "findings", "steps", "usage"):
                    value[name] = []
                for row in value["coverage"]:
                    row["unchecked_count"] = len(row["unchecked"])
                    row["unchecked"] = []
                for row in value["cross_coverage"]:
                    row["included_count"], row["omitted_count"] = len(row["included"]), len(row["omitted"])
                    row["included"], row["omitted"] = [], []
                value["coverage"], value["cross_coverage"] = [], []
                for document in value["documents"]:
                    document["blocks"], document["assets"], document["pages"] = [], [], []
                    document["warning_count"] = len(document["warnings"])
                    document["warnings"] = document["warnings"][:20]
                for layout in value["layouts"]:
                    layout.setdefault("state", "completed")
                    layout["rendered_count"] = sum(p.get("rendered", True) for p in layout["pages"])
                    layout["checked_count"] = sum(p["human_checked"] for p in layout["pages"])
                    layout["changed_count"] = sum(p["changed"] for p in layout["pages"] if p.get("rendered", True))
                    layout["planned_count"] = len(layout["pages"])
                    layout["pages"] = []
                value["events"] = value["events"][-20:]
                value["limitations"] = value["limitations"][:100]
            return value

    def _vision_steps(self, job):
        blocks = list(block_map(job).values())
        steps = []
        for image_id in job["selected_image_ids"]:
            document, asset = self._asset(job, image_id)
            candidates = sorted(blocks, key=lambda b: (b["kind"] in {"caption", "table", "chart_data"} and b["document_id"] == document["id"],
                b["role"] in {"abstract", "results", "discussion"}, b["page"] == asset["page"] and b["document_id"] == document["id"]), reverse=True)
            included = []
            for block in candidates[:60]:
                if input_estimate(included + [block], job["goal"], "vision") + 1024 <= job["budget"]["input_tokens"]:
                    included.append(block)
            steps.append({"id": f"r{job['revision']}-vision-{len(steps) + 1}", "phase": "vision", "label": document["filename"] + " / " + asset["locator"],
                          "block_ids": [block["id"] for block in included], "image_ids": [image_id], "revision": job["revision"], "status": "pending", "attempts": []})
        return steps

    def classify(self, payload):
        with self.lock:
            job = self._load(payload.get("job_id"))
            if job["state"] != "draft" or job["calls_reserved"]:
                raise DocumentError("章节类别只能在首次运行前调整")
            role = payload.get("role")
            if role not in {"abstract", "methods", "results", "discussion", "introduction", "references", "other"}:
                raise DocumentError("章节类别无效")
            job["documents"] = copy.deepcopy(job["documents"])
            matches = [block for block in block_map(job).values() if block["document_id"] == payload.get("document_id") and block["section"] == payload.get("section")]
            if not matches:
                raise DocumentError("未找到该章节")
            for block in matches:
                block["role"] = role
            job.pop("materials_ref", None)
            document = next(d for d in job["documents"] if d["id"] == payload["document_id"])
            job.setdefault("role_overrides", {}).setdefault(document["filename"], {})[payload["section"]] = role
            self._save(job)
        return self.snapshot(job["id"], compact=payload.get("compact") is True)

    def revise(self, payload):
        identifier = payload.get("job_id")
        uploads = payload.get("files")
        if not isinstance(uploads, list) or not 1 <= len(uploads) <= MAX_FILES:
            raise DocumentError("请选择要替换的同名文件")
        decoded = [self.decode_material(item) for item in uploads]
        if len({name for name, _ in decoded}) != len(decoded) or sum(len(data) for _, data in decoded) > MAX_TOTAL_BYTES:
            raise DocumentError("替换文件重名或总大小超限")
        with self.lock:
            previous = self._load(identifier)
            if previous["state"] in ACTIVE or any(w.is_alive() for w in self.workers.values()):
                raise DocumentError("请先暂停审阅，再替换材料")
            stamp = previous["updated_at"]
            names = {d["filename"] for d in previous["documents"]}
            if any(name not in names for name, _ in decoded):
                raise DocumentError("局部复查需要替换同名文件；新增材料请建立新任务")
        replacements = {name: import_document(name, data) for name, data in decoded}
        with self.lock:
            job = self._load(identifier)
            if job["updated_at"] != stamp:
                raise DocumentError("任务已发生变化；请重新提交替换文件")
            if all(replacements[d["filename"]]["sha256"] == d["sha256"] for d in job["documents"] if d["filename"] in replacements):
                self.discard_uploads(uploads)
                return self.snapshot(identifier, compact=payload.get("compact") is True)
            old_documents, old_steps = job["documents"], job["steps"]
            new_documents = [replacements.get(d["filename"], d) for d in old_documents]
            if sum(d["size_bytes"] for d in new_documents) > MAX_TOTAL_BYTES:
                raise DocumentError("替换后总大小超过 160 MB")
            mapping = {}
            for old, new in zip(old_documents, new_documents):
                if old["id"] == new["id"]:
                    mapping.update({b["id"]: b["id"] for b in old["blocks"]})
                    continue
                for block in new["blocks"]:
                    block["role"] = job.get("role_overrides", {}).get(new["filename"], {}).get(block["section"], block["role"])
                matcher = difflib.SequenceMatcher(None, [block_identity(b) for b in old["blocks"]],
                    [block_identity(b) for b in new["blocks"]], autojunk=False)
                for match in matcher.get_matching_blocks():
                    mapping.update({old["blocks"][match.a + i]["id"]: new["blocks"][match.b + i]["id"] for i in range(match.size)})
            job["documents"] = new_documents
            job.pop("materials_ref", None)
            job["history"].extend(old_steps)
            job["revision"] += 1
            available = block_map(job)
            positions = {b["id"]: index for d in new_documents for index, b in enumerate(d["blocks"])}
            reused, covered = [], set()
            for step in old_steps:
                if step["phase"] != "text" or step["status"] != "completed" or not step.get("cache_key") or not all(i in mapping for i in step["block_ids"]):
                    continue
                ids = [mapping[i] for i in step["block_ids"]]
                if any(positions[b] != positions[a] + 1 for a, b in zip(ids, ids[1:])):
                    continue
                candidate = {**copy.deepcopy(step), "id": f"r{job['revision']}-reuse-{len(reused)+1}",
                    "revision": job["revision"], "block_ids": ids, "attempts": [], "reused_from": {"revision": step["revision"], "step_id": step["id"]}}
                if step_cache_key(job, candidate) != step["cache_key"]:
                    continue
                candidate["result"] = validate_review(remap_result(step["result"], mapping), [available[i] for i in ids])
                reused.append(candidate)
                covered.update(ids)
            pending_documents = [{**d, "blocks": [b for b in d["blocks"] if b["id"] not in covered]} for d in new_documents]
            job["steps"] = reused + text_steps(pending_documents, job["budget"], job["goal"], job["revision"])
            retained_assets = {a["id"] for d in new_documents for a in d["assets"]}
            job["selected_image_ids"] = [i for i in job["selected_image_ids"] if i in retained_assets]
            job["steps"].extend(self._vision_steps(job))
            job.update(state="paused", chapter_built=False, cross_built=False, cross_coverage=[], error=None, planning_version=3)
            job["revision_change"] = {"at": now(), "unchanged_blocks": len(mapping), "reused_blocks": len(covered),
                "reused_batches": len(reused), "pending_blocks": len(available) - len(covered),
                "note": "仅复用相同要求、配置和整批文字下的结果；受影响章节及关联检查重新规划。修改文件的图像需在新任务中重新选择。"}
            for document in new_documents:
                if document["filename"] in replacements:
                    data = next(data for name, data in decoded if name == document["filename"])
                    (self._directory(identifier) / (document["id"] + ".bin")).write_bytes(data)
                    for asset in document["assets"]:
                        value = asset.pop("data_base64", None)
                        if value:
                            asset["blob"] = digest(asset["id"].encode()) + ".image"
                            (self._directory(identifier) / asset["blob"]).write_bytes(base64.b64decode(value))
            job["events"].append({"at": now(), "action": "revise", "revision": job["revision"], "filenames": list(replacements)})
            self._plan(job)
            self._save(job)
            self.discard_uploads(uploads)
        return self.snapshot(identifier, compact=payload.get("compact") is True)

    def start(self, payload):
        identifier = payload.get("job_id")
        with self.lock:
            if self.closed:
                raise DocumentError("工作台正在关闭")
            job = self._load(identifier)
            if job["state"] in ACTIVE or any(worker.is_alive() for worker in self.workers.values()):
                raise DocumentError("已有任务正在运行；请等待或暂停后再继续")
            if any(step["status"] == "uncertain" for step in job["steps"]) and payload.get("retry_uncertain") is not True:
                raise DocumentError("存在结果不明、可能已计费的请求；需要明确选择重试后才能继续")
            for key in ("max_calls", "total_tokens"):
                if key in payload:
                    job["budget"] = budget_settings({**job["budget"], key: payload[key]})
            if job["state"] == "draft":
                selected = payload.get("image_ids", [])
                if not isinstance(selected, list) or not all(isinstance(i, str) for i in selected) or len(selected) != len(set(selected)) or len(selected) > 200:
                    raise DocumentError("每轮最多明确选择 200 张图像或页面")
                for item in selected:
                    self._asset(job, item)
                if selected and not job["config"]["supports_images"]:
                    raise DocumentError("当前是文字模型配置；视觉审阅需另选支持图像的 API 模型并设置 AWT_SUPPORTS_IMAGES=1")
                job["selected_image_ids"] = selected
                job["steps"].extend(self._vision_steps(job))
            if not job["steps"]:
                raise DocumentError("没有可审阅的文字；请补充转写文本，或明确选择页面做视觉检查。排版对照仍可本地使用。")
            config = ProviderConfig(**job["config"])
            if config.provider != "codex" and self.call is default_call:
                config.api_key()  # Preflight before reserving a charged attempt.
            for document in job["documents"]:
                self._source(job, document)
            for step in job["steps"]:
                if step["status"] in {"failed", "uncertain"}:
                    step["status"] = "pending"
            job.update(state="running", error=None)
            self._plan(job)
            self._save(job)
            worker = threading.Thread(target=self._run, args=(identifier,), daemon=True, name="awt-review-" + identifier[:8])
            self.workers[identifier] = worker
            worker.start()
        return self.snapshot(identifier, compact=payload.get("compact") is True)

    def control(self, payload):
        identifier, action = payload.get("job_id"), payload.get("action")
        if action not in {"pause", "cancel", "steer"}:
            raise DocumentError("任务动作无效")
        with self.lock:
            job = self._load(identifier)
            if action == "steer":
                note = payload.get("goal")
                if not isinstance(note, str) or not note.strip() or len(note) > 1500:
                    raise DocumentError("补充后的要求需要 1–1500 个字符")
                if note.strip() == job["goal"]:
                    return self.snapshot(identifier, compact=payload.get("compact") is True)
                # Validate the revised plan before replacing the current contract.
                text_steps(job["documents"], job["budget"], note.strip(), job["revision"] + 1)
                job["pending_goal"] = note.strip()
                job["events"].append({"at": now(), "action": "steer", "goal": note.strip(), "prior_revision": job["revision"]})
                if job["state"] not in ACTIVE:
                    self._apply_steering(job)
                else:
                    job["state"] = "pause_requested"
            else:
                job["state"] = ("pause_requested" if action == "pause" else "cancel_requested") if job["state"] in ACTIVE else ("paused" if action == "pause" else "cancelled")
                job["events"].append({"at": now(), "action": action})
            self._save(job)
        return self.snapshot(identifier, compact=payload.get("compact") is True)

    def _apply_steering(self, job):
        if "pending_goal" not in job:
            return
        job["history"].extend(job["steps"])
        job["goal"] = job.pop("pending_goal")
        job["revision"] += 1
        job["steps"] = text_steps(job["documents"], job["budget"], job["goal"], job["revision"])
        job["steps"].extend(self._vision_steps(job))
        job.update(chapter_built=False, cross_built=False, cross_coverage=[], state="paused", planning_version=3)
        self._plan(job)

    def _reuse(self, job, step):
        if step["phase"] == "vision":
            return False
        key = step_cache_key(job, step)
        step["cache_key"] = key
        for old in reversed(job["history"]):
            if old["status"] != "completed" or old.get("cache_key") != key or len(old["block_ids"]) != len(step["block_ids"]):
                continue
            mapping = dict(zip(old["block_ids"], step["block_ids"]))
            result = validate_review(remap_result(old["result"], mapping), step_materials(job, step))
            step.update(status="completed", result=result, reused_from={"revision": old["revision"], "step_id": old["id"]})
            return True
        return False

    def _run(self, identifier):
        try:
            while True:
                with self.lock:
                    job = self._load(identifier)
                    if self.closed or job["state"] != "running":
                        if "pending_goal" in job:
                            self._apply_steering(job)
                        else:
                            job["state"] = "cancelled" if job["state"] == "cancel_requested" else "paused"
                        self._save(job)
                        return
                    pending = next((step for step in job["steps"] if step["status"] == "pending"), None)
                    if pending is None and not job.get("chapter_built", False):
                        extra = chapter_steps(job)
                        job["steps"].extend(extra)
                        job["chapter_built"] = True
                        self._plan(job)
                        pending = next(iter(extra), None)
                    if pending is None and not job["cross_built"]:
                        extra, coverage = cross_steps(job)
                        job["steps"].extend(extra)
                        job.update(cross_built=True, cross_coverage=coverage)
                        self._plan(job)
                        pending = next((step for step in extra), None)
                    if pending is None:
                        job["state"] = "completed"
                        self._save(job)
                        return
                    if self._reuse(job, pending):
                        self._save(job)
                        continue
                    blocks = step_materials(job, pending)
                    estimate = input_estimate(blocks, job["goal"], pending["phase"]) + 1024 * len(pending["image_ids"])
                    reserve = estimate + job["budget"]["output_tokens"]
                    if estimate > job["budget"]["input_tokens"] or job["calls_reserved"] >= job["budget"]["max_calls"] or job["tokens_reserved"] + reserve > job["budget"]["total_tokens"]:
                        job.update(state="budget_paused", error="已达到本轮调用或 token 预算；未检查内容仍保留在覆盖表。可调整总预算后继续。")
                        self._save(job)
                        return
                    images = [self._image(job, image_id) for image_id in pending["image_ids"]]
                    config = ProviderConfig(**job["config"])
                    step_id = pending["id"]
                    pending["status"] = "running"
                    pending["attempts"].append({"started_at": now(), "status": "in_flight", "input_estimate": estimate,
                                                "output_limit": job["budget"]["output_tokens"]})
                    job["calls_reserved"] += 1
                    job["tokens_reserved"] += reserve
                    self._save(job)  # Durable reservation before any network request.
                    context = source_payload(blocks, job["goal"], pending["phase"])
                    if images:
                        context += "\nImages in attachment order: " + ", ".join(pending["image_ids"])
                response = None
                try:
                    response = self.call(config, INSTRUCTIONS, context, CHECK_SCHEMA, images)
                    checked = validate_review(response, blocks, [item["id"] for item in images])
                    error = None
                except Exception as failure:
                    if isinstance(getattr(failure, "model_result", None), ModelResult):
                        response = failure.model_result
                    checked = None
                    error = str(failure) if isinstance(failure, (ProviderError, DocumentError)) else "模型请求或本地校验失败；当前批次没有计为已检查，可按需重试。"
                with self.lock:
                    job = self._load(identifier)
                    step = next(item for item in job["steps"] if item["id"] == step_id)
                    step["attempts"][-1].update(ended_at=now(), status="failed" if error else "completed")
                    if isinstance(response, ModelResult):
                        step["attempts"][-1]["model_run"] = response.metadata
                        if hasattr(response, "review_wire"):
                            step["attempts"][-1]["review_wire"] = response.review_wire
                    if error:
                        step["status"] = "failed"
                        job.update(state="failed", error=error)
                        if "pending_goal" in job:
                            self._apply_steering(job)
                        self._save(job)
                        return
                    step.update(status="completed", result=checked)
                    self._save(job)
        except Exception as failure:
            with self.lock:
                try:
                    job = self._load(identifier)
                    for step in job["steps"]:
                        if step["status"] == "running":
                            step["status"] = "uncertain"
                            step["attempts"][-1]["status"] = "outcome_unknown"
                    job.update(state="failed", error=str(failure) if isinstance(failure, DocumentError) else "任务保存或材料处理失败；请保留检查点后重试。")
                    self._save(job)
                except Exception:
                    pass  # The previous durable in-flight marker remains recoverable.

    def _asset(self, job, identifier):
        for document in job["documents"]:
            for asset in document["assets"]:
                if asset["id"] == identifier:
                    return document, asset
        raise DocumentError("未找到所选图像定位")

    def _image(self, job, identifier):
        document, asset = self._asset(job, identifier)
        if asset["kind"] == "page":
            data = render_pdf_page(self._source(job, document), asset["page"])
        elif asset.get("blob"):
            data = (self._directory(job["id"]) / asset["blob"]).read_bytes()
            if digest(data) != asset["sha256"]:
                raise DocumentError("图像副本校验失败")
        else:
            raise DocumentError("该图像格式不能直接预览；请导出为 PNG/JPEG 或 PDF 页面")
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height > 40_000_000:
                    raise DocumentError("图像像素数过大；请提供缩小副本")
                image = image.convert("RGB")
                image.thumbnail((1280, 1280))
                output = io.BytesIO()
                image.save(output, format="PNG")
                data = output.getvalue()
        except ImportError:
            raise DocumentError('图像预览需要：python -m pip install ".[documents]"') from None
        except (OSError, ValueError):
            raise DocumentError("图像不能解码") from None
        return {"id": identifier, "mime_type": "image/png", "data_base64": base64.b64encode(data).decode()}

    def preview(self, payload):
        with self.lock:
            job = self._load(payload.get("job_id"))
        return self._image(job, payload.get("asset_id"))

    def layout(self, payload):
        return self.layout_manager.create(payload)

    def layout_control(self, payload):
        return self.layout_manager.control(payload)

    def layout_page(self, payload):
        return self.layout_manager.page(payload)

    def layout_preview(self, payload):
        if payload.get("side") not in {"before", "after"}:
            raise DocumentError("Invalid page side")
        return self.layout_manager.page(payload)[payload["side"]]

    def layout_check(self, payload):
        return self.layout_manager.check(payload)

    def close(self):
        self.closed = True
        self.layout_manager.close()
        self.submission_manager.close()
        for worker in list(self.workers.values()):
            worker.join(timeout=1)
        if not any(worker.is_alive() for worker in list(self.workers.values()) + list(self.layout_manager.workers.values()) + list(self.submission_manager.workers.values())) and not self._file_lock.closed:
            self._file_lock.close()
