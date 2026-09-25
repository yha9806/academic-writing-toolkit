#!/usr/bin/env python3
"""Check each rewritten sentence against the sentence it replaced, and against the venue's own sentences.

    python3 audit-sentence-changes.py --target <file or dir> --base <file or dir> [--baseline <dir>] [--carriers <file>] [--json]
    python3 audit-sentence-changes.py --pairs <tsv with columns id, old, new> [--baseline <dir>] [--json]
    (a pairs file may add the columns verdict and reason once the author has read the rewrites)
    (either form: --venue-cache <file> keeps the venue's measured sentences between runs)

audit-prose-fingerprint.py and audit-prose-structure.py measure a whole document: rates per 1,000 words and
distributions across sections. A dozen rewritten sentences barely move those rates, and neither audit reads a
proposal that has not yet been applied. On one real round of proposed corrections most rewrites came back longer
than the sentences they replaced, several added an explanatory colon or a semicolon (the construction the venue
audit had already flagged in that manuscript), and others added a relative clause, a participial phrase or an
adjective. Neither document audit could see it: the rewrites sat in a separate file, and once applied they were a
few sentences in fifteen thousand words.

So this reads sentences one at a time, and only the ones that changed. Every changed sentence is judged; none is
waved through for lack of a predecessor. A sentence of the target that does not occur in the base is paired with
the most similar base sentence that no longer occurs (a revision). If it has none, it may be a piece of a sentence
that was split (most of its words come from one old sentence) or the result of a merge (it holds most of the words
of several old sentences); a split is judged as the old sentence against the sum of its pieces, a merge as the sum
of the old sentences against the new one. What is left is an addition, judged against the venue.

For a revision, a split or a merge it reports what the rewrite added: words (three or more), subordinate clauses
counted as occurrences gained (dropping one "because" and adding one "which" is still an added clause), adverbs and
modifiers counted net (swapping one term for another adds none), commas (when punctuation as a whole grew), colons, semicolons,
dashes, parentheses, subordinate clauses, adverbs, modifiers, prepositional phrases (two or more), a subordinate
opener. A merge is flagged as such: it is how short sentences become long ones. An addition is flagged for any
colon, semicolon, dash or worded parenthesis, and for length or density above the venue's 75th percentile of
sentences (pooled across its documents: one sentence is compared with published sentences, not with documents); a
revision that grows past the 90th is flagged for that too. Without --baseline additions are held to default ceilings
measured on one journal, and the report says so.

Adverbs are words ending in -ly and a closed list of others (also, still, only, even, very, often, instead ...);
connectives such as however, thus and consequently are not counted. Modifiers stand in for a part-of-speech
tagger, which this stdlib script does not have: participles after a noun ("the images collected from", "applied to
characters"), a participle or adjective-suffixed word after a determiner ("a controlled test"), a comma followed by
a participle, words with adjective suffixes (-al, -ive, -ous, -ic, -able, -ful, -less, -ary; a noun stoplist
applies), a closed list of common adjectives, and hyphenated prenominal compounds. It misses adjectives outside
those forms and relative clauses opened by "that", which is not counted as a clause for the reason
audit-prose-structure.py gives. Because gains are counted, a noun such as "manual" that the suffix rule mistakes
for an adjective only matters when the rewrite introduces it.

Before splitting, LaTeX list items and figure or table captions are kept as prose (the fingerprint audit drops
them), blank lines and Markdown headings and list items end a sentence, reference and citation commands and inline comments are removed, inline math becomes one placeholder word,
footnotes become parentheses, and headings are dropped. A pairs file is read with no quoting: a stray quotation
mark stays text.

The --pairs form is for proposals: run it on the rewrites before anyone reads them. The --target/--base form is for
a draft after the edit; the writing loop runs it against the last version at which it flagged nothing.

The thresholds (three words, two prepositions, the 75th and 90th percentiles) were set against one real round: a
handful of rewrites an author rejected for adding length, clauses, modifiers and punctuation, and a few dozen changes
the author accepted. That is the data they were fitted on, not a test of them. The test is a later round: give the
pairs file a verdict column (accepted or rejected, as the author decided; revised counts as rejected, empty as not
yet judged) and a reason column, and the report sets the flags against the verdicts, naming the script by its hash
so that the thresholds that judged are the ones frozen before the round. The flags are prompts to re-read a sentence, not targets: a revision
may need a clause to stay faithful to its source, and then the flag is the reason to check that it earns it.

A sentence removed without a successor (nothing in the target revises, splits or merges it) is judged too. Every check
of the draft rewards deletion: word and rate ceilings fall, a sentence nobody wrote cannot be flagged. On one
manuscript a research question, three qualifiers and a denominator were deleted and every check passed. A removal is
flagged when it carried something: it matches a pattern in --carriers (one regular expression per line; the writing
loop passes the claims ledger's required wordings), or it holds a number, or a limiting qualifier (only, at most, may,
exploratory, of N, in this study ...). A flagged removal needs a reason like a flagged rewrite. The report counts
removals and flagged removals apart, so "nothing flagged" is not read as "nothing removed".

Exit: 0 no changed sentence is flagged (including no change at all, reported as such); 1 at least one flagged;
2 nothing to compare (no prose in the target or the base, an empty or malformed pairs file, a baseline too small
to give percentiles) or an argument it does not recognise.
"""
import argparse
import csv
import difflib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

