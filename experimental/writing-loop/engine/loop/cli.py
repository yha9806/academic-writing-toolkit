"""Command line entry: `loop <command> <workspace> ...`."""
import argparse
import json
import os
import re
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
    # Not in doctor.run: the notch producer reads its problems as "the tool is broken" and stops drawing. A workspace
    # the hook registry does not list is a loop that never runs for it, which the person setting it up must hear here.
    warn = C.registry_warning(a.workspace)
    if warn:
        problems = problems + [("registry", warn)]
    else:
        facts = facts + [("registry", f"钩子登记表里有它（{C.registry_path()}）")]
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
    try:
        # The notch's turn signal (turns.py): every request is recorded before the lock, so a request folded into a
        # running update still counts. A broken notch module must not stop the index from being rebuilt (same as M3).
        from . import turns as TN
        TN.record(ws, a.reason)
    except Exception as e:  # noqa: BLE001
        TN = None
        HL.record_event(ws, "hook_error", f"刘海的轮次记录读不进来：{type(e).__name__}：{e}")
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
                    before = _head_on_disk(ws) if TN else None
                    files, summary = X.build(cfg)
                    X.write(cfg, files)
                except Exception as e:  # recorded, never swallowed: health shows it until a later success
                    HL.record_error(ws, f"{type(e).__name__}：{e}")
                    print(f"update 失败：{type(e).__name__}：{e}", file=sys.stderr)
                    return 1
                if TN and summary.get("head") and (before or "")[:7] != summary["head"]:
                    _record_head(ws, cfg, summary["head"], TN)
                HL.record_ok(ws, a.reason, time.time() - t0)
                _coverage_after_update(ws, cfg)
                if not dirty.exists():
                    break
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)
        if not dirty.exists():  # a request that arrived between the last check and the unlock
            break
    print(_summary_line(summary))
    return 0


def _head_on_disk(ws):
    """The manuscript HEAD the index on disk was built from. Only sources.json is read: an index this engine cannot
    summarize any more must not stop the rebuild that replaces it. None if unreadable (the new head then counts as new)."""
    try:
        head = json.loads((ws / "index" / "sources.json").read_text(encoding="utf-8")).get("head")
    except (OSError, ValueError, AttributeError):
        return None
    return head if isinstance(head, str) else None


def _record_head(ws, cfg, head, TN):
    """The manuscript got a commit: a touch, whichever repo git ran in. It is recorded at the commit's own time, not now:
    the rebuild that notices it ends 20-70 s after the commit, often after the turn's Stop, and a touch stamped after
    the Stop would reopen a turn that had ended (grill 09-22 #1). A commit made before the author's message is then
    not a touch of this turn at all (a reset to an old commit)."""
    from . import gitio
    from . import health as HL
    try:
        t = gitio.commit_time(cfg["repo"], head)
    except Exception as e:  # noqa: BLE001 -- the notch signal must not fail the update
        t, err = None, e
    else:
        err = None
    if t is None:
        HL.record_event(ws, "hook_error", f"刘海的轮次记录：读不到提交 {head} 的时刻（{err or 'git 没给'}），这次提交没记成碰稿")
        return
    TN.record(ws, f"head:{head}", now=t)


def _coverage_after_update(ws, cfg):
    """Run the checks the new index made due. A failure here never fails the update, and never leaves an old summary
    standing in for a new one: the summary is removed, so every surface says coverage was not computed."""
    from . import coverage as V
    from . import health as HL
    try:
        V.compute(cfg, ws, do_run=True)
    except Exception as e:  # recorded, never swallowed
        (Path(ws) / "cache" / "coverage" / "summary.json").unlink(missing_ok=True)
        V.refresh_outlet(ws, cfg)  # the note must not keep saying the removed summary's line
        HL.record_event(ws, "coverage_error", f"{type(e).__name__}：{e}")
        print(f"coverage 失败：{type(e).__name__}：{e}", file=sys.stderr)


