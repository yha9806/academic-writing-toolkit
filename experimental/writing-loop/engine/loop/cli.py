"""Command line entry: `loop <command> <workspace> ...`."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import config as C


def cmd_init(a):
    ws = Path(a.workspace)
    if (ws / "config.json").exists() and not a.force:
        print(f"{ws}/config.json 已存在；加 --force 才覆盖", file=sys.stderr)
        return 2
    for sub in C.SUBDIRS:
        (ws / sub).mkdir(parents=True, exist_ok=True)
    cfg = C.default_config(a.name or ws.name, Path(a.repo).expanduser().resolve(), a.ref, a.draft_glob, a.genre)
    if a.ledger:
        cfg["ledger"] = {"path": a.ledger, "evidence_dir": a.evidence_dir, "keymap_from": a.keymap_from}
    C.save(ws, cfg)
    print(f"wrote {ws}/config.json")
    return 0


def cmd_doctor(a):
    from . import doctor
    problems, facts = doctor.run(a.workspace)
    for item, msg in facts:
        print(f"  · {item}: {msg}")
    for item, msg in problems:
        print(f"  ✗ {item}: {msg}")
    if problems:
        print(f"doctor: {len(problems)} 项读不到或不存在")
        return 1
    print("doctor: 配置里的每个路径都读得到（不代表内容正确）")
    return 0


def _summary_line(s):
    st = s["ledger_status"]
    return (f"{s['name']} @ {s['head']}：定稿 {s['versions']} 版，当前 {s['sentences']} 句；"
            f"改动集 {s['changesets']} 个（混合 {s['mixed']}、触发源全 △ {s['all_unknown']}）；"
            f"台账 {s['ledger']} 条（原文里找到 {st.get('found', 0)}、找不到 {st.get('not_found', 0)}、文件缺失 {st.get('file_missing', 0)}、"
            f"无原文 {st.get('no_source', 0)}、没挂上句子 {s['unattached_ledger']}）；"
            f"你的消息 {s['messages']} 条（挂到句子 {s['messages_attached']}、早于第一版 {s['messages_before_first_version']}）")


def cmd_index(a):
    from . import index as X
    cfg = C.load(a.workspace)
    files, summary = X.build(cfg)
    X.write(cfg, files)
    print(_summary_line(summary))
    return 0


def cmd_rebuild(a):
    from . import index as X
    cfg = C.load(a.workspace)
    files, summary = X.build(cfg)
    if not a.check:
        X.write(cfg, files)
        print(_summary_line(summary))
        return 0
    diffs, cause = X.check(cfg, files)
    if not diffs:
        print("rebuild --check: 从真源重建的索引与磁盘上的逐字节相同")
        return 0
    for name, what in diffs:
        print(f"  ✗ index/{name}: {what}")
    print(f"rebuild --check: {cause}")
    return 1


STALE_LOCK = 600.0


def _acquire(lock):
    """An exclusive lock file; one left behind by a killed update is taken over after STALE_LOCK seconds."""
    for _ in range(2):
        try:
            return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime <= STALE_LOCK:
                    return None
                lock.unlink()
            except FileNotFoundError:
                pass
    return None


def cmd_update(a):
    """Rebuild index/ and record the outcome in health.json. Hooks call this detached, possibly many at once:
    if another update holds the lock, leave a marker so the running one goes round again, and return."""
    from . import health as HL
    from . import index as X
    ws = Path(a.workspace)
    (ws / "cache").mkdir(parents=True, exist_ok=True)
    lock, dirty = ws / "cache" / "update.lock", ws / "cache" / "update.dirty"
    summary = None
    while True:
        fd = _acquire(lock)
        if fd is None:
            dirty.touch()
            print("另一次更新正在进行：已记为待重跑")
            return 0
        try:
            while True:
                dirty.unlink(missing_ok=True)
                t0 = time.time()
                try:
                    cfg = C.load(ws)
                    files, summary = X.build(cfg)
                    X.write(cfg, files)
                except Exception as e:  # recorded, never swallowed: health shows it until a later success
                    HL.record_error(ws, f"{type(e).__name__}：{e}")
                    print(f"update 失败：{type(e).__name__}：{e}", file=sys.stderr)
                    return 1
                HL.record_ok(ws, a.reason, time.time() - t0)
                if not dirty.exists():
                    break
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)
        if not dirty.exists():  # a request that arrived between the last check and the unlock
            break
    print(_summary_line(summary))
    return 0


def cmd_health(a):
    from . import health as HL
    cfg = C.load(a.workspace)
    problems = HL.assess(cfg, check_index=not a.quick)
    for item, msg in problems:
        print(f"  ✗ {item}：{msg}")
    last = HL.load(cfg["_ws"]).get("last_ok")
    print(f"health：{len(problems)} 处问题" if problems else f"health：没有已知问题（最近一次成功 {last['at']}）")
    return 1 if problems else 0


def cmd_bench(a):
    from . import bench as B
    res = B.run(runs=a.runs)
    rows, ok = B.report(res)
    for kind, note, med, p95, target, passed in rows:
        timing = f"中位 {med:.2f} s，p95 {p95:.2f} s" if med is not None else ""
        verdict = "—" if passed is None else ("达标" if passed else "未达标")
        print(f"  {kind:10} 目标 ≤{target:.0f} s  {timing:24} {note}  {verdict}")
    if a.json:
        print(json.dumps(res))
    print("bench：可测的三类都达标" if ok else "bench：有未达标或超时的一类")
    return 0 if ok else 1


def cmd_lintel(a):
    """把「等你反应的事」交给 lintel 画（plan 阶段 4.2）。

    引擎自己出的事也要交上去——不然工具一挂，刘海上只会安静下来，而「安静」和「没事」长得一样。"""
    import time as _t

    from . import doctor
    from . import index as X
    from . import lintel as LN
    cfg = C.load(a.workspace)
    from . import health as HL
    while True:
        problems = [f"{item}：{msg}" for item, msg in doctor.run(a.workspace)[0]]
        summary = None
        if not problems:
            t0 = _t.time()
            try:
                files, summary = X.build(cfg)
                X.write(cfg, files)
                HL.record_ok(a.workspace, "lintel", _t.time() - t0)
            except Exception as e:  # 引擎抛了 = 工具异常，不是「没有活动」
                HL.record_error(a.workspace, f"{type(e).__name__}：{e}")
        problems += [f"{item}：{msg}" for item, msg in HL.file_problems(a.workspace)]
        if summary is None:
            summary = {"name": cfg["name"], "head": "?", "versions": 0, "sentences": 0, "changesets": 0,
                       "mixed": 0, "all_unknown": 0, "ledger": 0, "ledger_status": {},
                       "unattached_ledger": 0, "messages": 0, "messages_attached": 0,
                       "messages_before_first_version": 0}
        acts = LN.build(summary, now=_t.time(), problems=problems)
        try:
            counts = LN.sync(acts, home=a.home, producer=a.producer)
        except LN.NotRegistered as e:
            print(e, file=sys.stderr)
            return 2
        print(f"lintel：{len(acts)} 张卡（新写 {counts['written']}、续心跳 {counts['touched']}、"
              f"没变 {counts['unchanged']}、撤掉 {counts['removed']}）"
              + (f"；工具异常 {len(problems)} 处" if problems else ""), flush=True)
        if a.once:
            return 1 if problems else 0
        _t.sleep(a.interval)


def main(argv=None):
    p = argparse.ArgumentParser(prog="loop")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create a workspace and its config")
    i.add_argument("workspace")
    i.add_argument("--repo", required=True)
    i.add_argument("--ref", required=True)
    i.add_argument("--draft-glob", required=True)
    i.add_argument("--genre", default="conference")
    i.add_argument("--name")
    i.add_argument("--ledger")
    i.add_argument("--evidence-dir")
    i.add_argument("--keymap-from")
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=cmd_init)

    d = sub.add_parser("doctor", help="check that every configured path resolves")
    d.add_argument("workspace")
    d.set_defaults(fn=cmd_doctor)

    x = sub.add_parser("index", help="build index/ from git and transcripts")
    x.add_argument("workspace")
    x.set_defaults(fn=cmd_index)

    r = sub.add_parser("rebuild", help="rebuild index/; with --check compare instead of writing")
    r.add_argument("workspace")
    r.add_argument("--check", action="store_true")
    r.set_defaults(fn=cmd_rebuild)

    u = sub.add_parser("update", help="rebuild index/ and record the outcome in health.json")
    u.add_argument("workspace")
    u.add_argument("--reason", default="manual")
    u.set_defaults(fn=cmd_update)

    h = sub.add_parser("health", help="what is known to be wrong: errors, lag, index consistency, refused writes")
    h.add_argument("workspace")
    h.add_argument("--quick", action="store_true", help="skip the full rebuild comparison")
    h.set_defaults(fn=cmd_health)

    b = sub.add_parser("bench", help="time event -> updated index through the hook path (spec T15)")
    b.add_argument("--runs", type=int, default=10)
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=cmd_bench)

    from . import lintel as _LN
    n = sub.add_parser("lintel", help="write activities for the lintel notch host")
    n.add_argument("workspace")
    n.add_argument("--once", action="store_true")
    n.add_argument("--interval", type=float, default=10.0)
    n.add_argument("--home", default=_LN.HOME)
    n.add_argument("--producer", default=_LN.PRODUCER)
    n.set_defaults(fn=cmd_lintel)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
