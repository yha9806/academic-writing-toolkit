"""The checks the loop runs, and the ones it deliberately does not.

Every check registered in scripts/check-fails-closed.py appears here once: in CHECKS, with what makes it stale and
how to run it on the tracked draft, or in UNWIRED, with the reason it is not a check on a manuscript. A test holds
the two lists to the registry, so a new check cannot arrive in the toolkit without the loop either running it or
saying why not. The same test holds every skill to the Codex installer's list.

Per check:
  kind      script: deterministic, cheap, run by `loop update` whenever it is due.
            panel:  costs model calls and needs the host to open sub-agents; the loop only says when it is due.
  scripts   names in check-fails-closed.py's form: "<skill>/<file>" or "scripts/<file>".
  formats   draft formats the check can read. A draft in another format gets the status 不适用, never 最新.
  instead   for a format it cannot read: the check that covers the same ground there, or None when nothing does.
  scope     what makes a past run stale. kind: all | cite | numbers | sections | none (inputs only).
  needs     configuration the check cannot run without, as dotted paths into the workspace config.
  inputs    function(cfg) -> {role: repo path} of files the check reads besides the draft; they are archived with it,
            and a change to any of them makes the check stale.
  outside   function(cfg) -> [absolute paths] read in place (a venue corpus, an intent card); their content hash is
            part of what a run is keyed on.
  argv      function(ctx) -> argument list, run with cwd = the archived tree.
"""
import os
import sys
from pathlib import Path

# The toolkit checkout the scripts live in. A mutation run copies the engine elsewhere and points this back.
ENGINE_ROOT = Path(os.environ.get("AWT_ROOT") or Path(__file__).resolve().parents[4])
KINDS = ("script", "panel")
SCOPES = ("all", "cite", "numbers", "sections", "none")
UNWIRED_REASON_MIN = 20


def get(cfg, dotted):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur or cur[part] in (None, "", [], {}):
            return None
        cur = cur[part]
    return cur


def script_path(name):
    if Path(name).is_absolute():  # tests register throwaway checks by absolute path
        return Path(name)
    skill, _, file = name.partition("/")
    if skill == "scripts":
        return ENGINE_ROOT / "scripts" / file
    return ENGINE_ROOT / ".claude" / "skills" / skill / "scripts" / file


def _py(ctx, name):
    return [sys.executable, str(script_path(name))]


def _node(ctx, name):
    return ["node", str(script_path(name))]


def _ledger_inputs(cfg):
    led = get(cfg, "overview.ledger") or {}
    out = {"ledger": led.get("path")} if led.get("path") else {}
    for i, p in enumerate(led.get("archive") or []):
        out[f"archive{i}"] = p
    return out


def _ledger_argv(ctx):
    led = ctx["cfg"]["overview"]["ledger"]
    args = _py(ctx, "audit/audit-claim-ledger.py") + ["--base-dir", led["base_dir"], "--ledger", led["path"], "--json"]
    credits = Path(ctx["ws"]) / "human" / "credits.txt"
    if credits.is_file():
        args += ["--credits", str(credits)]
    return args


def _bib(cfg):
    b = get(cfg, "inputs.bib")
    return {"bib": b} if b else {}


def _positioning_argv(ctx):
    args = _py(ctx, "audit/audit-claim-positioning.py") + ["--base-dir", ".", "--json"]
    if ctx["inputs"].get("bib"):
        args += ["--bib", ctx["inputs"]["bib"]]
    return args


def _numbers_inputs(cfg):
    out = {"ledger": get(cfg, "inputs.number_ledger")} if get(cfg, "inputs.number_ledger") else {}
    for i, p in enumerate(get(cfg, "inputs.number_artifacts") or []):
        out[f"artifact{i}"] = p
    return out


def _fingerprint_venue_argv(ctx):
    corpus = get(ctx["cfg"], "target.venue_corpus.dir")
    return _py(ctx, "audit/audit-prose-fingerprint.py") + ["--target", ".", "--baseline", str(Path(corpus).expanduser()),
                                                           "--json"]


