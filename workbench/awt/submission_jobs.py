"""Saved local pre-submission reports and file-bound human review records."""
from __future__ import annotations

import copy
import os
import re
import threading
import time
from collections import Counter

from awt.documents import DocumentError
from awt.review_index import fingerprint
from awt.review_jobs import atomic_json, now, read_json
from awt.submission_checks import LABELS, STATUSES, VERSION, build_report, default_profile, normalise_profile


class Cancelled(Exception):
    pass


def binding(job, profile):
    return fingerprint({"checker_version": VERSION, "profile": profile,
        "documents": [[d["filename"], d["sha256"]] for d in job["documents"]], "materials": job.get("materials_ref"),
        "revision": job["revision"], "goal": job["goal"], "model": job["config"],
        "steps": [[s["id"], s["status"], s.get("result")] for s in job["steps"]],
        "cross_built": job["cross_built"], "layouts": [[r["id"], r["after_sha256"], r.get("state"),
            [[p["page"], p.get("rendered", True), p["human_checked"]] for p in r["pages"]]] for r in job["layouts"]]})


class SubmissionManager:
    def __init__(self, owner):
        self.owner, self.workers, self.closed = owner, {}, False

    def _data(self, job):
        return job.setdefault("submission", {"profile": default_profile(job["documents"]), "state": "idle", "reports": [], "confirmations": {}})

    def summary(self, job, include_profile=False):
        data = self._data(job)
        current = binding(job, data["profile"]) if data["reports"] else None
        reports = [{**r, "stale": r["binding"] != current} for r in reversed(data["reports"])]
        value = {"state": data["state"], "progress": data.get("progress", ""), "error": data.get("error"), "reports": reports,
                 "profile_sha256": fingerprint(data["profile"]), "model_calls": 0, "confirmation_revision": data.get("confirmation_revision", 0)}
        if include_profile:
            value["profile"] = copy.deepcopy(data["profile"])
        return value

    def status(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            return {"job_id": job["id"], **self.summary(job, include_profile=True)}

    def configure(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            data = self._data(job)
            if data["state"] in {"running", "cancel_requested"}:
                raise DocumentError("请先停止正在进行的投稿校验")
            data["profile"] = normalise_profile(payload.get("profile"), job["documents"])
            self.owner._save(job)
            return self.summary(job, include_profile=True)

    def run(self, payload):
        with self.owner.lock:
            if self.closed or any(w.is_alive() for w in self.workers.values()):
                raise DocumentError("已有投稿校验在运行，请等待或取消")
            job = self.owner._load(payload.get("job_id"))
            if job["state"] in {"running", "pause_requested", "cancel_requested"} or any(r.get("state") in {"preparing", "running", "pause_requested", "cancel_requested"} for r in job["layouts"]):
                raise DocumentError("请先暂停模型审阅和排版任务，再绑定稳定版本进行投稿校验")
            data = self._data(job)
            profile = normalise_profile(payload.get("profile", data["profile"]), job["documents"])
            if len(data["reports"]) >= 20:
                raise DocumentError("单个任务最多保存 20 份投稿校验报告；请导出历史并新建任务")
            token = os.urandom(16).hex()
            data.update(profile=profile, state="running", run_id=token, progress="校验材料哈希", error=None)
            self.owner._save(job)
            worker = threading.Thread(target=self._run, args=(job, token), daemon=True, name="awt-submit-" + token[:8])
            self.workers[job["id"]] = worker
            worker.start()
            return self.summary(job, include_profile=True)

    def cancel(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            data = self._data(job)
            if data["state"] == "running":
                data["state"] = "cancel_requested"
                self.owner._save(job)
            return self.summary(job)

    def _run(self, snapshot, token):
        identifier = snapshot["id"]
        profile = copy.deepcopy(snapshot["submission"]["profile"])
        captured_binding, updated = binding(snapshot, profile), 0.0
        def progress(stage):
            nonlocal updated
            if self.closed:
                raise Cancelled()
            with self.owner.lock:
                job = self.owner._load(identifier)
                data = self._data(job)
                if data.get("run_id") != token or data["state"] != "running":
                    raise Cancelled()
                if time.monotonic() - updated > 0.25:
                    data["progress"] = stage
                    self.owner._save(job)
                    updated = time.monotonic()
        try:
            for document in snapshot["documents"]:
                if profile["files"].get(document["filename"]) != "exclude":
                    progress("校验文件：" + document["filename"])
                    self.owner._source(snapshot, document)
            report = build_report(snapshot, profile, lambda d: self.owner._source(snapshot, d), progress)
            progress("保存报告")
            report.update(id=token, job_id=identifier, created_at=now(), binding=captured_binding, manuscript_revision=snapshot["revision"])
            report["report_sha256"] = fingerprint(report)
            with self.owner.lock:
                job = self.owner._load(identifier)
                data = self._data(job)
                if self.closed or data["state"] != "running":
                    raise Cancelled()
                atomic_json(self.owner._directory(identifier) / ("submission-" + token + ".json"), report)
                data["reports"].append({k: report[k] for k in ("id", "created_at", "binding", "report_sha256", "counts", "item_count", "omitted_items")})
                data.update(state="completed", progress="本地校验报告已保存", error=None)
                self.owner._save(job)
        except Exception as failure:
            with self.owner.lock:
                try:
                    job = self.owner._load(identifier)
                    data = self._data(job)
                    data.update(state="interrupted" if self.closed else "cancelled" if isinstance(failure, Cancelled) else "failed",
                                error=None if isinstance(failure, Cancelled) else str(failure) if isinstance(failure, DocumentError) else "本地校验失败；原文件和之前报告保留，可重新运行。",
                                progress="已停止；重新运行不调用模型" if isinstance(failure, Cancelled) else "未生成新报告")
                    self.owner._save(job)
                except DocumentError:
                    pass

    def _read(self, job, report_id):
        data = self._data(job)
        report_id = report_id or (data["reports"][-1]["id"] if data["reports"] else None)
        meta = next((r for r in data["reports"] if r["id"] == report_id), None)
        if not meta or not isinstance(report_id, str) or not re.fullmatch(r"[a-f0-9]{32}", report_id):
            raise DocumentError("投稿校验报告不存在")
        report = read_json(self.owner._directory(job["id"]) / ("submission-" + report_id + ".json"))
        original_hash = report.get("report_sha256")
        if original_hash != meta["report_sha256"] or fingerprint({k: v for k, v in report.items() if k != "report_sha256"}) != original_hash:
            raise DocumentError("投稿校验报告哈希不匹配")
        stale = report["binding"] != binding(job, data["profile"])
        confirmations = copy.deepcopy(data["confirmations"].get(report_id, {}))
        counts = Counter(report["counts"])
        for item in report["items"]:
            if item["id"] in confirmations:
                item["confirmation"] = confirmations[item["id"]]
                counts[item["status"]] -= 1
                counts["recorded"] += 1
                item["status"] = "recorded"
        report.update(stale=stale, confirmations=confirmations, counts={s: counts[s] for s in STATUSES})
        report["state"] = "stale" if stale else "blocked" if counts["block"] else "needs_review" if any(counts[s] for s in ("warning", "manual", "unchecked")) or report["omitted_items"] else "checks_recorded"
        return report

    def report(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            report = self._read(job, payload.get("report_id"))
            status, group = payload.get("status", "all"), payload.get("group", "all")
            if not isinstance(status, str) or status not in {*STATUSES, "all"} or not isinstance(group, str):
                raise DocumentError("报告筛选条件无效")
            offset, limit = payload.get("offset", 0), payload.get("limit", 20)
            if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
                raise DocumentError("报告分页范围无效")
            items = sorted((i for i in report["items"] if (status == "all" or i["status"] == status) and (group == "all" or i["group"] == group)), key=lambda i: STATUSES.index(i["status"]))
            return {**{k: v for k, v in report.items() if k not in {"items", "confirmations", "profile"}},
                    "items": items[offset:offset + limit], "total": len(items), "offset": offset, "limit": limit}

    def confirm(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            report = self._read(job, payload.get("report_id"))
            if report["stale"] or payload.get("binding") != report["binding"]:
                raise DocumentError("文件、规则或审阅记录已变化，请重新校验后再记录人工结果")
            item = next((r for r in report["items"] if r["id"] == payload.get("item_id")), None)
            if not item or item["status"] not in {"manual", "warning", "recorded"}:
                raise DocumentError("只能记录人工核对项或警告的处理；阻断和未检查项不能直接标为通过")
            reviewer, note = payload.get("reviewer"), payload.get("note")
            if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 100 or not isinstance(note, str) or not note.strip() or len(note) > 2000:
                raise DocumentError("请填写核对人和处理说明")
            decision = payload.get("decision", "checked")
            if not isinstance(decision, str) or decision not in {"checked", "not_applicable", "reopen"}:
                raise DocumentError("人工处理决定无效")
            self._verify_sources(job, report)
            confirmations = self._data(job)["confirmations"].setdefault(report["id"], {})
            if decision == "reopen":
                confirmations.pop(item["id"], None)
            else:
                confirmations[item["id"]] = {"reviewer": reviewer.strip(), "note": note.strip(), "decision": decision,
                    "at": now(), "binding": report["binding"], "report_sha256": report["report_sha256"]}
            self._data(job)["confirmation_revision"] = self._data(job).get("confirmation_revision", 0) + 1
            self.owner._save(job)
            return self.report({"job_id": job["id"], "report_id": report["id"]})

    def _verify_sources(self, job, report):
        for source in report["source_manifest"]:
            document = next((d for d in job["documents"] if d["filename"] == source["filename"] and d["sha256"] == source["sha256"]), None)
            if document is None:
                if report["stale"]:
                    continue  # Historical export remains explicitly stale.
                raise DocumentError("报告与当前材料不匹配")
            self.owner._source(job, document)

    def export(self, payload):
        with self.owner.lock:
            job = self.owner._load(payload.get("job_id"))
            report = self._read(job, payload.get("report_id"))
            self._verify_sources(job, report)
            report["exported_at"] = now()
            report["export_sha256"] = fingerprint(report)
            if payload.get("format", "json") == "json":
                return report
            if payload.get("format") != "markdown":
                raise DocumentError("导出格式需要 json 或 markdown")
            def cell(value):
                return str(value).replace("|", "\\|").replace("\n", " ")
            lines = ["# 投稿前校验报告", "", "目标：" + cell(report["profile"]["target"] or "未指定"),
                     "状态：" + ("已过期，不能代表当前稿件" if report["stale"] else "存在阻断问题" if report["state"] == "blocked" else "仍需核对" if report["state"] == "needs_review" else "当前清单已完成"),
                     "", report["scope"], "", "报告 SHA-256：`" + report["report_sha256"] + "`", "绑定：`" + report["binding"] + "`", "", "## 文件与规则", "",
                     "规则 SHA-256：`" + report["profile_sha256"] + "`", "", "| 文件 | 角色 | SHA-256 |", "|---|---|---|"]
            lines.extend("| " + " | ".join(cell(s[k]) for k in ("filename", "role", "sha256")) + " |" for s in report["source_manifest"])
            lines += ["", "## 检查结果", ""]
            for item in report["items"]:
                lines += ["### " + LABELS[item["status"]] + " · " + item["title"], "", item["detail"], ""]
                for anchor in item["anchors"]:
                    lines += ["- " + cell(anchor.get("filename", "")) + " · " + cell(anchor.get("location", anchor["locator"])) + "：" + cell(anchor["quote"])]
                if item.get("confirmation"):
                    c = item["confirmation"]
                    lines += ["", "人工记录：" + cell(c["reviewer"]) + " · " + c["at"] + " · " + c["decision"] + " · " + cell(c["note"]), ""]
            if report["omitted_items"]:
                lines += ["", f"另有 {report['omitted_items']} 条因报告条数上限未展开，请分章缩小范围后检查。"]
            lines += ["", "## 规则快照", "", "```json"]
            import json
            lines += [json.dumps(report["profile"], ensure_ascii=False, indent=2), "```", ""]
            return {"filename": "awt-submission-" + report["id"][:8] + ".md", "content": "\n".join(lines), "stale": report["stale"]}

    def close(self):
        self.closed = True
        for worker in list(self.workers.values()):
            worker.join(timeout=1)
