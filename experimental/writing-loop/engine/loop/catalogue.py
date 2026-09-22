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
SCOPES = ("all", "cite", "numbers", "sections", "none", "tree")
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


def credits_path(cfg):
    """Where the author's accepted method credits live: the ledger's own setting, as the overview reads it."""
    led = get(cfg, "overview.ledger") or {}
    if led.get("credits"):
        return Path(led["credits"]).expanduser()
    return Path(cfg["_ws"]) / "human" / "credits.txt" if cfg.get("_ws") else None


def _ledger_argv(ctx):
    led = ctx["cfg"]["overview"]["ledger"]
    args = _py(ctx, "audit/audit-claim-ledger.py") + ["--base-dir", led["base_dir"], "--ledger", led["path"], "--json"]
    credits = credits_path(ctx["cfg"])
    if credits and credits.is_file():
        args += ["--credits", str(credits)]
    return args


def _credits_outside(cfg):
    """The author's accepted method credits change what the ledger audit reports."""
    p = credits_path(cfg)
    return [str(p)] if p else []


def _literature_optional(cfg):
    """Reading notes and source PDFs a Markdown citation check reads when the repository has them."""
    return {"literature": get(cfg, "inputs.literature_dir") or "literature"}


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
    """What the panel is keyed on besides the text: the intent card and the directed questions."""
    return [str(Path(p).expanduser()) for p in (get(cfg, "target.intent_card"), get(cfg, "target.readers.questions")) if p]


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
     "scope": {"kind": "cite"}, "needs": ["overview.ledger"], "config_keys": ["overview.ledger"],
     "inputs": _ledger_inputs, "outside": _credits_outside, "argv": _ledger_argv},
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
     "scope": {"kind": "all"}, "needs": ["target.venue_corpus.dir"], "config_keys": ["target.venue"],
     "inputs": _none, "outside": _venue_outside, "argv": _fingerprint_venue_argv},
    {"id": "fingerprint-bibliography", "name": "文风·对照参考文献", "kind": "script",
     "scripts": ["audit/audit-prose-fingerprint.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["inputs.literature"], "config_keys": ["inputs.literature_exclude"],
     "inputs": _none, "outside": _literature_outside, "argv": _fingerprint_bib_argv},
    {"id": "structure-venue", "name": "句子结构·对照目标刊物", "kind": "script",
     "scripts": ["audit/audit-prose-structure.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["target.venue_corpus.dir"], "config_keys": ["target.venue"],
     "inputs": _none, "outside": _venue_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-prose-structure.py") + [
         "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "target.venue_corpus.dir")).expanduser()), "--json"]},
    {"id": "structure-bibliography", "name": "句子结构·对照参考文献", "kind": "script",
     "scripts": ["audit/audit-prose-structure.py"],
     "formats": ["latex", "markdown"], "instead": {},
     "scope": {"kind": "all"}, "needs": ["inputs.literature"], "config_keys": ["inputs.literature_exclude"],
     "inputs": _none, "outside": _literature_outside,
     "argv": lambda ctx: _py(ctx, "audit/audit-prose-structure.py") + [
         "--target", ".", "--baseline", str(Path(get(ctx["cfg"], "inputs.literature")).expanduser()), "--json"]
         + [x for g in (get(ctx["cfg"], "inputs.literature_exclude") or []) for x in ("--exclude", g)]},
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
     "scope": {"kind": "cite"}, "needs": [], "optional": _literature_optional,
     "inputs": _none, "outside": _no_outside,
     "argv": lambda ctx: _node(ctx, "audit/audit-citation-fidelity.mjs") + ["--base-dir", ".", "--json"]},
    {"id": "citation-style", "name": "引文格式", "kind": "script", "scripts": ["scripts/audit-citations.py"],
     "formats": ["markdown"], "instead": {"latex": None},
     "scope": {"kind": "cite"}, "needs": [], "optional": _literature_optional,
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
     "needs": ["target.intent_card"], "config_keys": ["target.readers.sections", "target.readers.personas"],
     "inputs": _none, "outside": _intent_outside, "argv": None},
]

UNWIRED = {
    "review/audit-review-findings.py":
        "只验 /review 写出的发现文件能否解析、是否只落在声明读过的文件里；对象是评审报告。/review 本身是模型阅读的稿件评审，"
        "见 MODEL_READ",
    "scripts/check_lost_in_conversation_bench.py":
        "校验 writing-control 基准的夹具目录（三种工作流与控制产物是否齐），对象是基准夹具，不是稿件",
    "scripts/audit-public-content.py":
        "审的是 AWT 公开仓自己有没有混进私密内容；对象是工具仓，不是用户的稿件，由 AWT 的测试套件调用",
}

# Skills present on disk but not installed for Codex, with the reason. Empty: every skill is installed.
SKILLS_NOT_INSTALLED = {}

# Checks a model performs by reading, with no script and so no run record: the loop cannot tell whether they have
# looked at the current draft. They are listed in every coverage table so that their absence is visible.
MODEL_READ = {
    "review": "/review：模型通读稿件，写出带锚点的发现（文件:行 + 原文 + 一句话问题）；没有运行记录，循环看不出它读的是哪一版",
    "audit": "/audit 的 A 数字一致、B 术语与缩写首次定义、C 交叉引用：由模型阅读完成，不是脚本；循环看不出它们查没查过当前稿",
}

# Skills that make no check on a manuscript, with what they do instead.
SKILL_ROLES = {
    "read": "逐页读文献、写带页码的笔记；不对稿件下判断",
    "integrate": "把笔记整合进章节：整合计划、编辑范围、升级规则；不对稿件下判断",
    "export": "把章节转成 Word 与 ZIP；不对稿件下判断",
}

# check-fails-closed.py's NOT_CHECKS, acknowledged here: moving a check there to escape the wiring invariant has to
# be done in two places, on purpose.
NOT_CHECKS_ACK = {
    "export/convert_to_docx.py", "audit/citations.mjs", "audit/quote-fidelity.mjs", "audit/pdf-pages.mjs",
    "audit/build-venue-baseline.py",
}


def by_id(cid):
    return next(c for c in CHECKS if c["id"] == cid)


def project_checks(cfg):
    """A manuscript's own checks (a submission build, a glyph check), declared in the workspace:

        "project_checks": [{"id": "build", "name": "...", "argv": ["python3", "tools/build.py"],
                            "auto": false, "timeout": 900}]

    Each runs on the whole repository archived at HEAD and is stale whenever that tree changes. They make no JSON
    promise, so exit 0 is a pass and anything else a failure. `auto: false` (the default) keeps a slow build out of
    `loop update`: it is run by `loop coverage --run --only <id>`, and until then it shows as not current."""
    out = []
    for p in cfg.get("project_checks") or []:
        argv = list(p["argv"])
        out.append({"id": p["id"], "name": p.get("name") or p["id"], "kind": "script", "project": True,
                    "definition": dict(p),
                    "auto": bool(p.get("auto", False)), "timeout": int(p.get("timeout", 900)), "scripts": [],
                    "formats": ["latex", "markdown"], "instead": {}, "scope": {"kind": "tree"}, "needs": [],
                    "inputs": _none, "outside": _no_outside, "argv": (lambda ctx, argv=argv: argv)})
    return out


def all_checks(cfg):
    """The toolkit's checks and this workspace's own."""
    return CHECKS + project_checks(cfg)


def wired_scripts():
    return {s for c in CHECKS for s in c["scripts"]}


def wiring_problems(registered, skills, installed, documented=None, not_checks=None):
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
    if documented is not None:
        for s in sorted(set(skills) - set(documented)):
            problems.append(f"技能 {s}：装得上，但 docs/skills/README.md 的技能表里没有它，用户发现不了")
    for s in sorted(set(installed) - set(skills)):
        problems.append(f"技能 {s}：安装器要装，但 .claude/skills/ 里没有")
    for c in CHECKS:
        for s in c["scripts"]:
            if not script_path(s).is_file():
                problems.append(f"{c['id']}：脚本 {s} 不在盘上")
    owners = {s.split("/", 1)[0] for s in wired}
    for s in sorted(set(skills) - owners - set(SKILL_ROLES) - set(MODEL_READ)):
        problems.append(f"技能 {s}：没有一项检查在目录里，也没在 SKILL_ROLES / MODEL_READ 说明它是什么")
    if not_checks is not None:
        for name in sorted(set(not_checks) ^ NOT_CHECKS_ACK):
            problems.append(f"{name}：check-fails-closed 的 NOT_CHECKS 与 catalogue.NOT_CHECKS_ACK 不一致（改一边必须改另一边）")
    return problems
