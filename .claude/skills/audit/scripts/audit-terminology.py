#!/usr/bin/env python3
"""Check a draft's words against the venue's: its spelling, one concept written two ways, and stock phrases.

    python3 audit-terminology.py --target <file or dir> --baseline <venue corpus dir> [--domain <dir>]
                                 [--families <tsv>] [--phrases <file>] [--min-baseline N] [--json]

Why this exists. On 2026-10-28 a draft for a venue whose 16 papers spelled the American way in every word family
counted (none of them used a British form) carried catalogue and cataloguing, and its writer found that by counting
with a one-off script. The same count found phrases that literature on the topic used in 10 to 28 papers each and
none of the 16 venue papers did. Nothing in this toolkit read the draft's words against the venue's own.

What it reports, each with the number of venue documents that use the form, and of --domain documents when given:

  spelling  a word spelled the way the venue's minority spells. Each venue document is placed by the spelling pairs
            it uses (British colour, centre, catalogue, modelled, -ise and -yse against American color, center,
            catalog, modeled, -ize and -yze; recoloured is spelled as coloured is), by which kind it uses more. A
            draft word of the kind fewer documents use is reported, with its other spelling, even when the venue
            never uses that word in either spelling.
  drift     one concept written two ways inside the draft: a word spelled both ways; a compound closed up in one
            place and written with a hyphen or a space in another (preregistered, pre-registered); two terms of one
            concept listed in --families (a TSV with columns concept, term), except a long form defined by its
            abbreviation in brackets right after it. A hyphen against a space is left alone: English hyphenates a
            compound before a noun and leaves it open after a verb.
  stock     a phrase from the stock list below (or a --phrases file, one per line) that the draft uses and no venue
            document does, its last word singular or plural. A phrase the venue uses is not reported, however stale
            it reads.
  links     a hint, not counted in the exit: a linking word or phrase the draft uses (opening a sentence or set off
            by commas inside one, as audit-sentence-changes.py reads them) that no venue document uses, named with
            the venue's forms of the same type. The venue's 16 papers used "in contrast" as a link in 8 and "by
            contrast" in none.

Every text is read without its reference list: everything after the last line that holds only References,
Bibliography or Works Cited (a Markdown heading or \\section{References} too), unless that line comes before 30% of
the text. Without the cut, counting phrases in a corpus returned author and venue names first. The report says how
many documents had no such heading and were counted whole. A PDF is read with pdftotext, keeping the hyphen of a
word broken across lines, so that a hyphenated compound is not read as closed. A venue or domain document under 400
words, or one whose text is mostly not words, is set aside and counted.

The counts are document counts: "0 of 16" means no venue document holds the form outside its reference list.
They say what the venue does, not what is right; a term the field has no other word for stays.

Exit: 0 nothing reported; 1 something reported; 2 nothing to read (no prose in the target, fewer venue documents
than --min-baseline, a --families or --phrases file that is missing or empty) or an argument it does not recognise.
"""
import argparse
import csv
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = {".tex", ".md", ".txt", ".pdf"}
MIN_DOC_WORDS = 400
# Space on the heading's line is any but a line break: pdftotext opens a page with a form feed, so "\fReferences" is
# a heading too (one paper in 257 kept its reference list and appendix when only spaces and tabs were allowed).
REF_LINE = re.compile(r"(?im)^[^\S\n]*(?:#+[^\S\n]*)?(?:\\(?:section|chapter)\*?\{)?[^\S\n]*"
                      r"(?:references|bibliography|works cited)[^\S\n]*\}?[^\S\n]*$|\\begin\{thebibliography\}")
LIMITS = ("not measured: a concept named two ways that --families does not list; a hyphen against an open compound; "
          "spelling pairs outside the lists and the -ise and -yse rules; names that look like a spelling (Gray, a "
          "Centre in an affiliation) are counted as words")