def _fingerprint_bib_argv(ctx):
    args = _py(ctx, "audit/audit-prose-fingerprint.py") + [
        "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "inputs.literature")).expanduser()), "--json"]
    for g in get(ctx["cfg"], "inputs.literature_exclude") or []:
        args += ["--exclude", g]
    return args


def _venue_outside(cfg):
    out = []
    m = get(cfg, "target.venue_corpus.dir")
    if m:
        out.append(str(Path(m).expanduser()))
    return out


def _literature_outside(cfg):
    lit = get(cfg, "inputs.literature")
    return [str(Path(lit).expanduser())] if lit else []


def _intent_outside(cfg):
    card = get(cfg, "target.intent_card")
    return [str(Path(card).expanduser())] if card else []


def _notes_inputs(cfg):
    return {f"note{i}": p for i, p in enumerate(get(cfg, "inputs.notes") or [])}


def _notes_argv(ctx):
    return _node(ctx, "note/notes-lint.mjs") + ["--json"] + [v for k, v in sorted(ctx["inputs"].items())]


def _none(cfg):
    return {}


def _no_outside(cfg):
    return []


CHECKS = [
    {"id": "claim-ledger", "name": "主张台账", "kind": "script", "scripts": ["audit/audit-claim-ledger.py"],
     "formats": ["latex"], "instead": {"markdown": "citation-fidelity"},
     "scope": {"kind": "cite"}, "needs": ["overview.ledger"],
     "inputs": _ledger_inputs, "outside": _no_outside, "argv": _ledger_argv},
    {"id": "claim-positioning", "name": "定位", "kind": "script", "scripts": ["audit/audit-claim-positioning.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _bib, "outside": _no_outside, "argv": _positioning_argv},
    {"id": "number-ledger", "name": "数字台账", "kind": "script", "scripts": ["audit/audit-number-ledger.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "numbers"}, "needs": ["inputs.number_ledger"],
     "inputs": _numbers_inputs, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-number-ledger.py") + [
         "--base-dir", ".", "--ledger", ctx["inputs"]["ledger"], "--json"]},
    {"id": "fingerprint-venue", "name": "文风·对照目标刊物", "kind": "script",
     "scripts": ["audit/audit-prose-fingerprint.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["target.venue_corpus.dir"],
     "inputs": _none, "outside": _venue_outside, "argv": _fingerprint_venue_argv},
    {"id": "fingerprint-bibliography", "name": "文风·对照参考文献", "kind": "script",
     "scripts": ["audit/audit-prose-fingerprint.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["inputs.literature"],
     "inputs": _none, "outside": _literature_outside, "argv": _fingerprint_bib_argv},
    {"id": "verify-refs", "name": "参考文献条目", "kind": "script", "scripts": ["verify-refs/verify-refs.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "none"}, "needs": ["inputs.bib"],
     "inputs": _bib, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "verify-refs/verify-refs.py") + ["--bib", ctx["inputs"]["bib"], "--json"]},
    {"id": "notes-lint", "name": "阅读笔记格式", "kind": "script", "scripts": ["note/notes-lint.mjs"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "none"}, "needs": ["inputs.notes"],
     "inputs": _notes_inputs, "outside": _no_outside, "argv": _notes_argv},
    {"id": "citation-fidelity", "name": "引文忠实度", "kind": "script", "scripts": ["audit/audit-citation-fidelity.mjs"],
     "formats": ["markdown"], "instead": {"latex": "claim-ledger"},
     "scope": {"kind": "cite"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _node(ctx, "audit/audit-citation-fidelity.mjs") + ["--base-dir", ".", "--json"]},
    {"id": "citation-style", "name": "引文格式", "kind": "script", "scripts": ["scripts/audit-citations.py"],
     "formats": ["markdown"], "instead": {"latex": None},
     "scope": {"kind": "cite"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-citations.py") + ["--base-dir", ".", "--json"]},
    {"id": "british-english", "name": "英式拼写", "kind": "script", "scripts": ["scripts/audit-british-english.py"],
     "formats": ["markdown"], "instead": {"latex": None},
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-british-english.py") + ["--base-dir", ".", "--json"]},
    {"id": "paragraph-logic", "name": "段落逻辑", "kind": "script", "scripts": ["scripts/audit-logic.py"],
     "formats": ["markdown"], "instead": {"latex": None},
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _py(ctx, "scripts/audit-logic.py") + ["--base-dir", ".", "--json"]},
    {"id": "word-count", "name": "字数", "kind": "script", "scripts": ["map/count-words.mjs"],
     "formats": ["markdown"], "instead": {"latex": None},
     "scope": {"kind": "all"}, "needs": [],
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _node(ctx, "map/count-words.mjs") + ["--base-dir", ".", "--json"]},
    {"id": "readers", "name": "读者组", "kind": "panel",
     "scripts": ["readers/build-reader-packet.py", "readers/check-reader-output.py", "readers/tally-readers.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "sections", "config": "target.readers.sections", "default": ["A", "I"]},
     "needs": ["target.intent_card"],
     "inputs": _none, "outside": _intent_outside, "argv": None},
]

UNWIRED = {
    "review/audit-review-findings.py":
        "审的是 /review 写出的发现文件能否解析、是否只落在声明读过的文件里；对象是评审报告，不是稿件，由 /review 自己调用",
    "scripts/audit-public-content.py":
        "审的是 AWT 公开仓自己有没有混进私密内容；对象是工具仓，不是用户的稿件，由 AWT 的测试套件调用",
}

# Skills present on disk but not installed for Codex, with the reason. Empty: every skill is installed.
SKILLS_NOT_INSTALLED = {}


def by_id(cid):
    return next(c for c in CHECKS if c["id"] == cid)


def wired_scripts():
    return {s for c in CHECKS for s in c["scripts"]}


def wiring_problems(registered, skills, installed):
    """Problems with how the toolkit's checks and skills reach a manuscript. Empty list = nothing unaccounted for."""
    problems = []
    wired = wired_scripts()
    for name in sorted(set(registered) - wired - set(UNWIRED)):
        problems.append(f"{name}：已登记为检查（check-fails-closed.py），但写作循环既不跑它，也没在 UNWIRED 写理由")
    for name in sorted(wired - set(registered)):
        problems.append(f"{name}：目录里有，但没在 check-fails-closed.py 登记为检查（空目标会不会假绿没人验）")
    for name in sorted(set(UNWIRED) - set(registered)):
        problems.append(f"{name}：在 UNWIRED 里，但已不是登记的检查；删掉这一条")
    for name, reason in sorted(UNWIRED.items()):
        if len((reason or "").strip()) < UNWIRED_REASON_MIN:
            problems.append(f"{name}：UNWIRED 的理由太短（少于 {UNWIRED_REASON_MIN} 字），说清楚为什么它不是对稿件的检查")
    for s in sorted(set(skills) - set(installed) - set(SKILLS_NOT_INSTALLED)):
        problems.append(f"技能 {s}：在 .claude/skills/ 里，但 Codex 安装器不装它，也没在 SKILLS_NOT_INSTALLED 写理由")
    for s in sorted(set(installed) - set(skills)):
        problems.append(f"技能 {s}：安装器要装，但 .claude/skills/ 里没有")
    for c in CHECKS:
        for s in c["scripts"]:
            if not script_path(s).is_file():
                problems.append(f"{c['id']}：脚本 {s} 不在盘上")
    return problems
