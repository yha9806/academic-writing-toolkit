#!/usr/bin/env python3
"""Build what a panel of readers reads: numbered paragraphs, one prompt per persona, and a record of the version.

    python3 build-reader-packet.py --workspace <loop workspace> --out <dir> [--sections A,I] [--questions q.tsv]
    python3 build-reader-packet.py --text <file> --out <dir> [--bib refs.bib] [--questions q.tsv]

With --workspace the paragraphs come from the writing loop's index (the tracked draft at its head, the sections
named in the workspace's target.readers.sections unless --sections is given), and packet.json records which
sentences, at which commit, against which intent card, so `loop coverage` can tell when a later edit has made the
panel's reading stale. With --text any file is split on blank lines.

LaTeX is made readable, not summarised: a citation becomes the author-year form a reader of the published paper
would see (from --bib, or the workspace's inputs.bib), never "[cite]"; a cross-reference becomes "§x"; figures and
their descriptions are dropped. Directed questions (--questions: one `id<TAB>question` per line) are asked of every
reader after the free questions.

Output in --out: manuscript.txt, prompt_<persona>.txt per persona, packet.json.
Exit: 0 written; 2 nothing to read (no paragraph, unreadable input), or an argument it does not recognise.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
# AWT_LOOP_ENGINE: the engine copy a mutation run is testing; otherwise the one in this checkout.
ENGINE = Path(os.environ.get("AWT_LOOP_ENGINE") or ROOT / "experimental" / "writing-loop" / "engine")
if not ENGINE.is_dir():
    # A user-scope install has no engine beside it; the installer records the checkout's (references/loop-engine.txt).
    _rec = Path(__file__).resolve().parent.parent / "references" / "loop-engine.txt"
    if _rec.is_file():
        ENGINE = Path(_rec.read_text(encoding="utf-8").strip())

PERSONAS = {
    "R1": "a researcher in the manuscript's field whose first language is not English; you read English papers daily",
    "R2": "a senior reviewer for the target venue whose first language is English",
}

INSTRUCTIONS = """READER INSTRUCTIONS
You are a reader, not an editor. Persona: {persona}. You have NOT read this manuscript before and know nothing about
its authors or its history. Ignore any background notes, memory, project files or earlier conversation you may be
able to see: read only the text below, as this reader would.

Below is part of a manuscript submitted to {venue}. Paragraphs are numbered [P1], [P2], ... Read them in order,
once, carrying forward what you have read.

For EACH paragraph report:
- "believe": one sentence: what you now believe the manuscript is claiming or doing, given everything so far
- "expect": one sentence: what you expect to read next
- "reread": the first 4-6 words (verbatim) of any sentence in this paragraph you had to go back and re-read
- "guessed": words or phrases (verbatim) whose meaning you had to guess

After the last paragraph report:
- "remember": the three things you will remember from this manuscript, most important first
- "why_accept": one sentence: the best reason, if any, to accept this paper
- "closest_prior_work": what kind of existing work it most resembles
- "reuse": what, if anything, you could apply to your own work after reading this
- "writing_got_in_way": anything about how it is written that got in your way (or "nothing")
{directed_block}- "outside_knowledge": any knowledge you used that is not in the text (or "none"). Report this last.

Output ONLY one JSON object with the keys packet, paragraphs, remember, why_accept, closest_prior_work, reuse,
writing_got_in_way{directed_keys}, outside_knowledge, where packet is exactly "{packet_id}" and paragraphs is a list of
{{"p": 1, "believe": "...", "expect": "...", "reread": [], "guessed": []}}. No other text.

