"""Command line entry: `loop <command> <workspace> ...`."""
import argparse
import sys
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


def cmd_lintel(a):
    """把「等你反应的事」交给 lintel 画（plan 阶段 4.2）。

    引擎自己出的事也要交上去——不然工具一挂，刘海上只会安静下来，而「安静」和「没事」长得一样。"""
    import time as _t

    from . import doctor
    from . import index as X
    from . import lintel as LN
    cfg = C.load(a.workspace)
    while True:
        problems = [f"{item}：{msg}" for item, msg in doctor.run(a.workspace)[0]]
        summary = None
        if not problems:
            try:
                files, summary = X.build(cfg)
                X.write(cfg, files)
            except Exception as e:  # 引擎抛了 = 工具异常，不是「没有活动」
                problems = [f"{type(e).__name__}：{e}"]
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