def cmd_coverage(a):
    """Which checks have looked at the draft as it is now. Exit 0 only when nothing needs attention."""
    from . import coverage as V
    try:
        cfg = C.load(a.workspace)
    except (OSError, ValueError) as e:
        print(f"coverage：读不出工作区配置：{e}", file=sys.stderr)
        return 2
    only = set(a.only.split(",")) if a.only else None
    s = V.compute(cfg, a.workspace, do_run=a.run, only=only, force=a.force)
    warn = C.registry_warning(a.workspace)
    if a.json:
        print(json.dumps(dict(s, hook_registry=warn), ensure_ascii=False, indent=1))
    else:
        if warn:
            print("注意：" + warn)
        print(V.table(s, a.workspace))
        if s["ran"]:
            print("这次跑了：" + "、".join(s["ran"]))
    return 1 if (V.attention(s) or (s.get("target") or {}).get("problems")) else 0


def cmd_precheck(a):
    """Every script check on the working tree before a commit, recording nothing. Exit 1 when a check would turn red
    at the commit, reads differently from its last record, or cannot run."""
    from . import coverage as V
    try:
        cfg = C.load(a.workspace)
    except (OSError, ValueError) as e:
        print(f"precheck：读不出工作区配置：{e}", file=sys.stderr)
        return 2
    only = set(a.only.split(",")) if a.only else None
    res = V.precheck(cfg, a.workspace, only=only)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(V.precheck_text(res, cfg.get("name") or a.workspace))
    if res.get("error"):
        return 2
    return 1 if any(c["group"] in (V.PRE_RED, V.PRE_CHANGED, V.PRE_FAILED) for c in res["checks"]) else 0


def cmd_state(a):
    """Whether the paper's claims stand: the claims ledger against the whole draft. Exit 0 only at 待作者终审, or at 已投稿 with nothing in the way."""
    from . import state as S
    try:
        cfg = C.load(a.workspace)
    except (OSError, ValueError) as e:
        print(f"state：读不出工作区配置：{e}", file=sys.stderr)
        return 2
    st = S.compute(cfg, a.workspace)
    warn = C.registry_warning(a.workspace)
    if a.json:
        out = dict(st, hook_registry=warn)
        out["claims"] = [dict({k: v for k, v in c.items() if k not in ("over", "must", "carry")},
                              over=[r for r, _ in c["over"]], must=[r for r, _ in c["must"]],
                              carry=[r for r, _ in c.get("carry") or []])
                         for c in st.get("claims") or []]
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if warn:
            print("注意：" + warn)
        print(S.table(st))
    return 0 if S.ready(st) else 1


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


EMPTY_SUMMARY = {"head": "?", "versions": 0, "sentences": 0, "changesets": 0, "mixed": 0, "all_unknown": 0,
                 "ledger": 0, "ledger_status": {}, "unattached_ledger": 0, "messages": 0, "messages_attached": 0,
                 "messages_before_first_version": 0, "latest": None}


def _producer_alive(pidfile):
    """The pid in pidfile belongs to a running `loop lintel` process."""
    import subprocess
    try:
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    r = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return "loop" in r.stdout and "lintel" in r.stdout


# K10 功耗（2026-10-01）：常驻来源进程只起不停，每 10 秒把整套状态从头算一遍（实测两个工作区合计占单核约两成，
# 内存各 1.5 GB 上下）。已投稿或长时间没有活动就收尾退出，钩子下次有活动再拉起；输入没变就只续心跳。
REBUILD_AT_LEAST = 60.0   # 输入没变也每这么多秒重算一次：卡片上有按时间走的字（「几分钟前」）
IDLE_EXIT = 1800.0        # 这么多秒没有活动就收尾退出


def _ledger_stage(cfg):
    """主张清单里写的阶段；没配清单或读不出是 None。"""
    p = cfg.get("claims")
    if not p:
        return None
    try:
        raw = Path(os.path.expanduser(p)).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    from . import state as S
    m = S.STAGE.search(re.sub(r"(?ms)^```.*?^```", "", raw))
    return m.group(1) if m else None