SUB_WORDS = {"which", "where", "when", "while", "whereas", "although", "though", "because", "since", "unless",
             "whether", "if", "after", "before", "until", "who", "whom", "whose", "once", "whereby", "wherein"}
SUB = re.compile(r"\b(" + "|".join(sorted(SUB_WORDS)) + r")\b", re.I)
# after / before / since / until followed by a number or an -ing word are prepositions ("since 2019", "after training");
# "once a year" and "once more" are adverbs.
TEMPORAL_PREP = re.compile(r"\b(?:after|before|since|until)\s+(?:\d|\w+ing\b)|\bonce\s+(?:a|an|per|every|more|again|or|and)\b"
                           r"|\bonce[.,;]", re.I)
AS_CLAUSE = re.compile(r"\bas\s+(?:(?:the|a|an|this|these|those|it|they|we|he|she|its|their|our)\s+)?\w+\s+"
                       r"(?:is|are|was|were|has|have|had|did|does|do|can|could|will|would|may|might|must|should|"
                       r"required|requires|expected|noted|shown|described|reported|suggested)\b", re.I)
SO_THAT = re.compile(r"\b(?:so|such)\s+that\b", re.I)
OPENER = re.compile(r"^(?:Where|When|If|Whether|Although|Though|While|Because|Since|Unless|Once|Whereas|As)\b")
PREP = re.compile(r"\b(?:of|in|for|with|by|between|from|on|at|into|across|against|within|without|under|over|"
                  r"through|about|among|beyond|via)\b", re.I)
LY = re.compile(r"\b([A-Za-z]{3,}ly)\b")
NOT_ADVERB = {"early", "family", "apply", "supply", "reply", "rely", "assembly", "anomaly", "italy", "july",
              "daily", "weekly", "monthly", "yearly", "ply", "multiply", "comply", "imply", "poly", "holy", "belly",
              "rally", "tally", "ally", "fly", "jelly", "bully", "lily", "folly",
              # adjectives more often than adverbs in this register ("is likely to"); counted as modifiers instead
              "likely", "unlikely", "costly", "timely", "friendly", "scholarly", "orderly",
              # connectives: they order an argument; the prose audits count them separately
              "consequently", "accordingly", "similarly", "conversely", "finally", "firstly", "secondly", "lastly",
              "thirdly"}
OTHER_ADVERBS = {"also", "still", "only", "even", "very", "often", "instead", "just", "rather", "quite", "already",
                 "almost", "never", "always", "merely", "perhaps", "indeed", "too", "again", "sometimes", "somewhat",
                 "seldom", "soon", "hardly", "nearly", "far", "much", "well"}
# "far", "much" and "well" are adverbs when they modify ("far fewer", "much larger", "well known"); as other parts of
# speech they rarely appear in a rewrite that did not have them before, and only gains are counted.
DET = r"(?:a|an|the|this|these|those|its|their|our|his|her|each|every|no|any|some|one|two|three|four|such|" \
      r"several|all|both|many)"
# "that" is left out: as a relative pronoun it would read the verb after it ("two that reported") as a modifier.
BE_HAVE = {"is", "are", "was", "were", "be", "been", "being", "has", "have", "had", "get", "gets", "got", "seem",
           "seems", "seemed", "appear", "appears", "appeared", "become", "becomes", "became", "remain", "remains",
           "remained", "not", "it", "they", "we", "he", "she", "i", "you", "can", "could", "will", "would", "may",
           "might", "must", "should"}
IRREGULAR_PARTICIPLES = {"given", "taken", "written", "shown", "known", "chosen", "drawn", "seen", "grown", "thrown",
                         "spoken", "broken", "hidden", "made", "built", "found", "held", "kept", "left", "set", "sent",
                         "told", "taught", "brought", "bought", "done", "cut", "put", "spent", "lost", "paid", "laid"}
PARTICIPLE = r"(?:\w{3,}ed|" + "|".join(sorted(IRREGULAR_PARTICIPLES)) + r")"
POST_PREP = r"(?:by|from|in|on|to|with|for|at|into|across|under|over|through|as|during|within|between|against|via)"
PARTICIPLE_AFTER_NOUN = re.compile(r"\b(\w+)\s+(" + PARTICIPLE + r")\s+" + POST_PREP + r"\b", re.I)
PARTICIPLE_AFTER_COMMA = re.compile(r",\s+(\w{3,}(?:ing|ed))\b")
PRENOMINAL = re.compile(r"\b" + DET + r"\s+(\w{3,}(?:ed|ing))\s+[a-z]", re.I)
ADJ_SUFFIX = re.compile(r"\b([a-z]{3,}(?:al|ive|ous|ic|able|ible|ful|less|ary))\b")
NOUN_STOP = {"manual", "manuals", "retrieval", "proposal", "signal", "journal", "material", "potential", "individual",
             "interval", "trial", "portal", "approval", "removal", "arrival", "rival", "animal", "capital", "festival",
             "terminal", "principal", "criminal", "survival", "renewal", "denial", "referral", "tutorial", "rival",
             "archive", "objective", "perspective", "initiative", "alternative", "incentive", "motive", "narrative",
             "representative", "directive", "detective", "native", "topic", "music", "logic", "public", "mechanic",
             "graphic", "fabric", "clinic", "critic", "rhetoric", "arithmetic", "epic", "traffic", "table", "variable",
             "cable", "summary", "library", "dictionary", "boundary", "vocabulary", "anniversary", "salary",
             "glossary", "commentary", "diary", "itinerary", "secretary", "sanctuary", "century", "several",
             "general", "usual", "total", "normal", "original", "local", "global", "final", "initial", "central",
             "legal", "equal", "natural", "social", "special", "digital", "visual", "textual", "cultural",
             "historical", "technical", "typical", "critical", "classical", "musical", "physical", "practical",
             "logical", "chemical", "medical", "political", "statistical", "empirical", "numerical", "vertical",
             "identical", "lexical", "theoretical", "biblical", "ethical", "optical", "radical", "tropical",
             "heuristic", "metric", "statistic", "rubric", "characteristic", "academic", "arithmetic"}