MANUSCRIPT
{manuscript}
"""


def die(msg, code=2):
    sys.stderr.write(f"build-reader-packet: {msg}\n")
    sys.exit(code)


def sha(b):
    return hashlib.sha1(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ bibliography

def bib_entries(text):
    """{key: "Surname et al., 2020"} from a BibTeX file; only author and year are read."""
    out = {}
    for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", text or "", re.S):
        key, body = m.group(1), m.group(2)
        au = re.search(r"\bauthor\s*=\s*[{\"](.*?)[}\"]\s*,?\s*\n", body, re.S | re.I)
        yr = re.search(r"\byear\s*=\s*[{\"]?(\d{4})", body, re.I)
        names = [n.strip() for n in re.split(r"\s+and\s+", au.group(1))] if au else []

        def surname(n):
            n = re.sub(r"[{}]", "", n)
            return n.split(",")[0].strip() if "," in n else (n.split()[-1] if n.split() else n)
        if not names:
            who = key
        elif len(names) == 1:
            who = surname(names[0])
        elif len(names) == 2:
            who = f"{surname(names[0])} and {surname(names[1])}"
        else:
            who = f"{surname(names[0])} et al."
        out[key] = f"{who}, {yr.group(1)}" if yr else who
    return out


# ------------------------------------------------------------------ LaTeX to reading text

CITE = re.compile(r"\\(citet|citep|cite|citeauthor|citeyear)\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def balanced_end(t, k):
    """Index just past the group that opens at t[k] == "{". An escaped brace (\\{ or \\}) is text, not structure: counted,
    one unpaired \\{ in alt text swallowed the rest of the paragraph."""
    depth, k = 1, k + 1
    while k < len(t) and depth:
        if t[k] == "\\":
            k += 2
            continue
        depth += {"{": 1, "}": -1}.get(t[k], 0)
        k += 1
    return k


def drop_command(t, name):
    """Remove \\name[...]{...} with its optional argument and its whole balanced argument; a figure's alt text
    (\\Description, whose acmart form takes an optional short text) is for screen readers, and a reader of the page
    never sees it."""
    out, i = [], 0
    rx = re.compile(r"\\" + name + r"(?![A-Za-z])\s*(?:\[[^\]]*\])?\s*\{")
    while True:
        m = rx.search(t, i)
        if not m:
            return "".join(out) + t[i:]
        out.append(t[i:m.start()])
        i = balanced_end(t, m.end() - 1)


def drop_env_args(t):
    """A tabular's column specification (and a tabular*/tabularx width) is typesetting, not text."""
    rx = re.compile(r"\\begin\{(tabular\*?|tabularx|array)\}\s*(?:\[[^\]]*\])?")
    out, i = [], 0
    while True:
        m = rx.search(t, i)
        if not m:
            return "".join(out) + t[i:]
        out.append(t[i:m.start()] + " ")
        k = m.end()
        for _ in range(1 if m.group(1) in ("tabular", "array") else 2):
            while k < len(t) and t[k].isspace():
                k += 1
            if k < len(t) and t[k] == "{":
                k = balanced_end(t, k)
        i = k


def readable(text, bib, unknown):
    """What a reader of the typeset page sees, as plain text. Applied to a whole paragraph: an environment or a
    figure's alt text often spans several indexed sentences, and cleaning each alone leaves its markup behind."""
    def cite(m):
        cmd, keys = m.group(1), [k.strip() for k in m.group(2).split(",") if k.strip()]
        parts = []
        for k in keys:
            if k not in bib:
                unknown.add(k)
            parts.append(bib.get(k, k))
        if cmd == "citet":
            return "; ".join(re.sub(r", (\d{4})$", r" (\1)", p) for p in parts)
        return "(" + "; ".join(parts) + ")"
    t = CITE.sub(cite, text)
    t = drop_command(t, "Description")
    t = drop_env_args(t)
    t = re.sub(r"\\(?:input|include|includegraphics)\*?(?:\[[^\]]*\])?\{[^}]*\}", "", t)
    t = re.sub(r"\\caption\s*(?:\[[^\]]*\])?\s*\{", " Caption: {", t)
    t = re.sub(r"\\begin\{[^}]*\}(?:\[[^\]]*\])*", " ", t)
    t = re.sub(r"\\end\{[^}]*\}", " ", t)
    t = re.sub(r"\\item\[([^\]]*)\]", r"\1", t)
    t = re.sub(r"~", " ", t)
    t = re.sub(r"\\(?:S)?\\?(?:ref|eqref|autoref|cref|Cref)\{[^}]*\}", "§x", t)
    t = re.sub(r"\\S\s*§x", "§x", t)
    t = re.sub(r"\\label\{[^}]*\}", "", t)
    t = re.sub(r"\\(?:emph|textit|textbf|texttt|text|mathrm|mbox)\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\times", "×", t)
    t = re.sub(r"\\%", "%", t)
    t = re.sub(r"\\,|\\;|\\!", " ", t)
    t = re.sub(r"\{=\}", "=", t)
    t = re.sub(r"\$([^$]*)\$", lambda m: re.sub(r"[{}\\]", "", m.group(1)), t)
    t = re.sub(r"\\[a-zA-Z]+\*?", "", t)
    t = re.sub(r"[{}]", "", t)
    t = re.sub(r"---", "—", t).replace("--", "–")
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------------ sources of paragraphs

def from_workspace(ws, sections_arg):
    if not ENGINE.is_dir():
        die(f"--workspace needs the writing loop engine at {ENGINE}; this copy of the skill does not have it")
    sys.path.insert(0, str(ENGINE))
    from loop import catalogue as K  # noqa: E402
    from loop import config as C  # noqa: E402
    from loop import coverage as V  # noqa: E402
    from loop import targets as TG  # noqa: E402
    try:
        cfg = C.load(ws)
    except (OSError, ValueError) as e:
        die(f"workspace config unreadable: {e}")
    check = dict(K.by_id("readers"))
    if sections_arg:
        cfg.setdefault("target", {}).setdefault("readers", {})["sections"] = sections_arg
    sentences, head = V.current_sentences(ws)
    if sentences is None:
        die("the workspace has no index yet (run `loop update` first)")
    prefixes = K.get(cfg, "target.readers.sections") or check["scope"]["default"]
    kept = [s for s in sentences if V.in_sections(s.get("section"), prefixes)]
    paras, order = {}, []
    for s in kept:
        key = (s.get("section"), s.get("par"))
        if key not in paras:
            paras[key] = []
            order.append(key)
        paras[key].append(s)
    bibtext = ""
    b = K.get(cfg, "inputs.bib")
    if b:
        import subprocess
        r = subprocess.run(["git", "-C", str(cfg["repo"]), "show", f"{head}:{b}"], capture_output=True)
        bibtext = r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    snap = V.snapshot(check, cfg, sentences, head)
    state, card = TG.intent_card_state(cfg)
    personas = K.get(cfg, "target.readers.personas")
    if personas:
        PERSONAS.clear()
        PERSONAS.update(personas)
    questions = K.get(cfg, "target.readers.questions")
    source = {"workspace": str(Path(ws).resolve()), "commit": head, "sections": prefixes, "questions_file": questions,
              "format": V.draft_format(cfg), "venue": K.get(cfg, "target.venue"),
              "intent_card": {"path": card, "state": state,
                              "sha1": sha(Path(card).read_bytes()) if card and Path(card).is_file() else None}}
    return [[(s["text"], s["sid"], s["hash"]) for s in paras[k]] for k in order], bibtext, source, snap


def from_text(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        die(f"cannot read {path}: {e}")
    raw = re.sub(r"(?m)(?<!\\)%.*$", "", raw)
    raw = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", "", raw, flags=re.S)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
    blocks = [b for b in blocks if not re.fullmatch(r"\\[a-zA-Z]+\*?(\{[^}]*\})*", b)]
    return [[(b, None, sha(b)[:10])] for b in blocks], "", {"text": str(Path(path).resolve()), "sha1": sha(raw)}, None


def read_questions(path):
    out = []
    if not path:
        return out
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        qid, _, q = line.partition("\t")
        if not q.strip():
            die(f"{path}:{i}: a directed question is `id<TAB>question`")
        out.append({"id": qid.strip(), "question": q.strip()})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--workspace")
    src.add_argument("--text")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sections", help="comma-separated section prefixes (workspace mode)")
    ap.add_argument("--bib", help="BibTeX file for author-year citations")
    ap.add_argument("--questions", help="directed questions: id<TAB>question per line")
    ap.add_argument("--venue", help="how the prompt names the venue (default: the workspace's target.venue)")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        sys.exit(2 if e.code else 0)

    if a.workspace:
        paras, bibtext, source, snap = from_workspace(a.workspace, a.sections.split(",") if a.sections else None)
    else:
        paras, bibtext, source, snap = from_text(a.text)
    if a.bib:
        try:
            bibtext = Path(a.bib).read_text(encoding="utf-8")
        except OSError as e:
            die(f"cannot read --bib {a.bib}: {e}")
    if not paras:
        die("no paragraph to give the readers: nothing was built")
    bib, unknown = bib_entries(bibtext), set()
    rendered = []
    for i, para in enumerate(paras, 1):
        text = readable(" ".join(t for t, _, _ in para), bib, unknown)
        rendered.append({"p": i, "text": text, "sids": [s for _, s, _ in para if s], "hashes": [h for _, _, h in para]})
    manuscript = "\n\n".join(f"[P{r['p']}] {r['text']}" for r in rendered)
    questions = read_questions(a.questions or (source.get("questions_file") and str(Path(source["questions_file"]).expanduser())))
    venue = a.venue or source.get("venue") or "a journal"
    directed_block = "".join(f'- "{q["id"]}": {q["question"]}\n' for q in questions)
    directed_keys = "".join(f", {q['id']}" for q in questions)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manuscript.txt").write_text(manuscript + "\n", encoding="utf-8")
    # The packet id travels through every reader's output, so an output written for another version of the text
    # cannot be tallied against this one.
    packet_id = sha(json.dumps([manuscript, questions, sorted(PERSONAS.items()), venue]))[:12]
    prompts = {}
    for pid, persona in PERSONAS.items():
        text = INSTRUCTIONS.format(persona=persona, venue=venue, directed_block=directed_block,
                                   directed_keys=directed_keys, manuscript=manuscript, packet_id=packet_id)
        (out / f"prompt_{pid}.txt").write_text(text, encoding="utf-8")
        prompts[pid] = {"file": f"prompt_{pid}.txt", "sha1": sha(text)}
    packet = {"schema": 1, "packet_id": packet_id, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "source": source,
              "paragraphs": rendered, "questions": questions, "personas": PERSONAS, "prompts": prompts,
              "unknown_citation_keys": sorted(unknown), "snapshot": snap}
    (out / "packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(r["text"].split()) for r in rendered)
    print(f"packet: {len(rendered)} paragraphs, {words} words, {len(questions)} directed question(s), "
          f"{len(PERSONAS)} personas -> {out}")
    if unknown:
        print(f"  citation keys not in the bibliography, left as keys: {', '.join(sorted(unknown))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