def _submitted(cfg):
    """阶段写的是投稿（已投稿、审稿中……）：不用再常驻。"""
    from . import state as S
    stage = _ledger_stage(cfg)
    return stage if stage and S.SUBMITTED_STAGE.search(stage) else None


def _outside_inputs(cfg):
    """工作区外面、卡片也要读的文件：主张清单、风险台账、意图卡。"""
    return [Path(os.path.expanduser(cfg[k])) for k in ("claims", "risks", "intent_card") if cfg.get(k)]


def _last_activity(ws, cfg):
    """最近一次有人在这份稿子上干活的时刻：钩子触发的更新（health.json）、轮次、作者的话、上面那几份文件。"""
    ws = Path(ws)
    paths = [ws / "health.json", ws / "cache" / "turns.jsonl", *(ws / "human").glob("*"), *_outside_inputs(cfg)]
    times = []
    for p in paths:
        try:
            times.append(p.stat().st_mtime)
        except OSError:
            pass
    return max(times) if times else None


def _quiet_reason(cfg, ws, now, idle):
    """常驻来源进程现在该不该收尾退出；该就回一句为什么，不该是 None。"""
    stage = _submitted(cfg)
    if stage:
        return f"阶段写着「{stage}」，稿子已经投出"
    if idle:
        last = _last_activity(ws, cfg)
        if last is not None and now - last > idle:
            return f"{int((now - last) // 60)} 分钟没有活动"
    return None


def _inputs_signature(ws, cfg, home, producer):
    """卡片读的东西有没有变：工作区里每个文件的大小与修改时间（来源进程自己的日志和 pid 文件不算）、
    工作区外的清单与台账、lintel 收件箱里待办的动作。

    cache/overview-audit 也不算：那是来源进程自己算总览时写的缓存。算进去的话，每次真有变化都要多重算一轮
    （这一轮写了缓存，下一轮看见「变了」又算一遍）。"""
    ws = Path(ws)
    own = {ws / "cache" / "lintel.log", ws / "cache" / "lintel.log.1", ws / "cache" / "lintel.pid"}
    sig = []
    for root, dirs, files in os.walk(ws):
        if Path(root) == ws / "cache" and "overview-audit" in dirs:
            dirs.remove("overview-audit")
        for f in files:
            p = Path(root) / f
            if p in own:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            sig.append((str(p), st.st_size, st.st_mtime_ns))
    for p in _outside_inputs(cfg):
        try:
            st = p.stat()
            sig.append((str(p), st.st_size, st.st_mtime_ns))
        except OSError:
            sig.append((str(p), -1, -1))
    from . import inbox as IB
    sig += [(str(p), 0, 0) for p in IB.pending(home, producer)]
    return hash(tuple(sorted(sig)))


def _resting(act):
    """收尾时留给 lintel 的那一份：不带心跳（不然过了心跳时限会被标成「没消息」），也不算在跑。"""
    a = dict(act)
    a.pop("heartbeatSeconds", None)
    a["running"] = False
    a["inProgress"] = False
    return a


def _say(msg, file=None):
    """来源进程的一行日志，带本地时间：中断以后才分得清哪一轮跑了、哪一轮没跑（〈八〉）。"""
    import time as _t
    print(f"{_t.strftime('%Y-%m-%d %H:%M:%S')} {msg}", file=file or sys.stdout, flush=True)