# The -al adjectives in the stoplist are real adjectives; they are removed because a manuscript's own subject words
# ("historical", "cultural", "lexical") recur in every rewrite and are not modifiers the rewrite chose to add.
COMMON_ADJ = {"new", "old", "large", "small", "big", "open", "same", "different", "other", "own", "single", "whole",
              "full", "main", "major", "minor", "key", "clear", "strong", "weak", "good", "bad", "high", "low", "long",
              "short", "wide", "broad", "narrow", "simple", "specific", "real", "true", "false", "various", "certain",
              "possible", "similar", "recent", "modern", "late", "best", "better", "worse", "worst", "rich", "poor",
              "deep", "fine", "hard", "easy", "free", "fair", "fast", "slow", "great", "entire", "overall", "prior",
              "particular", "multiple", "unique", "common", "rare", "unknown", "robust", "reliable", "relevant",
              "important", "significant", "substantial", "considerable", "notable", "strict", "careful", "novel",
              "complex", "diverse", "distinct", "explicit", "implicit", "direct", "indirect", "sharp", "trained",
              "independent", "comprehensive", "extensive", "systematic", "rigorous", "subtle", "crucial", "genuine",
              "likely", "unlikely", "costly", "timely", "friendly", "scholarly", "orderly"}
HYPHEN_PRENOMINAL = re.compile(r"\b([a-z]+(?:-[a-z]+)+)\s+(?!(?:and|or|but|nor|the|for|with|from|into|that|than|are|was|were|has|have)\b)[a-z]{3,}")
DASH = re.compile(r"---|—|―|\s--\s|\s–\s|\s-\s")
PAREN_WORDED = re.compile(r"\(([^()]*)\)")
ABBREV = re.compile(r"\b(e\.g|i\.e|et al|cf|vs|Fig|Figs|Eq|Eqs|Sec|Secs|No|approx|resp|ca)\.", re.I)
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
# pre_tex puts this where LaTeX ends a unit without a full stop (a list item, a caption, a heading); the fingerprint's
# markup stripping collapses the line breaks that would otherwise have marked it.
BREAK = " \u00b6 "
FEATURES = ["words", "clauses", "commas", "colons", "semicolons", "dashes", "parentheses", "adverbs", "modifiers",
            "prepositions", "opener"]
# A revision is "longer" when it gains at least this many words. In the round the thresholds were set on, the
# rejected rewrites that grew gained well over this, and no accepted revision gained more than two.
LONGER_WORDS = 3
# Prepositional phrases gained before a revision is flagged: one is often the fact the correction adds.
MORE_PREPOSITIONS = 2
MATCH_MIN = 0.40
# What a removed sentence can carry besides a pattern the caller names. Numbers: a count, a denominator, a result.
# Qualifiers: the words that keep a claim no larger than its evidence. Both lists catch only what is written here.
REMOVED_NUMBER = re.compile(r"\d")
REMOVED_QUALIFIER = re.compile(
    r"\b(only|at most|at least|no more than|may|might|could|approximately|roughly|estimated|exploratory|"
    r"preliminary|tentative|suggests?|limited to|except|unless|in (?:this|our) (?:study|benchmark|sample|pool|setting|data)|"
    r"(?:out )?of \d+)\b|仅|只有|至多|至少|可能|大约|估计|探索性|初步|除非|在本(?:研究|基准|文)", re.I)
PIECE_MIN = 0.60   # share of a sentence's content words found in another before one is read as part of the other
VENUE_PCT = 90      # a revision that grows past this is long or dense for the venue
ADDITION_PCT = 75   # an added sentence has nothing to be compared with, so it is held to a typical published one
FP = None
MIN_VENUE_SENTENCES = 1000
MIN_VENUE_DOCUMENTS = 5
STOPWORDS = {"the", "a", "an", "of", "in", "for", "with", "by", "and", "or", "to", "is", "are", "was", "were", "be",
             "that", "this", "it", "its", "on", "at", "as", "from", "not", "we", "our", "their", "they", "than"}
LIMITS = ("not measured: adjectives outside the suffix and word lists, nouns used as modifiers, relative clauses "
          "opened by 'that', a comma splice beyond the comma it adds; the writing loop reads committed versions only")


