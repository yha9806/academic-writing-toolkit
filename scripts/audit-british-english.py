#!/usr/bin/env python3
"""Detect and optionally fix common US spellings in thesis text, or, with --mode consistent, report spellings that
mix the two conventions.

Python 3.8 stdlib only. The fixer is intentionally conservative: it only
replaces whole words in Markdown text files and preserves simple title case.

--mode british (the default) flags the US forms in REPLACEMENTS. --mode consistent is for venues that accept either
convention but not a mixture: it sorts words into families (-ize/-ise, -yze/-yse, -or/-our, -er/-re, -l-/-ll-,
-og/-ogue, and a few single words), and a family written both ways is an issue at each occurrence of whichever form
is rarer. Words spelt the same way in both conventions (advise, otherwise, size) are not counted, and a capitalised
word in mid-sentence is taken for a name ("Research Center") and skipped. It does not say which convention is
right, only that the text uses both.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List

REPLACEMENTS: Dict[str, str] = {
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "center": "centre",
    "color": "colour",
    "colors": "colours",
    "emphasize": "emphasise",
    "emphasized": "emphasised",
    "favor": "favour",
    "favors": "favours",
    "labor": "labour",
    "modeling": "modelling",
    "organize": "organise",
    "organized": "organised",
    "theorize": "theorise",
    "utilize": "utilise",
}


ROOTS = ("chapters", "literature/reading_notes")

# --mode consistent ------------------------------------------------------------------------------------------------
# -ise in both conventions, or -ize in both: never evidence of either.
SAME_BOTH = {"advise", "arise", "chastise", "comprise", "compromise", "concise", "cruise", "demise", "despise",
             "devise", "disguise", "enterprise", "excise", "exercise", "expertise", "franchise", "guise", "improvise",
             "incise", "likewise", "merchandise", "noise", "otherwise", "paradise", "poise", "praise", "precise",
             "premise", "promise", "raise", "reprise", "revise", "rise", "supervise", "surmise", "surprise", "televise",
             "treatise", "wise", "size", "resize", "oversize", "capsize", "seize", "prize", "maize", "baize",
             "bruise", "turquoise", "tortoise", "porpoise", "mortise", "chemise", "valise", "anise"}
IZE = re.compile(r"([a-z]{3,}?)i([sz])(e|es|ed|ing|ation|ations|er|ers)")
YZE = re.compile(r"(ana|para|cata|dia|electro|hydro|photo)ly([sz])(e|es|ed|ing|er|ers)")
# Each family: (name, British form, American form), matched against the whole word. Stems with suffixes, not
# prefixes: "literature" starts like "liter" and is neither, "cataloguing" starts like "catalog" and is British.
_OUR = r"(col|behavi|fav|hon|lab|neighb|hum|rig|vap|harb|flav|endeav|tum|od|arm|vig)"
_OUR_TAIL = r"(s|ed|ing|able|ably|al|ally|ite|ites|ful|less|ist|ists|er|ers|hood|hoods|ise|ize|ised|ized|ises|izes)?"
_RE = r"(cent|fib|theat|lit|calib|spect|somb|lust)"
_LL = r"(model|label|travel|cancel|signal|fuel|level|channel|counsel|total|dial|marshal|tunnel|quarrel|rival|equal)"
FAMILIES = [
    ("-our/-or", re.compile(_OUR + "our" + _OUR_TAIL), re.compile(_OUR + "or" + _OUR_TAIL)),
    ("-re/-er", re.compile(_RE + r"r(e|es|ed)|centring"), re.compile(_RE + r"er(s|ed)?|centering")),
    ("-ll-/-l-", re.compile(_LL + r"l(ed|ing|er|ers)"), re.compile(_LL + r"(ed|ing|er|ers)")),
    ("-ogue/-og", re.compile(r"(catalog|dialog|analog)u(e|es|ed|ing)"), re.compile(r"(catalog|dialog|analog)(s|ed|ing)?")),
    ("grey/gray", re.compile(r"grey(s|er|est|ish|ed|ing)?"), re.compile(r"gray(s|er|est|ish|ed|ing)?")),
    ("sceptic/skeptic", re.compile(r"sceptic(s|al|ally|ism)?"), re.compile(r"skeptic(s|al|ally|ism)?")),
    ("judgement/judgment", re.compile(r"judgements?"), re.compile(r"judgments?")),
    ("acknowledgement/acknowledgment", re.compile(r"acknowledgements?"), re.compile(r"acknowledgments?")),
    ("defence/defense", re.compile(r"defences?"), re.compile(r"defenses?")),
    ("ageing/aging", re.compile(r"ageing"), re.compile(r"aging")),
]
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _is_name(text: str, start: int) -> bool:
    """A capitalised word that does not open a sentence, a heading or a line is taken for a name."""
    if not text[start:start + 1].isupper():
        return False
    before = text[:start].rstrip(" \t\"'(")
    return bool(before) and before[-1] not in ".!?\n#:"


def spelling_of(word: str):
    """(family, 'uk' | 'us') for a word that belongs to a family, else None."""
    w = word.lower()
    if w in SAME_BOTH:
        return None
    m = YZE.fullmatch(w)
    if m:
        return "-yse/-yze", ("uk" if m.group(2) == "s" else "us")
    m = IZE.fullmatch(w)
    # judged by the base form: "revised" is "revise", spelt -ise in both conventions
    if m and (m.group(1) + "ise") not in SAME_BOTH and (m.group(1) + "ize") not in SAME_BOTH:
        return "-ise/-ize", ("uk" if m.group(2) == "s" else "us")
    for family, uk, us in FAMILIES:
        if uk.fullmatch(w):
            return family, "uk"
        if us.fullmatch(w):
            return family, "us"
    return None


def consistency(files: List[Path], base_dir: Path) -> dict:
    """Families written both ways, and an issue at each occurrence of the rarer form (both forms on a tie)."""
    fams: Dict[str, dict] = {}
    seen = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for m in WORD.finditer(text):
            got = spelling_of(m.group(0))
            if not got or _is_name(text, m.start()):
                continue
            family, side = got
            f = fams.setdefault(family, {"uk": 0, "us": 0, "uk_words": {}, "us_words": {}})
            f[side] += 1
            words = f[side + "_words"]
            words[m.group(0).lower()] = words.get(m.group(0).lower(), 0) + 1
            loc = "{}:{}".format(path.relative_to(base_dir), text.count("\n", 0, m.start()) + 1)
            seen.append((family, side, m.group(0), loc))
    issues = []
    for family, f in fams.items():
        if not (f["uk"] and f["us"]):
            continue
        rarer = "both" if f["uk"] == f["us"] else ("uk" if f["uk"] < f["us"] else "us")
        for fam, side, word, loc in seen:
            if fam == family and rarer in ("both", side):
                issues.append({"kind": "mixed-spelling", "severity": "low", "location": loc, "current": word,
                               "family": family, "convention": "British" if side == "uk" else "American",
                               "counts": {"British": f["uk"], "American": f["us"]}})
    return {"families": fams, "issues": issues}


def markdown_files(base_dir: Path) -> Iterable[Path]:
    for item in ROOTS:
        root = base_dir / item
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.is_file():
                yield path


def roots_present(base_dir: Path) -> List[str]:
    return [item for item in ROOTS if (base_dir / item).is_dir()]


def replacement_for(word: str) -> str:
    repl = REPLACEMENTS[word.lower()]
    if word[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def audit_file(path: Path, base_dir: Path) -> List[dict]:
    text = path.read_text(encoding="utf-8")
    issues: List[dict] = []
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in REPLACEMENTS) + r")\b", re.IGNORECASE)
    for m in pattern.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        current = m.group(0)
        issues.append({
            "kind": "us-spelling",
            "severity": "low",
            "location": "{}:{}".format(path.relative_to(base_dir), line),
            "current": current,
            "replacement": replacement_for(current),
        })
    return issues


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in REPLACEMENTS) + r")\b", re.IGNORECASE)
    new_text = pattern.sub(lambda m: replacement_for(m.group(0)), text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit British English spelling in toolkit projects.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--mode", choices=("british", "consistent"), default="british",
                        help="british: flag US spellings (default); consistent: flag a mixture of the two")
    args = parser.parse_args()
    if args.fix and args.mode == "consistent":
        sys.stderr.write("error: --fix only applies to --mode british (consistent mode does not choose a convention)\n")
        return 2

    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2

    files = list(markdown_files(base_dir))
    # A run that read no Markdown is not a clean run. This used to exit 0 with
    # `issue_count: 0` for a base-dir with no chapters/ and no notes, the same
    # line as a manuscript with nothing to fix (found 2026-09-20).
    present = roots_present(base_dir)
    coverage = {
        "files_scanned": len(files),
        "roots_present": present,
        "roots_missing": [r for r in ROOTS if r not in present],
        "nothing_checked": not files,
    }
    if args.fix:
        changed = [str(p.relative_to(base_dir)) for p in files if fix_file(p)]
        payload = {"schema_version": 2, "changed": changed}
        payload.update(coverage)
        if args.emit_json:
            print(json.dumps(payload, indent=2))
        else:
            print("changed files: {} (of {} read)".format(len(changed), len(files)))
        if not files:
            sys.stderr.write("nothing checked: no Markdown under {} in {}\n".format(" or ".join(ROOTS), base_dir))
            return 2
        return 0

    issues: List[dict] = []
    extra: dict = {}
    if args.mode == "consistent":
        got = consistency(files, base_dir)
        issues, extra = got["issues"], {"families": got["families"]}
    else:
        for path in files:
            issues.extend(audit_file(path, base_dir))
    payload = {"schema_version": 2, "mode": args.mode, "issues": issues, "issue_count": len(issues)}
    payload.update(extra)
    payload.update(coverage)
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            if args.mode == "consistent":
                print("{location}: {current} ({convention}; {family} is written both ways)".format(**issue))
            else:
                print("{location}: {current} -> {replacement}".format(**issue))
        print("scanned {} file(s); {} issue(s)".format(len(files), len(issues)))
    if not files:
        sys.stderr.write("nothing checked: no Markdown under {} in {}\n".format(" or ".join(ROOTS), base_dir))
        return 2
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