def cmd_lintel(a):
    """把「等你反应的事」交给 lintel 画（plan 阶段 4.2）。

    常驻：读磁盘上的索引（由钩子触发的 update 维护），每 interval 秒同步一次卡片并续心跳；
    不自己重建索引（--rebuild 才重建），所以常驻不吃 CPU。一个工作区只跑一个，第二个直接退出。
    引擎自己出的事也要交上去——不然工具一挂，刘海上只会安静下来，而「安静」和「没事」长得一样。"""
    import time as _t

    from . import doctor
    from . import health as HL
    from . import inbox as IB
    from . import index as X
    from . import lintel as LN
    from . import overview as OV
    cfg = C.load(a.workspace)
    ovw = OV.Overview(cfg)
    ws = Path(a.workspace)
    a.home = a.home or LN.lintel_home()
    a.producer = a.producer or LN.PRODUCER
    pidfile = ws / "cache" / "lintel.pid"
    if not a.once:
        if not LN.registered(a.home, a.producer):
            _say(f"lintel 里没有登记来源 {a.producer}：不启动", file=sys.stderr)
            return 2
        if _producer_alive(pidfile):
            _say("lintel 来源进程已在跑", file=sys.stderr)
            return 0
        pidfile.parent.mkdir(parents=True, exist_ok=True)
        pidfile.write_text(f"{os.getpid()}\n")
    last_sig = last_acts = last_problems = None
    last_built = 0.0
    said = None
    rounds = 0
    while True:
        now_t = a.now if a.now is not None else _t.time()
        sig = None if a.once else _inputs_signature(ws, cfg, a.home, a.producer)
        if last_acts is not None and sig == last_sig and now_t - last_built < REBUILD_AT_LEAST:
            acts, problems = last_acts, last_problems   # 输入没变：只续心跳，不重算
        else:
            with X.round_reads():   # sentences.json 这一轮只解析一次（index.round_reads）
                problems = [f"{item}：{msg}" for item, msg in doctor.run(a.workspace)[0]]
                summary = None
                if not problems:
                    t0 = _t.time()
                    try:
                        if a.rebuild:
                            files, summary = X.build(cfg)
                            X.write(cfg, files)
                            HL.record_ok(a.workspace, "lintel", _t.time() - t0)
                        else:
                            summary = X.load_summary(cfg)
                            if summary is None:
                                problems.append("索引：index/ 还没建或读不出（钩子触发的 update 会建）")
                    except Exception as e:  # 引擎抛了 = 工具异常，不是「没有活动」
                        HL.record_error(a.workspace, f"{type(e).__name__}：{e}")
                problems += [f"{item}：{msg}" for item, msg in HL.file_problems(a.workspace)]
                notices = [f"{item}：{msg}" for item, msg in HL.file_notices(a.workspace)]
                summary = summary or {**EMPTY_SUMMARY, "name": cfg["name"]}
                ov = None
                if not problems:
                    try:
                        # 面板上点的「是方法署名」：只认这份稿子当前给出的动作（分镜 ㊺）。
                        for name, ok, why in IB.take_actions(a.home, LN.activity_id(cfg["name"]),
                                                             lambda act: OV.apply_action(ovw, act, _t.time()), producer=a.producer):
                            _say(f"收件 {name}：{'记下' if ok else '没收'}（{why}）")
                        ov = ovw.get(_t.time())
                    except Exception as e:  # 总览算不出来是工具异常，照样交上去；卡片其余部分照写
                        HL.record_error(a.workspace, f"总览：{type(e).__name__}：{e}")
                        problems.append(f"总览：{type(e).__name__}：{e}")
                from . import coverage as V
                turn = readers = None
                try:
                    # 这一轮在做什么（开工 / 在跑 / 落地）：读不出是引擎的毛病，照样交上去，不当作「没有在跑」
                    from . import turns as TN
                    turn, readers = TN.current(ws, cfg), TN.readers_run(ws)
                except Exception as e:  # noqa: BLE001
                    problems.append(f"轮次：{type(e).__name__}：{e}")
                from . import outlet as OUT
                analysis = None
                from . import catalogue as K
                if K.get(cfg, "ring.analysis"):
                    # 分析 on the ring (spec 2026-09-25 §4.5), off unless turned on: the notch was laid out for seven stages.
                    try:
                        from . import state as S
                        analysis = [t for t in S.compute(cfg, a.workspace).get("todo") or [] if t.get("kind") == "分析"]
                    except Exception as e:  # noqa: BLE001
                        problems.append(f"分析环：{type(e).__name__}：{e}")
                cov = V.load_summary(a.workspace, cfg)
                # What the ring sees past the coverage summary: a landing, the register's decisions, the intent card, a freeze
                # (spec 2026-09-29-ring-rounds-and-stages). One that cannot be read leaves the ring as it was for that part.
                from . import ringinputs as RI
                ring_inputs = RI.gather(cfg, a.workspace, cov, problems) if cov else None
                acts = LN.build(summary, now=_t.time(), problems=problems, notices=notices, overview=ov, analysis=analysis,
                                ring_inputs=ring_inputs, coverage=cov, turn=turn, readers=readers,
                                built_at=(HL.load(a.workspace).get("last_ok") or {}).get("t"),
                                denials=HL.guard_denials(a.workspace), overrides=HL.gate_overrides(a.workspace),
                                note=OUT.read(a.workspace))
                last_sig, last_acts, last_problems, last_built = sig, acts, problems, now_t
        why = None if a.once else _quiet_reason(cfg, ws, now_t, a.idle_exit)
        # 一次性写卡（--once；钩子给没有常驻来源进程的稿件写的就是这种）没人续心跳、也没人收尾：同样不带心跳，
        # 不然几分钟后 lintel 就标「没消息」（10-04 刘海上挂着「171 分钟没消息」）。旁边有常驻进程在续就照常带。
        if why or (a.once and not _producer_alive(pidfile)):
            acts = [_resting(x) for x in acts]
        try:
            counts = LN.sync(acts, home=a.home, producer=a.producer)
        except LN.NotRegistered as e:
            _say(e, file=sys.stderr)
            return 2
        # 日志只记有变化的轮次（以前每 10 秒一行，一个工作区的日志涨到 5 MB）。
        news = (counts["written"], counts["removed"], len(problems))
        if a.once or why or news != said:
            _say(f"lintel：{len(acts)} 张卡（新写 {counts['written']}、续心跳 {counts['touched']}、"
                 f"没变 {counts['unchanged']}、撤掉 {counts['removed']}）"
                 + (f"；工具异常 {len(problems)} 处" if problems else ""))
            said = (0, 0, len(problems))
        if a.once:
            return 1 if problems else 0
        if why:
            _say(f"lintel：{why}，来源进程收尾退出（下次有活动时钩子再拉起）")
            try:
                if pidfile.read_text().strip() == str(os.getpid()):
                    pidfile.unlink()
            except OSError:
                pass
            return 0
        rounds += 1
        if a.rounds is not None and rounds >= a.rounds:
            return 0
        _t.sleep(a.interval)