def die(msg):
    sys.stderr.write(f"audit-sentence-changes: {msg}\n")
    sys.exit(2)


def fingerprint():
    path = HERE / "audit-prose-fingerprint.py"
    if not path.is_file():
        die(f"the fingerprint audit is not beside this script ({path}); both must read prose the same way")
    spec = importlib.util.spec_from_file_location("fingerprint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- reading LaTeX

def _braced(text, start):
    """(content, end) of the brace group opening at text[start] == '{', nested groups included."""
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], len(text)


def _replace_command(text, name, fn):
    out, i = [], 0
    pat = re.compile(r"\\" + name + r"\*?\s*(?:\[[^\]]*\])?\s*\{")
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        body, end = _braced(text, m.end() - 1)
        out.append(text[i:m.start()])
        out.append(fn(body))
        i = end


def pre_tex(text):
    """LaTeX to the prose a reader sees, before the fingerprint's own stripping: lists and captions are prose here."""
    body = re.split(r"\\begin\{document\}", text, maxsplit=1)
    text = body[1] if len(body) == 2 else text
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\n[ \t]*\n", BREAK, text)   # a sentence never runs across a blank line
    text = re.sub(r"\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\s*(?:\[[^\]]*\])?"
                  r"\s*\{(?:[^{}]|\{[^{}]*\})*\}", BREAK, text)
    # A float becomes its caption; the table body and graphics are not sentences.
    def float_to_caption(m):
        caps = []
        _replace_command(m.group(0), "caption", lambda b: caps.append(b) or "")
        return BREAK + BREAK.join(caps) + BREAK
    text = re.sub(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", float_to_caption, text, flags=re.S)
    text = re.sub(r"\\(?:begin|end)\{(?:itemize|enumerate|description)\}", BREAK, text)
    text = re.sub(r"\\item(?:\[[^\]]*\])?", BREAK, text)
    text = re.sub(r"\\S\s*~?\s*(?=\\(?:c|C|auto|name|page|eq|v)?ref)", " ", text)
    text = re.sub(r"\\(?:c|C|auto|name|page|eq|v)?ref\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:cite\w*|parencite|textcite|autocite|footcite)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{[^}]*\}", " ", text)
    text = re.sub(r"\\label\{[^}]*\}", " ", text)
    text = _replace_command(text, "footnote", lambda b: " (" + b + ") ")
    text = text.replace("\\textemdash", " --- ").replace("\\textendash", " -- ")
    text = re.sub(r"(?<!\\)\$[^$]+\$|\\\(.*?\\\)", " MATH ", text)
    return text


def pre_md(text):
    """Markdown headings, list items and blank lines end a unit of prose; without this a heading is read as the start
    of the sentence after it."""
    text = re.sub(r"(?m)^\s{0,3}#+.*$", BREAK, text)
    text = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", BREAK, text)
    return re.sub(r"\n[ \t]*\n", BREAK, text)


def read_text(fp, path):
    suffix = path.suffix.lower()
    if suffix == ".tex":
        raw = path.read_text(encoding="utf-8", errors="replace")
        return fp.strip_markup(pre_tex(raw), ".tex")
    if suffix == ".md":
        raw = path.read_text(encoding="utf-8", errors="replace")
        return fp.strip_markup(pre_md(raw), ".md")
    return fp.load(path)


def sentences(text):
    text = ABBREV.sub(lambda m: m.group(1), re.sub(r"\s+", " ", text or ""))
    return [s.strip() for unit in text.split(BREAK.strip()) for s in SPLIT.split(unit.strip())
            if len(s.split()) >= 3]


# ---------------------------------------------------------------- measuring

def _words(s):
    return re.findall(r"[A-Za-z][A-Za-z'-]*", s)


def clause_tokens(s):
    toks = [m.group(1).lower() for m in SUB.finditer(s)]
    for m in TEMPORAL_PREP.finditer(s):
        w = m.group(0).split()[0].lower()
        if w in toks:
            toks.remove(w)
    toks += ["as"] * len(AS_CLAUSE.findall(s)) + ["so that"] * len(SO_THAT.findall(s))
    return toks


def adverb_tokens(s):
    out = []
    words = _words(s)
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in OTHER_ADVERBS:
            out.append(lw)
        elif LY.fullmatch(w) and lw not in NOT_ADVERB and not (w[0].isupper() and i > 0):
            out.append(lw)
    return out


def modifier_tokens(s):
    out = []
    for m in PARTICIPLE_AFTER_NOUN.finditer(s):
        if m.group(1).lower() not in BE_HAVE:
            out.append(m.group(2).lower())
    out += [m.group(1).lower() for m in PARTICIPLE_AFTER_COMMA.finditer(s)]
    out += [m.group(1).lower() for m in PRENOMINAL.finditer(s)]
    low = s[0].lower() + s[1:] if s else s
    for w in ADJ_SUFFIX.findall(low):
        if w not in NOUN_STOP:
            out.append(w)
    out += [w.lower() for w in _words(s) if w.lower() in COMMON_ADJ]
    out += [m.group(1) for m in HYPHEN_PRENOMINAL.finditer(low)]
    return out


def worded_parentheses(s):
    """Parentheses holding a lowercase word: an aside ("(roughly)", "(both historians)"), not a number, a symbol or an
    abbreviation being defined ("(CC)")."""
    return sum(1 for inner in PAREN_WORDED.findall(s) if re.search(r"\b[a-z]{3,}\b", inner))


def features(s):
    return {
        "words": len(s.split()),
        "clauses": len(clause_tokens(s)),
        "commas": s.count(","),
        "colons": len(re.findall(r":(?!\d)", s)),
        "semicolons": s.count(";"),
        "dashes": len(DASH.findall(s)),
        "parentheses": s.count("("),
        "adverbs": len(adverb_tokens(s)),
        "modifiers": len(modifier_tokens(s)),
        "prepositions": len(PREP.findall(s)),
        "opener": 1 if OPENER.match(s) else 0,
    }


def summed(sents):
    total = {k: 0 for k in FEATURES}
    for s in sents:
        for k, v in features(s).items():
            total[k] += v
    total["opener"] = min(total["opener"], 1)
    return total


def gained(old_sents, new_sents, fn):
    """Occurrences the new text has beyond the old, as a sorted list (a multiset difference, not a net count)."""
    extra = Counter(t for s in new_sents for t in fn(s)) - Counter(t for s in old_sents for t in fn(s))
    return sorted(extra.elements())


# ---------------------------------------------------------------- reading files and pairs

def read_prose(fp, path):
    """{file: [sentences]} for a file, or for every prose file under a directory. Directories whose names start with
    a dot are skipped: the loop puts the previous version beside the draft in one."""
    path = Path(path)
    files = [path] if path.is_file() else sorted(
        p for p in path.rglob("*") if p.is_file() and not any(part.startswith(".") for part in p.relative_to(path).parts))
    out = {}
    for p in files:
        if p.suffix.lower() not in fp.TEXT_SUFFIXES:
            continue
        t = read_text(fp, p)
        if t and t.strip():
            out[p.name if path.is_file() else str(p.relative_to(path))] = sentences(t)
    return out


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def content(s):
    return {w.lower() for w in _words(s) if len(w) >= 3 and w.lower() not in STOPWORDS | SUB_WORDS}


def share(part, whole):
    a, b = content(part), content(whole)
    return (len(a & b) / len(a)) if a else 0.0, len(a & b)


def pair_changes(target, base):
    """[(file, [old sentences], [new sentences])] for every target sentence that does not occur in the base, grouped:
    a revision is one old and one new, a split one old and several new, a merge several old and one new, an addition
    no old. Second value: the removed base sentences matched to nothing, as (file, sentence)."""
    base_all = {norm(s) for ss in base.values() for s in ss}
    target_all = {norm(s) for ss in target.values() for s in ss}
    removed = {f: [s for s in ss if norm(s) not in target_all] for f, ss in base.items()}
    pool = [(f, s) for f, ss in removed.items() for s in ss]
    used = set()
    matched, unmatched = [], []
    for f, ss in target.items():
        for s in ss:
            if norm(s) in base_all:
                continue
            best, score = None, 0.0
            words = s.split()
            for pf, ps in sorted(pool, key=lambda x: x[0] != f):   # prefer the same file, then anywhere
                if (pf, ps) in used:
                    continue
                r = difflib.SequenceMatcher(None, words, ps.split(), autojunk=False).ratio()
                if r > score:
                    best, score = (pf, ps), r
            if best and score >= MATCH_MIN:
                used.add(best)
                matched.append([f, [best], [s]])
            else:
                unmatched.append((f, s))
    groups = {id(g): g for g in matched}
    by_old = {g[1][0]: g for g in matched}
    rest = []
    for f, s in unmatched:
        # a piece of a split: most of its content words come from one old sentence (matched or not)
        best, best_share = None, 0.0
        for old in pool:
            sh, n = share(s, old[1])
            if n >= 3 and sh >= PIECE_MIN and sh > best_share:
                best, best_share = old, sh
        if best is not None:
            g = by_old.get(best)
            if g is None:
                used.add(best)
                g = [f, [best], []]
                by_old[best] = g
                groups[id(g)] = g
            g[2].append(s)
        else:
            rest.append((f, s))
    def holds(new, old):
        # most of the old sentence's content words are in the new one; a short old sentence needs all of them
        sh, n = share(old, new)
        return sh >= PIECE_MIN and n >= min(3, len(content(old))) and n >= 1

    for f, s in rest:
        olds = [old for old in pool if old not in used and holds(s, old[1])]
        if olds:
            used.update(olds)
            g = [f, olds, [s]]
        else:
            g = [f, [], [s]]
        groups[id(g)] = g
    out = []
    for g in groups.values():
        f, olds, news = g
        out.append((f, [o[1] for o in olds], news))
    # a merged sentence matched by similarity to one old sentence may hold others that nothing else claimed
    for g in out:
        if len(g[1]) == 1 and len(g[2]) == 1:
            extra = [old for old in pool if old not in used and holds(g[2][0], old[1])]
            if extra:
                used.update(extra)
                g[1].extend(o[1] for o in extra)
    return out, [old for old in pool if old not in used]


def carried(sentence, carriers):
    """What a removed sentence carried: the caller's patterns it matches, then a number, then a qualifier."""
    out = [f"pattern {rx.pattern}" for rx in carriers if rx.search(sentence)]
    if REMOVED_NUMBER.search(sentence):
        out.append("number")
    q = REMOVED_QUALIFIER.search(sentence)
    if q:
        out.append(f"qualifier '{q.group(0)}'")
    return out


def read_carriers(path):
    if not Path(path).is_file():
        die(f"no carriers file at {path}")
    out = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(re.compile(line, re.I))
        except re.error as e:
            die(f"{path}:{n}: not a regular expression ({e}): {line}")
    return out


def prose(cell):
    """A proposal is usually written in the draft's markup; read it the way the draft is read."""
    cell = (cell or "").strip()
    if "\\" in cell or "~" in cell or "$" in cell or "%" in cell:
        cell = FP.strip_markup(pre_tex(cell), ".tex")
    return re.sub(r"\s+", " ", cell).strip()


VERDICTS = {"accepted": "accepted", "accept": "accepted", "kept": "accepted", "接受": "accepted", "留": "accepted",
            "保留": "accepted", "rejected": "rejected", "reject": "rejected", "revised": "rejected",
            "退回": "rejected", "拒": "rejected", "不要": "rejected", "改掉": "rejected", "作者改": "rejected"}


def read_pairs(path):
    """[(id, old sentences, new sentences, verdict, reason)]. verdict is accepted, rejected or None (not judged)."""
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader, None)
        if not header or not {"id", "old", "new"} <= {h.strip() for h in header}:
            die(f"{path}: the header must name the columns id, old, new (tab-separated)")
        col = {h.strip(): i for i, h in enumerate(header)}
        for alias, name in (("作者裁定", "verdict"), ("原因", "reason")):
            if alias in col and name not in col:
                col[name] = col[alias]
        for n, r in enumerate(reader, start=2):
            if not any(c.strip() for c in r):
                continue
            if len(r) > len(header):
                die(f"{path}:{n}: {len(r)} cells where the header has {len(header)} (a tab inside a cell?)")
            get = lambda k: r[col[k]] if k in col and col[k] < len(r) else ""  # noqa: E731
            raw = get("verdict").strip().lower()
            if raw and raw not in VERDICTS:
                die(f"{path}:{n}: verdict {get('verdict')!r} is not one of accepted, rejected, revised (or empty)")
            new = prose(get("new"))
            if new:
                old = prose(get("old"))
                rows.append((get("id"), sentences(old) if old else [], sentences(new) or [new],
                             VERDICTS.get(raw), get("reason").strip() or None))
    return rows