# ---------------------------------------------------------------- spelling pairs
# Each rule is (British pattern, American pattern, the tails that map between them). A word matching one side is
# that kind; its other spelling is the stem with the other side's tail. Only tails that both kinds inflect the same
# way are listed: "laborious", "honorary" and "vigorous" have no u in British English either.
_OUR_TAILS = ("", "s", "ed", "ing", "ings", "ful", "fully", "less", "er", "ers", "able", "ably", "ite", "ites",
              "hood", "hoods", "ly", "ise", "ised", "ising", "isation", "ize", "ized", "izing", "ization")
_OUR_STEMS = ("col", "fav", "hon", "lab", "neighb", "rum", "hum", "vig", "rig", "endeav", "harb", "flav", "od", "tum",
              "arm", "vap", "sav")
# behavioural / behavioral; "humoral" and "honorific" are spelled so in British English too, so -al stays with this one.
_BEHAVIOUR_TAILS = _OUR_TAILS + ("al", "ally", "ism", "ist", "ists")
RULES = [
    ("(" + "|".join(_OUR_STEMS) + ")our(" + "|".join(_OUR_TAILS) + ")",
     "(" + "|".join(_OUR_STEMS) + ")or(" + "|".join(_OUR_TAILS) + ")", ("our", "or"), None),
    ("(behavi)our(" + "|".join(_BEHAVIOUR_TAILS) + ")", "(behavi)or(" + "|".join(_BEHAVIOUR_TAILS) + ")",
     ("our", "or"), None),
    ("(cent|fib|theat|calib|meag|somb)r(e|es|ed|ing)", "(cent|fib|theat|calib|meag|somb)er(|s|ed|ing)", ("r", "er"),
     {"e": "", "es": "s", "ed": "ed", "ing": "ing"}),
    ("(defen|offen|preten)c(e|es|eless)", "(defen|offen|preten)s(e|es|eless)", ("c", "s"), None),
    ("(catalog|analog)u(e|es|ed|ing)", "(catalog|analog)(|s|ed|ing)", ("u", ""),
     {"e": "", "es": "s", "ed": "ed", "ing": "ing"}),
    ("(model|label|travel|signal|level|channel|tunnel|fuel|total|funnel|marvel|dial|pedal|shovel|quarrel|rival|equal|"
     "jewel)l(ed|ing|ings|er|ers)",
     "(model|label|travel|signal|level|channel|tunnel|fuel|total|funnel|marvel|dial|pedal|shovel|quarrel|rival|equal|"
     "jewel)(ed|ing|ings|er|ers)", ("l", ""), None),
]
RULES = [(re.compile("^" + b + "$"), re.compile("^" + a + "$"), mid, tails) for b, a, mid, tails in RULES]
WORDS = {"artefact": "artifact", "artefacts": "artifacts", "artefactual": "artifactual", "grey": "gray",
         "greys": "grays", "greyscale": "grayscale", "greyish": "grayish", "greyed": "grayed", "ageing": "aging",
         "aluminium": "aluminum", "enrol": "enroll", "enrols": "enrolls", "enrolment": "enrollment",
         "enrolments": "enrollments", "fulfil": "fulfill", "fulfils": "fulfills", "fulfilment": "fulfillment",
         "skilful": "skillful", "skilfully": "skillfully", "wilful": "willful", "wilfully": "willfully",
         "jewellery": "jewelry", "plough": "plow", "ploughs": "plows", "ploughed": "plowed", "ploughing": "plowing",
         "manoeuvre": "maneuver", "manoeuvres": "maneuvers", "manoeuvred": "maneuvered", "manoeuvring": "maneuvering",
         "sceptic": "skeptic", "sceptics": "skeptics", "sceptical": "skeptical", "scepticism": "skepticism",
         "mould": "mold", "moulds": "molds", "moulded": "molded", "moulding": "molding"}
