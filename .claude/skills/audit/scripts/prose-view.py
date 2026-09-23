#!/usr/bin/env python3
"""Write the prose a reader sees as Markdown chapters, so that checks written for chapters/*.md can read any draft.

    python3 prose-view.py --out <dir> [--format latex|markdown] FILE...

Writes <dir>/chapters/NN-<name>.md, one per FILE, in the order given. A Markdown file is copied as it is. A LaTeX
file is read the way the changed-sentence audit reads it (pre_tex in audit-sentence-changes.py): lists, citations,
references, labels, footnotes and inline math are handled there; what is left of the markup is then stripped by the
fingerprint audit's rules. On top of that, for the paragraph structure those checks need:

- section headings become Markdown headings (`## Title`), and the abstract environment becomes `## Abstract`;
- floats (figure, table) leave the running text; their captions are collected into one fenced block at the end of
  the chapter. A check that reads paragraphs skips fenced blocks; a check that reads every word still sees them;
- display math, tabulars outside floats and verbatim environments are dropped.

It is an approximation of the text, not a LaTeX parser. Macros the author defined are not expanded, so a word that
lives only inside a custom macro is lost. Exit 0 with the files written; 2 when a file cannot be read or holds no
prose at all.
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DROP_ENVS = ("equation", "align", "gather", "multline", "eqnarray", "displaymath", "tabular", "tikzpicture",
             "verbatim", "lstlisting", "algorithm", "algorithmic", "thebibliography", "CCSXML")
# Commands whose arguments are file names, addresses or definitions, not prose: dropped with their arguments.
NOT_PROSE = re.compile(r"\\(?:input|include|subfile|bibliography|bibliographystyle|addbibresource|includegraphics|"
                       r"url|graphicspath|usepackage|newcommand|renewcommand|providecommand|setcounter|setlength|"
                       r"hypersetup|pagestyle|thispagestyle|vspace|hspace)(?![A-Za-z])\*?(?:\s*\[[^\]]*\])?"
                       r"(?:\s*\{(?:[^{}]|\{[^{}]*\})*\})*")
HEADING = re.compile(r"\\(?:part|chapter|section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*"
                     r"\{((?:[^{}]|\{[^{}]*\})*)\}(?:\s*\\label\{[^}]*\})?")


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [filename]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


SC = _load("audit_sentence_changes", "audit-sentence-changes.py")
FP = SC.fingerprint()
MARK = "\u2063HEADING\u2063"


def _plain(tex):
    """A fragment of LaTeX (a heading, a caption) as plain words."""
    return FP.strip_markup(SC.pre_tex(tex).replace(SC.BREAK, " "), ".tex")


def _tidy(s):
    """What removing a citation or a reference leaves behind: empty brackets and a space before punctuation."""
    s = re.sub(r"\(\s*\)|\[\s*\]", "", s)
    s = re.sub(r"\s+([,.;:!?)])", r"\1", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def latex_view(text):
    body = re.split(r"\\begin\{document\}", text, maxsplit=1)
    text = body[1] if len(body) == 2 else text
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\end\{document\}.*", "", text, flags=re.S)
    captions = []

    def take_float(m):
        SC._replace_command(m.group(0), "caption", lambda b: captions.append(_plain(b)) or "")
        return "\n\n"
    text = re.sub(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", take_float, text, flags=re.S)
    for env in DROP_ENVS:
        text = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}", "\n\n", text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]|\$\$.*?\$\$", "\n\n", text, flags=re.S)
    text = re.sub(r"\\begin\{abstract\}", "\n\n" + MARK + "Abstract" + MARK + "\n\n", text)
    text = re.sub(r"\\end\{abstract\}", "\n\n", text)
    text = HEADING.sub(lambda m: "\n\n" + MARK + _plain(m.group(1)) + MARK + "\n\n", text)
    text = re.sub(r"\\makeatletter.*?\\makeatother", " ", text, flags=re.S)   # internal macros, never prose
    text = NOT_PROSE.sub(" ", text)
    text = re.sub(r"\\(?:maketitle|tableofcontents|printbibliography|appendix|clearpage|newpage|noindent)\b", " ", text)
    # An environment's name is not prose: \begin{center} would otherwise leave the word "center" behind.
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?", " ", text)
    out = []
    for chunk in SC.pre_tex(text).split(SC.BREAK):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith(MARK) and chunk.endswith(MARK) and len(chunk) > 2 * len(MARK):
            out.append("## " + chunk[len(MARK):-len(MARK)].strip())
            continue
        prose = _tidy(FP.strip_markup(chunk, ".tex"))
        if prose:
            out.append(prose)
    if captions:
        out.append("```captions\n" + "\n".join(c for c in captions if c) + "\n```")
    return "\n\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Write a draft's prose as Markdown chapters.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--format", choices=("latex", "markdown"), default=None,
                    help="default: by file suffix (.tex is LaTeX, anything else Markdown)")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    dest = Path(a.out) / "chapters"
    dest.mkdir(parents=True, exist_ok=True)
    written = 0
    for n, name in enumerate(a.files, 1):
        p = Path(name)
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"prose-view: cannot read {name}: {e}\n")
            return 2
        fmt = a.format or ("latex" if p.suffix.lower() == ".tex" else "markdown")
        view = latex_view(raw) if fmt == "latex" else raw
        if not view.strip():
            continue
        (dest / f"{n:02d}-{p.stem}.md").write_text(view, encoding="utf-8")
        written += 1
    if not written:
        sys.stderr.write("prose-view: no prose in any of the files given\n")
        return 2
    print(f"prose-view: {written} chapter(s) in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