def _venue_key(baseline):
    """What the venue's distribution depends on: the corpus files (name, size, modification time) and the code that
    measures them (this script and the fingerprint audit it reads prose with)."""
    import hashlib
    h = hashlib.sha256()
    for f in (Path(__file__).resolve(), HERE / "audit-prose-fingerprint.py"):
        h.update(f.read_bytes())
    for f in sorted(p for p in Path(baseline).rglob("*") if p.is_file()):
        st = f.stat()
        h.update(f"{f.relative_to(baseline)}\0{st.st_size}\0{st.st_mtime_ns}\0".encode("utf-8"))
    return h.hexdigest()


def venue_distribution(fp, baseline, cache=None):
    """The venue's sentences, measured. Reading a corpus of PDFs takes seconds; with --venue-cache the columns are kept
    and reused while neither the corpus nor this code has changed."""
    key = _venue_key(baseline) if cache else None
    if cache:
        try:
            got = json.loads(Path(cache).read_text(encoding="utf-8"))
            if got.get("key") == key:
                return {"documents": got["documents"], "sentences": got["sentences"], "columns": got["columns"],
                        "cached": True}
        except (OSError, ValueError, KeyError):
            pass
    docs = fp.collect(Path(baseline))
    kept, sents = 0, []
    for _, text, _ in docs:
        if hasattr(fp, "word_share") and fp.word_share(text) < getattr(fp, "MIN_WORD_SHARE", 0.3):
            continue
        ss = [s for s in sentences(text) if 5 <= len(s.split()) <= 120]
        if ss:
            kept += 1
            sents.extend(ss)
    if kept < MIN_VENUE_DOCUMENTS or len(sents) < MIN_VENUE_SENTENCES:
        die(f"the baseline {baseline} gave {len(sents)} sentences from {kept} documents; percentiles need at least "
            f"{MIN_VENUE_SENTENCES} sentences from {MIN_VENUE_DOCUMENTS} documents")
    cols = {k: sorted(features(s)[k] for s in sents) for k in FEATURES}
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(json.dumps({"key": key, "documents": kept, "sentences": len(sents), "columns": cols}),
                               encoding="utf-8")
    return {"documents": kept, "sentences": len(sents), "columns": cols}