def cmd_inbox(a):
    """Register what the author dragged onto the notch (lintel wrote the drop files; it never runs us)."""
    from . import inbox as IB
    from . import lintel as LN
    home = a.home or LN.lintel_home()
    a.producer = a.producer or LN.PRODUCER
    if not LN.registered(home, a.producer):
        print(f"lintel 里没有登记来源 {a.producer}：不读收件", file=sys.stderr)
        return 2
    results = IB.process(home, a.workspaces, producer=a.producer, projects_dir=a.projects_dir)
    for name, o in results:
        print(f"{name}: " + (f"登记好了 {o['workspace']}（{o['sentences']} 句 · {o['sections']} 节 · {o['ref']}）" if o["ok"] else f"没收：{o['reason']}"))
    if not results:
        print("收件目录里没有新的拖放")
    return 0 if all(o["ok"] for _, o in results) else 1


def cmd_accept(a):
    """A check out of date for the current draft, and a small enough change not to re-run for: say so, with the reason.
    It holds until the next change to what the check reads."""
    from . import coverage as V
    try:
        cfg = C.load(a.workspace)
        acc = V.accept(cfg, a.workspace, a.check, a.reason, by=a.by, uuid=a.author_uuid)
    except (OSError, ValueError) as e:
        print(f"accept：{e}", file=sys.stderr)
        return 1
    V.compute(cfg, a.workspace)
    who = "作者" if acc["by"] == "author" else "Claude"
    print(f"已记下：{who}接受 {a.check} 这次过期（{acc['why_stale']}）：{acc['reason']}；下一次改动它读的内容，就重新算过期")
    return 0


