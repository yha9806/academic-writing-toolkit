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


# Arguments that name things rather than say them: citation keys, labels, file paths. Their contents are not words.
_TEX_KEYARG = re.compile(r"\\(?:cite[a-z]*|ref|eqref|autoref|[cC]ref|label|input|include|includegraphics|url|href)\*?"
                         r"(?:\[[^\]]*\])*\{[^{}]*\}")
_WORD = re.compile(r"(?<![\\A-Za-z0-9])[A-Za-z][A-Za-z'\-]*")
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
BEFORE_FIRST = "(第一个标题之前)"
_MD_TOP = re.compile(r"^## ", re.M)
_TEX_DOC = re.compile(r"\\begin\{document\}")


def prose_words(body):
    """Words of prose in a section body: letter-led tokens, not command names, citation keys or labels; each CJK
    character counts as one word."""
    body = _TEX_COMMENT.sub("", body)
    body = _TEX_KEYARG.sub(" ", body)
    return len(_WORD.findall(body)) + len(_CJK.findall(body))


def _before_first(md, fmt):
    """The text a reader meets before the first heading the section cutter knows: a markdown draft's lines above its
    first level-2 heading; a LaTeX draft's body between \\begin{document} (or the start) and the first sectioning
    command, without the abstract, which is cut on its own."""
    if fmt == "latex":
        tex = _TEX_COMMENT.sub("", md)
        m = _TEX_DOC.search(tex)
        body = tex[m.end():] if m else tex
        body = _TEX_ABSTRACT.sub("", body)
        h = _TEX_HEADING.search(body)
        return body[: h.start()] if h else body
    m = _MD_TOP.search(md)
    return md[: m.start()] if m else md


def section_coverage(md, section_rules, fmt="markdown", ignore=()):
    """How much of the draft the section rules keep. sentences_of skips a heading no rule matches without a word;
    this counts what that skipped: words under kept headings, under headings the config chose to ignore, and under
    headings nothing names, listed with their word counts in draft order. Text before the first heading (a title page,
    authors, keywords) is counted apart, as before_first: it is front matter in a normal draft, and the whole draft in
    one the cutter cannot cut, which the caller tells apart by kept == 0."""
    kept = ignored = dropped = 0
    missing = []
    for heading, body in (latex_sections(md) if fmt == "latex" else markdown_sections(md)):
        n = prose_words(body)
        if any(re.search(r["match"], heading) for r in section_rules):
            kept += n
        elif any(re.search(p, heading) for p in ignore):
            ignored += n
        else:
            dropped += n
            if n:
                missing.append({"heading": heading, "words": n})
    return {"kept": kept, "ignored": ignored, "dropped": dropped, "missing": missing,
            "before_first": prose_words(_before_first(md, fmt))}


_TEX_BREAK = re.compile(r"\\\\\*?(?:\s*\[[^\]]*\])?")
_TEX_ESCAPED = re.compile(r"\\([%&_#$])")
_HOLD = {c: chr(0xE000 + i) for i, c in enumerate("%&_#$")}  # private-use stand-ins while & and ~ are spaced out
_TEX_CMD = re.compile(r"\\[A-Za-z@]+\*?")
_TEX_SPACING = re.compile(r"\\(?:[hv]space|kern|[hv]skip|rule)\*?(?:\{[^{}]*\})+")
_TEX_SYMBOL = re.compile(r"\\[^A-Za-z\s]")


def tex_plain(tex):
    """The words a reader of a LaTeX figure or table source would see, joined into plain text. Order matters: a line
    break (with its optional spacing) goes first, so a comment right after it is still a comment; escaped characters
    are kept as characters, ties (~) and cell separators become spaces, command names and delimiters are removed and
    their text kept. For scanning wordings, not for display: coordinates and option keys stay as noise."""
    t = _TEX_BREAK.sub(" ", tex)
    t = _TEX_COMMENT.sub("", t)
    t = _TEX_KEYARG.sub(" ", t)
    t = _TEX_SPACING.sub(" ", t)
    t = t.replace("\\-", "")  # a discretionary hyphen joins the word
    t = re.sub(r"\\\s", " ", t)  # control space
    t = _TEX_ESCAPED.sub(lambda m: _HOLD[m.group(1)], t)
    t = t.replace("&", " ").replace("~", " ")
    t = _TEX_CMD.sub(" ", t)
    t = _TEX_SYMBOL.sub(" ", t)
    t = re.sub(r"[{}\[\]]", " ", t)
    for c, h in _HOLD.items():
        t = t.replace(h, c)
    return re.sub(r"\s+", " ", t).strip()


def glob_match(path, pattern):
    """Path globbing with directory semantics: * and ? stay within one path segment, ** spans segments (and, as
    **/, may match none). fnmatch lets * cross '/', so figures/*.tex would also take figures/old/x.tex."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        elif pattern[i] == "[" and "]" in pattern[i + 2:]:
            j = pattern.index("]", i + 2)
            body = pattern[i + 1:j]
            body = "^" + body[1:] if body.startswith("!") else body
            out, i = out + "[" + body.replace("\\", "\\\\") + "]", j + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.fullmatch(out, path) is not None


TEXT_SUFFIXES = (".tex", ".md", ".txt", ".tikz", ".pgf")


def resolve_listed(specs, files):
    """[(spec, [paths])] for a config list of paths, directories and globs against the files present: a glob matches
    with glob_match; a path present is itself; otherwise a directory yields its text files (never a tree listing)."""
    out = []
    for spec in specs:
        if any(ch in spec for ch in "*?["):
            names = sorted(n for n in files if glob_match(n, spec) and n.endswith(TEXT_SUFFIXES))
        elif spec in files:
            names = [spec]
        else:
            d = spec.rstrip("/") + "/"
            names = sorted(n for n in files if n.startswith(d) and n.endswith(TEXT_SUFFIXES))
        out.append((spec, names))
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