def percentile(col, x):
    below = sum(1 for v in col if v < x)
    equal = sum(1 for v in col if v == x)
    return round(100 * (below + equal / 2) / len(col))


def at(col, pct):
    return col[int(pct / 100 * (len(col) - 1))]


DENSITY = ("clauses", "commas", "prepositions", "adverbs", "modifiers")
# Ceilings for an added sentence when no venue corpus is given: the 75th percentiles of one journal's published papers
# as this script measures them. A venue corpus replaces them, and the report says which was used. Why the 75th: on the
# sentences added in one real round, the 90th flagged none, the 50th flagged about half (most for a single "also" or
# "often"), and the 75th flagged only the densest. That is the round the value was chosen on.
DEFAULT_CEILING = {"words": 31, "clauses": 1, "commas": 2, "prepositions": 3, "adverbs": 1, "modifiers": 3}


# ---------------------------------------------------------------- judging

def judge(olds, news, venue):
    """One group: the old sentences (none for an addition) and the new ones."""
    kind = ("added" if not olds else "split" if len(news) > 1 and len(olds) == 1
            else "merged" if len(olds) > 1 else "revised")
    fn = summed(news)
    fo = summed(olds) if olds else None
    flags, added = [], {}
    if fo:
        if fn["words"] - fo["words"] >= LONGER_WORDS:
            flags.append("longer")
        punct = ("commas", "colons", "semicolons", "dashes")
        # A comma that replaces a semicolon or a colon is not added punctuation.
        if fn["commas"] > fo["commas"] and sum(fn[k] for k in punct) > sum(fo[k] for k in punct):
            flags.append("comma")
        for k, name in (("colons", "colon"), ("semicolons", "semicolon"), ("dashes", "dash"),
                        ("parentheses", "parenthesis")):
            if fn[k] > fo[k]:
                flags.append(name)
        # Clauses are counted as occurrences gained: trading "because" for "which" turns a reason into a relative
        # clause. Adverbs and modifiers are counted net: a correction that swaps one term for another adds none.
        g = gained(olds, news, clause_tokens)
        if g:
            flags.append("clause")
            added["clauses"] = g
        for k, name, fnc in (("adverbs", "adverb", adverb_tokens), ("modifiers", "modifier", modifier_tokens)):
            g = gained(olds, news, fnc)
            if fn[k] > fo[k] and g:
                flags.append(name)
                added[k] = g
        if fn["prepositions"] - fo["prepositions"] >= MORE_PREPOSITIONS:
            flags.append("prepositions")
        if fn["opener"] and not fo["opener"]:
            flags.append("opener")
        if kind == "merged":
            flags.append("merged")
    else:
        for k, name in (("colons", "colon"), ("semicolons", "semicolon"), ("dashes", "dash")):
            if fn[k]:
                flags.append(name)
        if any(worded_parentheses(s) for s in news):
            flags.append("parenthesis")
        added = {k: [t for s in news for t in f(s)] for k, f in
                 (("clauses", clause_tokens), ("adverbs", adverb_tokens), ("modifiers", modifier_tokens))}
        added = {k: v for k, v in added.items() if v}
    pct, dense_hits = {}, set()
    pct_used = ADDITION_PCT if fo is None else VENUE_PCT
    ceiling = ({k: at(venue["columns"][k], pct_used) for k in ("words",) + DENSITY} if venue else DEFAULT_CEILING)
    # Without a venue, only additions are held to the default ceilings: a revision is already judged against the
    # sentence it replaced.
    if venue or fo is None:
        for s in news:
            f1 = features(s)
            if venue:
                pct = {k: percentile(venue["columns"][k], f1[k]) for k in ("words",) + DENSITY}
            longest_old = max((features(o)["words"] for o in olds), default=0)
            grew = fo is None or f1["words"] > (fo["words"] if kind != "merged" else longest_old)
            if f1["words"] > ceiling["words"] and grew:
                flags.append("long_for_venue")
            for k in DENSITY:
                if f1[k] > ceiling[k] and (fo is None or fn[k] > fo[k]):
                    dense_hits.add(k)
        if dense_hits:
            flags.append("dense_for_venue")
    return {"old": " ".join(olds) or None, "new": " ".join(news), "kind": kind, "features_old": fo,
            "features_new": fn, "added": added, "dense": sorted(dense_hits), "venue_percentile": pct,
            "flags": sorted(set(flags), key=flags.index), "pieces": len(news), "olds": len(olds)}