def cmd_ack(a):
    from . import health as HL
    HL.ack(a.workspace)
    print("已确认：此前的拦截与钩子异常不再显示（记录仍在 health.json）")
    return 0


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

    v = sub.add_parser("coverage", help="which checks have looked at the draft as it is now (exit 1 if any has not)")
    v.add_argument("workspace")
    v.add_argument("--run", action="store_true", help="run the script checks that are due before reporting")
    v.add_argument("--force", action="store_true", help="with --run: run every runnable script check, due or not")
    v.add_argument("--only", help="comma-separated check ids to run")
    v.add_argument("--json", action="store_true")
    v.set_defaults(fn=cmd_coverage)

    pc = sub.add_parser("precheck", help="run every script check on the working tree before a commit, recording "
                                         "nothing (exit 1 if one would turn red or change)")
    pc.add_argument("workspace")
    pc.add_argument("--only", help="comma-separated check ids")
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(fn=cmd_precheck)

    st = sub.add_parser("state", help="whether the paper's claims stand: the claims ledger against the whole draft")
    st.add_argument("workspace")
    st.add_argument("--json", action="store_true")
    st.set_defaults(fn=cmd_state)

    b = sub.add_parser("bench", help="time event -> updated index through the hook path (spec T15)")
    b.add_argument("--runs", type=int, default=10)
    b.add_argument("--json", action="store_true")
    b.set_defaults(fn=cmd_bench)

    ac = sub.add_parser("accept", help="accept that a check is out of date for the draft as it is now (a small change)")
    ac.add_argument("workspace")
    ac.add_argument("check", help="check id, e.g. readers")
    ac.add_argument("--reason", required=True, help="why this change does not need a re-run")
    ac.add_argument("--by", choices=("claude", "author"), default="claude")
    ac.add_argument("--author-uuid", default=None, help="required with --by author: the uuid of the author's message")
    ac.set_defaults(fn=cmd_accept)

    k = sub.add_parser("ack", help="the author has seen the refused writes and hook errors so far")
    k.add_argument("workspace")
    k.set_defaults(fn=cmd_ack)

    ib = sub.add_parser("inbox", help="register the folders the author dragged onto the lintel notch (候选 B)")
    ib.add_argument("--workspaces", required=True, help="where new workspaces are created (<root>/<repo name>)")
    ib.add_argument("--home", default=None)
    ib.add_argument("--producer", default=None, help="default: the writing loop's producer id")
    ib.add_argument("--projects-dir", default=None, help="override the transcripts directory (tests)")
    ib.set_defaults(fn=cmd_inbox)

    n = sub.add_parser("lintel", help="write activities for the lintel notch host")
    n.add_argument("workspace")
    n.add_argument("--once", action="store_true")
    n.add_argument("--interval", type=float, default=10.0)
    n.add_argument("--home", default=None, help="lintel's directory (default: $LOOP_LINTEL_HOME or the standard one)")
    n.add_argument("--producer", default=None, help="default: the writing loop's producer id")
    n.add_argument("--rebuild", action="store_true", help="rebuild the index on every round instead of reading it")
    n.add_argument("--idle-exit", type=float, default=IDLE_EXIT,
                   help="seconds without activity before the resident producer rests its card and exits (0: never)")
    n.add_argument("--rounds", type=int, default=None, help=argparse.SUPPRESS)   # tests: stop after this many rounds
    n.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)    # tests: a fixed clock for the idle check
    n.set_defaults(fn=cmd_lintel)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