WORDS_US = {v: k for k, v in WORDS.items()}
# -ise / -isation and -yse are British only where the -ize / -yze spelling of the same word is also met somewhere in
# what was read (the draft, the venue or --domain): "precise", "promise" and "pairwise" have none. The same holds the
# other way round. Words built on "size" are left out (resize, oversize).
ISE = re.compile(r"^([a-z]{4,}?)is(e|es|ed|ing|er|ers|ation|ations|able)$")
IZE = re.compile(r"^([a-z]{4,}?)iz(e|es|ed|ing|er|ers|ation|ations|able)$")
YSE = re.compile(r"^([a-z]{3,}?)ys(e|es|ed|ing|er|ers)$")
YZE = re.compile(r"^([a-z]{3,}?)yz(e|es|ed|ing|er|ers)$")


# A listed word under a prefix is spelled as the word is: recoloured, uncatalogued, multicentre.
PREFIXES = ("re", "un", "dis", "mis", "non", "pre", "multi", "bi", "tri", "sub", "inter", "over", "under")


def listed(w):
    if w in WORDS:
        return "british", WORDS[w]
    if w in WORDS_US:
        return "american", WORDS_US[w]
    for br, am, (bm, am_mid), tails in RULES:
        m = br.match(w)
        if m:
            tail = tails[m.group(2)] if tails else m.group(2)
            return "british", m.group(1) + am_mid + tail
        m = am.match(w)
        if m:
            back = {v: k for k, v in tails.items()} if tails else None
            return "american", m.group(1) + bm + (back[m.group(2)] if back else m.group(2))
    return None


def spelling(w, vocab):
    """("british" or "american", the other spelling) when w is one side of a pair, else None."""
    got = listed(w)
    if got:
        return got
    for p in PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 4:
            got = listed(w[len(p):])
            if got:
                return got[0], p + got[1]
    if "size" in w or w.endswith("wise"):
        return None
    for pat, kind, mid in ((ISE, "british", "iz"), (IZE, "american", "is"), (YSE, "british", "yz"),
                           (YZE, "american", "ys")):
        m = pat.match(w)
        if m:
            other = m.group(1) + mid + m.group(2)
            return (kind, other) if other in vocab else None
    return None


# ---------------------------------------------------------------- stock phrases
# Phrases that literature on a topic uses and a venue may not: on 2026-10-28, four of them appeared in 10 to 28 of
# 257 papers on the draft's topic and in none of the 16 venue papers. Only those the venue does not use are reported.
STOCK = [
    "bridge this gap", "bridge the gap", "bridges this gap", "bridges the gap", "bridging this gap", "bridging the gap",
    "fill this gap", "fills this gap", "address this gap", "addresses this gap",
    "address these challenges", "address this challenge", "addresses these challenges", "tackle these challenges",
    "highlight the need", "highlights the need", "highlighting the need", "underscore the need", "underscores the need",
    "highlight the importance", "highlights the importance", "underscore the importance", "underscores the importance",
    "underscoring the importance", "findings highlight", "findings underscore", "findings reveal", "results highlight",
    "results underscore", "extensive experiments", "comprehensive experiments", "comprehensive benchmark",
    "comprehensive evaluation", "comprehensive analysis", "plays a crucial role", "play a crucial role",
    "plays a pivotal role", "plays a vital role", "pave the way", "paves the way", "paving the way", "shed light on",
    "sheds light on", "shedding light on", "delve into", "delves into", "delving into", "a growing body of",
    "has garnered", "have garnered", "garnered significant attention", "gained significant attention",
    "remains underexplored", "remain underexplored", "remains largely unexplored", "remain largely unexplored",
    "remains an open challenge", "it is worth noting", "it is important to note", "in the realm of",
    "the landscape of", "a myriad of", "a plethora of", "a wide array of", "unlock the potential",
    "unlocking the potential", "harness the power", "harnessing the power", "leverage the power", "a testament to",
    "rather than merely", "rather than simply", "holistic understanding", "nuanced understanding",
    "deeper understanding", "intricate interplay", "multifaceted", "seamlessly integrate", "seamlessly integrates",
    "ever-evolving", "ever-growing", "rapidly evolving", "paradigm shift", "game-changer", "cutting-edge",
    "a significant step", "marks a significant", "in today's",
]