def verdict_table(results):
    """The flags set against the author's verdicts, and which version of this script (its thresholds) set them."""
    import hashlib
    t = {"judged": 0, "flagged_rejected": 0, "flagged_accepted": 0, "unflagged_rejected": 0, "unflagged_accepted": 0,
         "script": hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()}
    for r in results:
        v = r.get("verdict")
        if v:
            t["judged"] += 1
            t[("flagged_" if r["flags"] else "unflagged_") + v] += 1
    return t


def main():
    ap = argparse.ArgumentParser(description="Check rewritten sentences one by one.")
    ap.add_argument("--target")
    ap.add_argument("--base")
    ap.add_argument("--pairs")
    ap.add_argument("--baseline")
    ap.add_argument("--venue-cache", help="keep the venue's measured sentences here and reuse them while unchanged")
    ap.add_argument("--carriers", help="patterns (one per line) that a removed sentence must not take with it unflagged")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    global FP
    fp = FP = fingerprint()
    removed = []
    carriers = read_carriers(a.carriers) if a.carriers else []
    verdicts = {}
    if a.pairs:
        if a.target or a.base:
            die("give --pairs, or --target with --base, not both")
        if not Path(a.pairs).is_file():
            die(f"no pairs file at {a.pairs}")
        rows = read_pairs(a.pairs)
        if not rows:
            die(f"{a.pairs} holds no rewritten sentence")
        verdicts = {rid: (v, why) for rid, _, _, v, why in rows}
        changes = [(rid, old, new) for rid, old, new, _, _ in rows if norm(" ".join(old)) != norm(" ".join(new))]
        compared = {"pairs": len(rows)}
    else:
        if not (a.target and a.base):
            die("give --target and --base (the version before the edit), or --pairs")
        target = read_prose(fp, a.target) if Path(a.target).exists() else {}
        base = read_prose(fp, a.base) if Path(a.base).exists() else {}
        if not any(target.values()):
            die(f"no prose in the target {a.target}")
        if not any(base.values()):
            die(f"no prose in the base {a.base}: nothing to compare the draft with")
        changes, removed = pair_changes(target, base)
        compared = {"target_sentences": sum(map(len, target.values())), "base_sentences": sum(map(len, base.values()))}
    venue = venue_distribution(fp, a.baseline, a.venue_cache) if a.baseline else None
    results = []
    for where, olds, news in changes:
        r = judge(olds, news, venue)
        r["where"] = where
        if where in verdicts:
            r["verdict"], r["reason"] = verdicts[where]
        results.append(r)
    removed_flagged = 0
    for where, old in removed:
        what = carried(old, carriers)
        if not what:
            continue
        removed_flagged += 1
        results.append({"old": old, "new": "", "kind": "removed", "where": where, "features_old": features(old),
                        "features_new": None, "added": {}, "dense": [], "venue_percentile": {}, "carried": what,
                        "flags": ["removed_carrier"], "pieces": 0, "olds": 1})
        if where in verdicts:
            results[-1]["verdict"], results[-1]["reason"] = verdicts[where]
    flagged = [r for r in results if r["flags"]]
    kinds = Counter(r["kind"] for r in results)
    compared.update({"changed": len(results) - removed_flagged, "revised": kinds["revised"], "split": kinds["split"],
                     "merged": kinds["merged"], "added": kinds["added"], "removed": len(removed),
                     "removed_flagged": removed_flagged})
    unjudged = kinds["added"] if venue is None else 0   # judged against DEFAULT_CEILING, not a venue
    out = {"schema_version": 2, "compared": compared, "changed": len(results) - removed_flagged, "flagged": len(flagged),
           "added_without_venue": unjudged,
           "venue": ({"documents": venue["documents"], "sentences": venue["sentences"],
                      "p90": {k: at(venue["columns"][k], VENUE_PCT) for k in ("words",) + DENSITY},
                      "p75": {k: at(venue["columns"][k], ADDITION_PCT) for k in ("words",) + DENSITY}}
                     if venue else None),
           "limits": LIMITS,
           "verdicts": verdict_table(results) if verdicts else None,
           "sentences": results,
           "issues": [{"where": r["where"], "flags": r["flags"], "added": r["added"], "new": r["new"],
                       **({"old": r["old"], "carried": r["carried"]} if r["kind"] == "removed" else {})}
                      for r in flagged]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"changed sentences: {len(results) - removed_flagged} ({kinds['revised']} revised, {kinds['split']} split, "
              f"{kinds['merged']} merged, {kinds['added']} added); removed without a successor: {len(removed)}, "
              f"{removed_flagged} of them carrying something; flagged: {len(flagged)}")
        if venue:
            print(f"venue: {venue['sentences']} sentences from {venue['documents']} documents; p90 "
                  + ", ".join(f"{k} {v}" for k, v in out["venue"]["p90"].items())
                  + "; added sentences held to p75 " + ", ".join(f"{k} {v}" for k, v in out["venue"]["p75"].items()))
        elif unjudged:
            print(f"{unjudged} added sentence(s) held to default ceilings, not to a venue: give --baseline "
                  + "(" + ", ".join(f"{k} {v}" for k, v in DEFAULT_CEILING.items()) + ")")
        for r in flagged:
            if r["kind"] == "removed":
                print(f"\n[{r['where']}] removed: {', '.join(r['carried'])}")
                print(f"  was: {r['old']}")
                continue
            fo, fn = r["features_old"], r["features_new"]
            size = f"{fo['words']}->{fn['words']} words" if fo else f"{fn['words']} words, added"
            extra = "; ".join(f"{k}: {', '.join(v)}" for k, v in r["added"].items())
            print(f"\n[{r['where']}] {r['kind']}: {', '.join(r['flags'])}  ({size})" + (f"  [{extra}]" if extra else ""))
            if r["old"]:
                print(f"  was: {r['old']}")
            print(f"  now: {r['new']}")
        if not results and not removed:
            print("no sentence changed")
        vt = out["verdicts"]
        if vt:
            print(f"\nauthor verdicts on {vt['judged']} of {len(results)} changed sentences (script {vt['script'][:12]}): "
                  f"flagged and rejected {vt['flagged_rejected']}, flagged but kept {vt['flagged_accepted']}, "
                  f"not flagged but rejected {vt['unflagged_rejected']}, not flagged and kept {vt['unflagged_accepted']}")
        print(f"\n{LIMITS}")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
