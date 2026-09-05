"""Page-at-a-time local layout comparison, resumable without paid requests."""
from __future__ import annotations

import base64
import os
import threading

from awt.documents import DocumentError, as_pdf, compare_pdf_page, digest, pdf_page_info
from awt.review_jobs import now

ACTIVE = {"preparing", "running", "pause_requested", "cancel_requested"}


def write_file(path, data):
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class LayoutManager:
    def __init__(self, owner):
        self.owner = owner
        self.workers = {}
        self.closed = False

    def _report(self, job, identifier):
        report = next((r for r in job["layouts"] if r["id"] == identifier), None)
        if report is None:
            raise DocumentError("排版任务不存在")
        return report

    def _directory(self, job_id, layout_id):
        # Both IDs have been resolved from a hash-checked job, never a path input.
        return self.owner._directory(job_id) / ("layout-" + layout_id)

    def create(self, payload):
        owner, job_id = self.owner, payload.get("job_id")
        name, data = owner.decode_material(payload.get("revised"))
        with owner.lock:
            if self.closed or any(w.is_alive() for w in self.workers.values()):
                raise DocumentError("已有本地排版任务在运行，请先暂停或等待")
            job = owner._load(job_id)
            if len(job["layouts"]) >= 10:
                raise DocumentError("单个任务最多保存 10 组排版对照")
            doc = next((d for d in job["documents"] if d["id"] == payload.get("document_id")), None)
            if not doc or doc["format"] not in {"pdf", "docx"} or not name.lower().endswith((".pdf", ".docx")):
                raise DocumentError("排版对照需要已导入的 PDF/DOCX 和修改副本")
            start, end = payload.get("page_start", 1), payload.get("page_end")
            if type(start) is not int or not 1 <= start <= 1000 or (end is not None and (type(end) is not int or not start <= end <= 1000)):
                raise DocumentError("排版范围需要有效的 1–1000 页页码")
            identifier = os.urandom(16).hex()
            directory = self._directory(job_id, identifier)
            directory.mkdir(mode=0o700)
            write_file(directory / "revised.bin", data)
            report = {"id": identifier, "document_id": doc["id"], "before_document": {k:doc[k] for k in ("id", "sha256", "filename")},
                "before_filename": doc["filename"], "after_filename": name, "before_sha256": doc["sha256"], "after_sha256": digest(data),
                "state": "preparing", "status": "awaiting_human_review", "created_at": now(), "updated_at": now(),
                "page_start": start, "page_end": end, "before_pages": 0, "after_pages": 0, "pages": [], "error": None,
                "source_unchanged": True, "scope": "逐页像素变化、空白页和文字越界提示；需要人工核对图表、重叠、字体与分页。DOCX 的 LibreOffice 渲染可能不同于 Word。"}
            job["layouts"].append(report)
            owner._save(job)
            owner.discard_uploads([payload.get("revised")])
            worker = self._dispatch(job_id, identifier)
        if payload.get("background") is not True:
            worker.join()
        return owner.snapshot(job_id, compact=payload.get("compact") is True)

    def _dispatch(self, job_id, identifier):
        worker = threading.Thread(target=self._run, args=(job_id, identifier), daemon=True, name="awt-layout-" + identifier[:8])
        self.workers[identifier] = worker
        worker.start()
        return worker

    def control(self, payload):
        owner, job_id = self.owner, payload.get("job_id")
        with owner.lock:
            job = owner._load(job_id)
            report = self._report(job, payload.get("layout_id"))
            action = payload.get("action")
            if action == "resume":
                if self.closed or any(w.is_alive() for w in self.workers.values()):
                    raise DocumentError("本地排版任务尚未停止")
                report.update(state="running" if report.get("prepared") else "preparing", error=None)
            elif action in {"pause", "cancel"}:
                report["state"] = ("pause_requested" if action == "pause" else "cancel_requested") if report.get("state") in ACTIVE else ("paused" if action == "pause" else "cancelled")
            else:
                raise DocumentError("排版任务动作无效")
            report["updated_at"] = now()
            owner._save(job)
            if action == "resume":
                self._dispatch(job_id, report["id"])
        return owner.snapshot(job_id, compact=payload.get("compact") is True)

    def _run(self, job_id, identifier):
        owner = self.owner
        try:
            with owner.lock:
                job = owner._load(job_id)
                report = self._report(job, identifier)
                directory = self._directory(job_id, identifier)
                before_raw = owner._source(job, report["before_document"])
                revised = (directory / "revised.bin").read_bytes()
                if digest(revised) != report["after_sha256"]:
                    raise DocumentError("排版修改副本哈希不匹配")
                prepared = report.get("prepared", False)
            if not prepared:
                before, after = as_pdf(report["before_filename"], before_raw), as_pdf(report["after_filename"], revised)
                counts = [pdf_page_info(data)["page_count"] for data in (before, after)]
                end = min(report["page_end"] or max(counts), max(counts))
                if report["page_start"] > end:
                    raise DocumentError("所选排版范围超出文档页数")
                write_file(directory / "before.pdf", before)
                write_file(directory / "after.pdf", after)
                with owner.lock:
                    job = owner._load(job_id)
                    report = self._report(job, identifier)
                    report.update(prepared=True, before_pages=counts[0], after_pages=counts[1], page_end=end,
                        before_render_sha256=digest(before), after_render_sha256=digest(after),
                        pages=[{"page": n, "rendered": False, "changed": False, "human_checked": False}
                               for n in range(report["page_start"], end + 1)])
                    if report["state"] == "preparing":
                        report["state"] = "running"
                    owner._save(job)
            else:
                before, after = (directory / "before.pdf").read_bytes(), (directory / "after.pdf").read_bytes()
                if digest(before) != report["before_render_sha256"] or digest(after) != report["after_render_sha256"]:
                    raise DocumentError("缓存的排版 PDF 哈希不匹配")
            while True:
                with owner.lock:
                    job = owner._load(job_id)
                    report = self._report(job, identifier)
                    if self.closed or report["state"] != "running":
                        report["state"] = "cancelled" if report["state"] == "cancel_requested" else "paused"
                        report["updated_at"] = now()
                        owner._save(job)
                        return
                    pending = next((p for p in report["pages"] if not p["rendered"]), None)
                    if pending is None:
                        report.update(state="completed", updated_at=now())
                        owner._save(job)
                        return
                    number, before_count, after_count = pending["page"], report["before_pages"], report["after_pages"]
                row, images = compare_pdf_page(before, after, number, before_count, after_count)
                for side, data in images.items():
                    write_file(directory / f"{side}-{number}.png", data)
                with owner.lock:
                    job = owner._load(job_id)
                    report = self._report(job, identifier)
                    report["pages"] = [row if page["page"] == number else page for page in report["pages"]]
                    report["updated_at"] = now()
                    owner._save(job)  # Commit only this completed page, with image hashes.
        except Exception as failure:
            with owner.lock:
                try:
                    job = owner._load(job_id)
                    report = self._report(job, identifier)
                    report.update(state="failed", error=str(failure) if isinstance(failure, DocumentError) else "本地排版处理失败；已完成页保留，可继续。", updated_at=now())
                    owner._save(job)
                except Exception:
                    pass

    def page(self, payload):
        owner = self.owner
        with owner.lock:
            job = owner._load(payload.get("job_id"))
            report = self._report(job, payload.get("layout_id"))
            page = next((p for p in report["pages"] if p["page"] == payload.get("page")), None)
            if page is None:
                raise DocumentError("页码不在本次对照范围")
            result = {**page, "rendered": page.get("rendered", True), "layout_id": report["id"], "state": report.get("state", "completed"), "after_sha256": report["after_sha256"]}
            for side in ("before", "after"):
                path = self._directory(job["id"], report["id"]) / f"{side}-{page['page']}.png"
                if page.get("rendered", True) and path.is_file():
                    data = path.read_bytes()
                    if page.get("image_hashes", {}).get(side, digest(data)) != digest(data):
                        raise DocumentError("排版预览图片哈希不匹配")
                    result[side] = {"available": True, "mime_type": "image/png", "data_base64": base64.b64encode(data).decode()}
                else:
                    result[side] = {"available": False}
            return result

    def check(self, payload):
        owner = self.owner
        with owner.lock:
            job = owner._load(payload.get("job_id"))
            report = self._report(job, payload.get("layout_id"))
            if payload.get("after_sha256") != report["after_sha256"]:
                raise DocumentError("人工记录与修改副本不匹配")
            if "page" in payload:
                row = next((p for p in report["pages"] if p["page"] == payload["page"]), None)
                if row is None or not row.get("rendered", True) or type(payload.get("checked")) is not bool:
                    raise DocumentError("只能记录已渲染页面的检查")
                row["human_checked"] = payload["checked"]
            else:
                pages = payload.get("checked_pages")
                valid = {p["page"] for p in report["pages"] if p.get("rendered", True)}
                if not isinstance(pages, list) or any(type(n) is not int or n not in valid for n in pages):
                    raise DocumentError("人工检查页码无效")
                for row in report["pages"]:
                    row["human_checked"] = row["page"] in pages
            report.update(status="human_review_recorded" if report["pages"] and all(p["human_checked"] for p in report["pages"]) else "awaiting_human_review",
                          checked_at=now(), updated_at=now())
            owner._save(job)
        return owner.snapshot(job["id"], compact=payload.get("compact") is True)

    def close(self):
        self.closed = True
        for worker in list(self.workers.values()):
            worker.join(timeout=1)
