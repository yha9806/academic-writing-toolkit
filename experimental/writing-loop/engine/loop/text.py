"""Text primitives: normalisation, section parsing, sentence splitting, hashing.

Everything here is deterministic and model-free. A sentence's identity across
versions is decided in sentences.py; this module only cuts and fingerprints.
"""
import hashlib
import re
import unicodedata

_QUOTES = {"’": "'", "‘": "'", "“": '"', "”": '"'}


def norm(s):
    s = unicodedata.normalize("NFKC", s)
    for a, b in _QUOTES.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def text_hash(s):
    return hashlib.sha1(norm(s).encode("utf-8")).hexdigest()[:10]


# Abbreviations that end in a period but do not end a sentence.
SPLIT = re.compile(r"(?<!\bal\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bcf\.)(?<!\bvs\.)(?<=[.!?])\s+(?=[A-Z\[\"“(])")


def split_sentences(paragraph):
    par = re.sub(r"\s+", " ", paragraph.strip())
    if not par:
        return []
    if par.startswith("[") and par.endswith("]"):  # a bracketed editorial note is one unit
        return [par]
    return [s for s in SPLIT.split(par) if s]


def markdown_sections(md):
    """Return [(heading_text, body)] for level-2 headings, in order."""
    out = []
    matches = list(re.finditer(r"^## (.+?)\s*$", md, re.M))
    for k, m in enumerate(matches):
        end = matches[k + 1].start() if k + 1 < len(matches) else len(md)
        out.append((m.group(1), md[m.end():end].strip("\n")))
    return out


_LIST_MARK = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
_TEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.M)
_TEX_HEADING = re.compile(r"^\s*\\(?:sub){0,2}section\*?\{((?:[^{}]|\{[^{}]*\})*)\}(?:\\label\{[^}]*\})?[ \t]*$", re.M)
_TEX_ABSTRACT = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)


def latex_sections(tex):
    """Return [(heading_text, body)]: the abstract environment as "Abstract", then every
    \\section / \\subsection / \\subsubsection up to the next heading. Comments are dropped (an escaped \\% is text)."""
    tex = _TEX_COMMENT.sub("", tex)
    out = [("Abstract", m.group(1).strip("\n")) for m in _TEX_ABSTRACT.finditer(tex)]
    body_tex = _TEX_ABSTRACT.sub("", tex)
    matches = list(_TEX_HEADING.finditer(body_tex))
    for k, m in enumerate(matches):
        end = matches[k + 1].start() if k + 1 < len(matches) else len(body_tex)
        out.append((m.group(1).strip(), body_tex[m.end():end].strip("\n")))
    return out


def sentences_of(md, section_rules, fmt="markdown"):
    """Cut a markdown (or, with fmt="latex", a LaTeX) draft into sentences.

    section_rules: list of {"match": regex on the heading, "prefix": "A", "kind": "title"|"prose"}.
    Returns [{"label", "section", "par", "text"}]; labels are positional (A03, I4.2, T01)
    and are only for display. Stable identity is assigned later.
    """
    out = []
    for heading, body in (latex_sections(md) if fmt == "latex" else markdown_sections(md)):
        rule = next((r for r in section_rules if re.search(r["match"], heading)), None)
        if rule is None:
            continue
        p = rule["prefix"]
        if rule.get("kind") == "title":
            lines = [_LIST_MARK.sub("", ln).strip() for ln in body.splitlines()]
            for i, ln in enumerate([x for x in lines if x], 1):
                out.append({"label": f"{p}{i:02d}", "section": p, "par": 1, "text": ln})
            continue
        pars = [x for x in re.split(r"\n\s*\n", body) if x.strip()]
        n = 0
        for pi, par in enumerate(pars, 1):
            for si, s in enumerate(split_sentences(par), 1):
                n += 1
                label = f"{p}{n:02d}" if rule.get("flat") else f"{p}{pi}.{si}"
                out.append({"label": label, "section": p, "par": pi, "text": s})
    return out