COMPOUND_STOP = set("a an the of and or to in on at by for with from as is are was were be been it its we our they "
                    "their this that these those not no any every some one may can will would should must all each "
                    "both such more most other than then so do does did has have had up out off over under into".split())


# ---------------------------------------------------------------- reading
def module(name, file):
    path = HERE / file
    if not path.is_file():
        die(f"{file} is not beside this script; this audit reads prose the way it does")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def die(msg):
    sys.stderr.write(f"audit-terminology: {msg}\n")
    sys.exit(2)


def pdf_text(path):
    if not shutil.which("pdftotext"):
        return None
    try:
        out = subprocess.run(["pdftotext", "-q", str(path), "-"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return re.sub(r"-\n\s*", "-", out.stdout) if out.stdout else None


def read(path, fp, gate):
    """(the prose a reader sees without the reference list, one space between words; whether a list was cut)."""
    suffix = path.suffix.lower()
    raw = pdf_text(path) if suffix == ".pdf" else path.read_text(encoding="utf-8", errors="replace")
    if not raw:
        return "", False
    body = fp.cut_references(raw, REF_LINE)
    cut = len(body) < len(raw)
    if suffix == ".tex":
        body = fp.strip_markup(gate.pre_tex(body), ".tex")
    elif suffix == ".md":
        body = fp.strip_markup(gate.pre_md(body), ".md")
    return re.sub(r"\s+", " ", body.replace(gate.BREAK.strip(), " ")).strip(), cut


def files(target):
    p = Path(target)
    if p.is_file():
        return [p] if p.suffix.lower() in SUFFIXES else []
    return sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in SUFFIXES) if p.is_dir() else []


class Doc:
    def __init__(self, name, text):
        self.name, self.text = name, text
        self.low = text.lower()
        self.words = Counter(re.findall(r"[a-z]+", self.low))
        self.hyphened = Counter(re.findall(r"[a-z]+(?:-[a-z]+)+", self.low))


def corpus(target, fp, gate):
    """(kept documents, set aside, kept documents in which no reference list was found to cut)."""
    kept, aside, uncut = [], 0, 0
    for f in files(target):
        t, cut = read(f, fp, gate)
        if len(t.split()) < MIN_DOC_WORDS or fp.word_share(t) < fp.MIN_WORD_SHARE:
            aside += 1
            continue
        kept.append(Doc(str(f.relative_to(target)) if Path(target).is_dir() else f.name, t))
        uncut += not cut
    return kept, aside, uncut


# ---------------------------------------------------------------- counting
def phrase_pattern(phrase, case=False):
    """A stock phrase, its last word also in the plural: a venue that writes "comprehensive benchmarks" uses the
    phrase (two of 16 venue papers on 2026-10-28, which a singular-only count read as none)."""
    words = re.split(r"[\s-]+", phrase.strip())
    return re.compile(r"(?<![\w-])" + r"[\s-]+".join(map(re.escape, words)) + r"s?(?![\w-])", 0 if case else re.I)


def term_regex(term):
    return r"(?<![\w-])" + r"\s+".join(map(re.escape, re.split(r"\s+", term.strip()))) + r"s?"


def term_pattern(term):
    """A --families term: an abbreviation in capitals matches in capitals only; a plural s is allowed."""
    return re.compile(term_regex(term) + r"(?![\w-])", 0 if term.isupper() else re.I)


def holds(doc, pat, first):
    """Whether doc holds pat; first is a lower-case word the match must contain, checked before the expression."""
    return first in doc.low and pat.search(doc.text) is not None


def form_count(doc, form):
    """Occurrences of a word, a hyphenated compound or an open one in doc."""
    if " " in form:
        return len(re.findall(r"(?<![\w-])" + re.escape(form) + r"(?![\w-])", doc.low))
    if "-" in form:
        return doc.hyphened[form]
    return doc.words[form]


def docs_with(docs, fn):
    return sum(1 for d in docs if fn(d))


def placement(doc, vocab):
    """Which spelling a document uses more of: british, american, mixed (as many of each) or neither."""
    c = Counter()
    for w, n in doc.words.items():
        s = spelling(w, vocab)
        if s:
            c[s[0]] += n
    if not c:
        return "neither"
    if c["british"] == c["american"]:
        return "mixed"
    return "british" if c["british"] > c["american"] else "american"


def read_families(path):
    p = Path(path)
    if not p.is_file():
        die(f"no --families file at {path}")
    fam = {}
    with open(p, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            c, t = (row.get("concept") or "").strip(), (row.get("term") or "").strip()
            if c and t:
                fam.setdefault(c, []).append(t)
    if not fam:
        die(f"{path}: no rows with a concept and a term (columns concept, term)")
    return fam


def read_phrases(path):
    p = Path(path)
    if not p.is_file():
        die(f"no --phrases file at {path}")
    got = [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
    if not got:
        die(f"{path}: no phrase in it")
    return got


def definitions(text, terms):
    """Counter of terms that appear as a long form followed by its abbreviation in brackets, both from one family:
    'support vector machine (SVM)' defines SVM; that use of each is not a second name."""
    out = Counter()
    for long in terms:
        for short in terms:
            if long == short:
                continue
            n = len(re.findall(term_regex(long) + r"\s*\(\s*" + re.escape(short) + r"s?\s*\)", text,
                               0 if long.isupper() else re.I))
            if n:
                out[long] += n
                out[short] += n
    return out


def main():
    ap = argparse.ArgumentParser(description="Check a draft's words against the venue's.")
    ap.add_argument("--target", required=True, help="the draft: a file or a directory of .tex, .md, .txt or .pdf")
    ap.add_argument("--baseline", required=True, help="the venue's published papers")
    ap.add_argument("--domain", help="literature on the draft's topic, counted beside the venue for each finding")
    ap.add_argument("--families", help="TSV with columns concept, term: the names one concept goes by")
    ap.add_argument("--phrases", help="more stock phrases, one per line")
    ap.add_argument("--min-baseline", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    gate = module("sentence_changes", "audit-sentence-changes.py")
    fp = module("fingerprint", "audit-prose-fingerprint.py")

    drafted = [(f, read(f, fp, gate)[0]) for f in files(a.target)]
    drafted = [(f, t) for f, t in drafted if t]
    if not drafted:
        die(f"no prose in the target {a.target}")
    draft = Doc("draft", " ".join(t for _, t in drafted))
    venue, venue_aside, venue_uncut = corpus(a.baseline, fp, gate)
    if len(venue) < a.min_baseline:
        die(f"the baseline {a.baseline} gave {len(venue)} documents of {MIN_DOC_WORDS} words or more "
            f"({venue_aside} set aside); --min-baseline is {a.min_baseline}")
    domain, domain_aside, domain_uncut = corpus(a.domain, fp, gate) if a.domain else ([], 0, 0)
    families = read_families(a.families) if a.families else {}
    stock = STOCK + (read_phrases(a.phrases) if a.phrases else [])

    vocab = set(draft.words) | {w for d in venue + domain for w in d.words}
    nv, nd = len(venue), len(domain)

    def counts(fn):
        out = {"venue_docs": docs_with(venue, fn)}
        if domain:
            out["domain_docs"] = docs_with(domain, fn)
        return out

    placed = Counter(placement(d, vocab) for d in venue)
    venue_spelling = {k: placed.get(k, 0) for k in ("american", "british", "mixed", "neither")}
    majority = ("american" if placed["american"] > placed["british"] else
                "british" if placed["british"] > placed["american"] else None)

    marked = {w: spelling(w, vocab) for w in draft.words}
    marked = {w: s for w, s in marked.items() if s}
    spelled = []
    for w, (kind, other) in sorted(marked.items()):
        if majority and kind != majority:
            row = {"form": w, "kind": kind, "draft_count": draft.words[w], "other": other}
            row.update(counts(lambda d, w=w: d.words[w] > 0))
            row.update({"other_" + k: v for k, v in counts(lambda d, o=other: d.words[o] > 0).items()})
            spelled.append(row)

    drift = []
    for w, (kind, other) in sorted(marked.items()):
        if kind == "british" and draft.words[other]:
            forms = {w: draft.words[w], other: draft.words[other]}
            drift.append({"kind": "spelling", "forms": forms,
                          "venue_docs": {f: docs_with(venue, lambda d, f=f: d.words[f] > 0) for f in forms},
                          **({"domain_docs": {f: docs_with(domain, lambda d, f=f: d.words[f] > 0) for f in forms}}
                             if domain else {})})
    groups = {}
    for h in draft.hyphened:
        parts = h.split("-")
        if any(p in COMPOUND_STOP for p in parts):
            continue
        groups["".join(parts)] = ["".join(parts), h, " ".join(parts)]
    tokens = list(re.findall(r"[a-z]+", draft.low))
    for x, y in zip(tokens, tokens[1:]):
        if x + y in draft.words and len(x) >= 3 and len(y) >= 3 and x not in COMPOUND_STOP and y not in COMPOUND_STOP:
            groups.setdefault(x + y, [x + y, f"{x}-{y}", f"{x} {y}"])
    for closed, variants in sorted(groups.items()):
        forms = {v: form_count(draft, v) for v in variants}
        forms = {v: n for v, n in forms.items() if n}
        if closed in forms and len(forms) >= 2:
            drift.append({"kind": "compound", "forms": forms,
                          "venue_docs": {v: docs_with(venue, lambda d, v=v: form_count(d, v) > 0) for v in forms},
                          **({"domain_docs": {v: docs_with(domain, lambda d, v=v: form_count(d, v) > 0)
                                              for v in forms}} if domain else {})})
    for concept, terms in families.items():
        defined = definitions(draft.text, terms)
        forms = {t: len(term_pattern(t).findall(draft.text)) - defined[t] for t in terms}
        forms = {t: n for t, n in forms.items() if n > 0}
        if len(forms) >= 2:
            has = {t: (lambda d, p=term_pattern(t), w=t.lower().split()[0]: holds(d, p, w)) for t in terms}
            drift.append({"kind": "family", "concept": concept, "forms": forms,
                          "venue_docs": {t: docs_with(venue, has[t]) for t in terms},
                          **({"domain_docs": {t: docs_with(domain, has[t]) for t in terms}} if domain else {})})

    staled, stock_in_venue = [], {}
    for phrase in dict.fromkeys(stock):
        pat = phrase_pattern(phrase)
        n = len(pat.findall(draft.text))
        if not n:
            continue
        first = re.split(r"[\s-]+", phrase.strip().lower())[0]
        c = counts(lambda d, pat=pat, first=first: holds(d, pat, first))
        if c["venue_docs"]:
            stock_in_venue[phrase] = c["venue_docs"]
        else:
            staled.append({"phrase": phrase, "draft_count": n, **c})

    # Linking words and phrases, read as the changed-sentence audit reads them: one that opens a sentence or is set
    # off by commas inside one. A form no venue document uses is named with the forms of its type that the venue
    # does use. A hint, not counted: with a few dozen venue documents a sound form can be missing by chance.
    gate.FP = fp
    in_draft = Counter(f for _, t in drafted for s in gate.sentences(t) for f in gate.links(s))
    venue_links = Counter(f for d in venue for f in {f for s in gate.sentences(d.text) if 5 <= len(s.split()) <= 120
                                                     for f in gate.links(s)})
    unused = []
    for f, n in sorted(in_draft.items()):
        if venue_links[f]:
            continue
        kind = gate.link_type(f)
        same = sorted(((g, k) for g, k in venue_links.items() if kind and gate.link_type(g) == kind),
                      key=lambda x: (-x[1], x[0]))[:3]
        unused.append({"form": f, "draft_count": n, "venue_docs": 0, "type": kind, "venue_uses": dict(same)})

    issues = len(spelled) + len(drift) + len(staled)
    summary = (f"拼写与会场不一致 {len(spelled)}，同一概念两种写法 {len(drift)}，会场不用的套话 {len(staled)}"
               if issues else "术语与会场一致") + (f"；会场不用的连接写法 {len(unused)}（提示）" if unused else "")
    out = {"schema_version": 1, "target_files": [str(f) for f, _ in drafted], "draft_words": len(draft.text.split()),
           "venue": {"documents": nv, "set_aside": venue_aside, "no_reference_heading": venue_uncut,
                     "spelling": venue_spelling, "majority": majority},
           "domain": ({"documents": nd, "set_aside": domain_aside, "no_reference_heading": domain_uncut}
                      if a.domain else None),
           "spelling": spelled, "drift": drift, "stock": staled, "stock_in_venue": stock_in_venue,
           "links": unused, "link_forms": {f: {"draft": n, "venue_docs": venue_links[f]} for f, n in sorted(in_draft.items())},
           "issues": issues, "summary_zh": summary, "limits": LIMITS}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        dom = (f"; domain {nd} documents ({domain_aside} set aside, {domain_uncut} with no reference heading found)"
               if a.domain else "")
        print(f"terminology: draft {len(drafted)} file(s), {out['draft_words']} words; venue {nv} documents "
              f"({venue_aside} set aside, {venue_uncut} with no reference heading found, so counted whole){dom}")
        print(f"venue spelling, by document: American {venue_spelling['american']}, British {venue_spelling['british']}, "
              f"as many of each {venue_spelling['mixed']}, neither {venue_spelling['neither']}")
        of = lambda r, k="": (f"venue {r[k + 'venue_docs']} of {nv}"  # noqa: E731
                              + (f", domain {r[k + 'domain_docs']} of {nd}" if domain else ""))
        if spelled:
            print(f"\nspelled the way fewer venue documents spell ({len(spelled)}):")
            for r in spelled:
                print(f"  {r['form']} x{r['draft_count']} ({r['kind']}; {of(r)}); {r['other']}: {of(r, 'other_')}")
        if drift:
            print(f"\none concept written two ways in the draft ({len(drift)}):")
            for r in drift:
                name = f"{r['kind']} '{r['concept']}'" if r["kind"] == "family" else r["kind"]
                print(f"  {name}: " + ", ".join(f"{f} x{n}" for f, n in r["forms"].items())
                      + "; venue " + ", ".join(f"{f} {n}" for f, n in r["venue_docs"].items()) + f" of {nv}"
                      + ("; domain " + ", ".join(f"{f} {n}" for f, n in r["domain_docs"].items()) + f" of {nd}"
                         if domain else ""))
        if staled:
            print(f"\nstock phrases no venue document uses ({len(staled)}):")
            for r in staled:
                print(f"  {r['phrase']} x{r['draft_count']} ({of(r)})")
        if stock_in_venue:
            print("\nstock phrases the venue also uses, not reported: "
                  + ", ".join(f"{p} ({n} of {nv})" for p, n in stock_in_venue.items()))
        if unused:
            print(f"\nlinking forms no venue document uses ({len(unused)}; a hint, not counted):")
            for r in unused:
                print(f"  {r['form']} x{r['draft_count']}" + (f"; its {r['type']} links in the venue: "
                      + ", ".join(f"{g} ({k} of {nv})" for g, k in r["venue_uses"].items()) if r["venue_uses"] else ""))
        if not issues:
            print("\nnothing reported")
        print(f"\n{LIMITS}")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
