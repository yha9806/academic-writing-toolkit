#!/usr/bin/env python3
"""Chinese prose, read for the sentence audits: the one place the Chinese reading depends on.

audit-sentence-changes.py and audit-prose-structure.py load this module beside them, the way they load the
fingerprint audit, so the two read Chinese the same way. It is a library: it makes no pass/fail claim of its own.
Every word list and every converted threshold below can be revised here, and both audits follow.

Which text is Chinese. A text is read as Chinese when Han characters make up at least ZH_SHARE (half) of its units,
or at least ZH_SHARE_WITH_PUNCT (a quarter) when it also uses Chinese punctuation (，。；：！？、（）「」). A unit is a Han
character, a kana or hangul character, or a run of Latin letters and digits (a word or a number, counted once). A
text with kana or hangul in a twentieth of its units is Japanese or Korean and is not read as Chinese. Kana and hangul are counted so that Japanese or Korean text is not read as Chinese; neither is handled here.
English text has no Han character and never reaches this module: the audits' English reading is unchanged.

Sentences end at 。！？ together with any closing quotation mark or bracket after them (”’」』）］】). A terminator inside
a bracket or a quotation that goes on after it does not end the sentence ("（见表3。下同）" stays inside its sentence);
when a paragraph's brackets do not balance, every terminator ends a sentence instead, so one stray mark cannot fuse
the rest of a paragraph. ； does not end a sentence, as ; does not in the English reading: both count it as a
semicolon inside the sentence. A piece of a Chinese paragraph that is not itself Chinese (a quoted English sentence)
is split by the caller's English rule. Numeric citation markers (^［9, 10］^, ［12］, [3-5]) are removed first: their
commas and brackets are not the sentence's.

Length is in units: a Han character, or a Latin word or number counted as one ("PRISMA 2020" is two). The English
audits' thresholds are in words; a threshold of n words becomes zh_units(n) = ceil(n * ZH_UNITS_PER_WORD) units.
ZH_UNITS_PER_WORD = 1.6 is an assumed ratio of Han characters to English words for the same content. It was not
measured, and no Chinese venue corpus exists yet, so every converted threshold is uncalibrated for Chinese, and the
reports say so. Counts that are not lengths (two prepositional phrases, a ceiling of one clause or two commas) are
kept as the English audits have them; they are uncalibrated for Chinese too.

Punctuation, in the categories the English reading uses: commas are ， 、 and , (a , that groups digits, as in 4,120,
is not one); colons are ： and : (not 10:30); semicolons ； and ;; dashes are —— and the spaced forms the English
reading counts (a single — between two terms, as in 感知—记录, joins them and is not a dash); parentheses （ and (.

Clauses, prepositional phrases, adverbs, modifiers and linking openers are matched from the closed lists below: they
are word lists, not a word segmenter and not a parser. A marker the list does not name is not counted, and a string
the list names is counted wherever it occurs, whatever its role. Exclusions written beside an entry keep the commonest
false matches out (若干 is not 若, 存在 is not 在, 更新 is not 更).
"""
import math
import re

# --------------------------------------------------------------------------------------------- what is Chinese

# 〇 (U+3007) is the Han zero of 二〇二三.
HAN_RANGE = "\u3007\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
HAN = re.compile(f"[{HAN_RANGE}]")
# A unit: one Han character, one kana or hangul character, or one Latin word or number (4,120 and 3.5 are one).
UNIT = re.compile(f"[{HAN_RANGE}]|[\u3040-\u30ff\uac00-\ud7af]|[A-Za-z0-9]+(?:[.,'\u2019\\-][A-Za-z0-9]+)*")
ZH_SHARE = 0.5
# A sentence that uses Chinese punctuation is Chinese from a lower share: "CIDOC概念参考模型（CIDOC Conceptual Reference
# Model, CIDOC CRM）" is a Chinese sentence about an English name. Curly quotation marks are not counted as Chinese:
# English uses them too.
ZH_SHARE_WITH_PUNCT = 0.25
ZH_PUNCT = re.compile("[\uff0c\u3002\uff1b\uff1a\uff01\uff1f\u3001\uff08\uff09\u300c\u300d]")
# Kana or hangul in a twentieth of the units makes a text Japanese or Korean, whatever its Han share.
KANA_HANGUL = re.compile("[\u3040-\u30ff\uac00-\ud7af]")
KANA_HANGUL_MAX = 0.05
ZH_UNITS_PER_WORD = 1.6


def units(text):
    """The text's units, in order."""
    return UNIT.findall(text or "")


def han_share(text):
    us = units(text)
    return sum(1 for u in us if HAN.fullmatch(u)) / len(us) if us else 0.0


def is_chinese(text):
    if not text or not HAN.search(text):
        return False
    us = units(text)
    if sum(1 for u in us if KANA_HANGUL.fullmatch(u)) >= KANA_HANGUL_MAX * len(us):
        return False   # Japanese or Korean: Han characters, but not Chinese
    share = han_share(text)
    return share >= ZH_SHARE or (share >= ZH_SHARE_WITH_PUNCT and bool(ZH_PUNCT.search(text)))


def length(text):
    return len(units(text))


def zh_units(words):
    """A threshold in English words as one in units: ceil(words x ZH_UNITS_PER_WORD). Uncalibrated."""
    return math.ceil(words * ZH_UNITS_PER_WORD)


# --------------------------------------------------------------------------------------------- sentences

# Numeric citation markers, superscript or not, with half- or full-width brackets: ^［9, 10］^, ［12］, [3-5], ^[2]^.
CITATION = re.compile(r"\^?[［\[]\s*\d+(?:\s*[-–—~～,，、]\s*\d+)*\s*[］\]]\^?")
TERMINATORS = "。！？"
OPENERS = "（［【「『“‘(["
CLOSERS = "）］】」』”’)]"


def strip_citations(text):
    return CITATION.sub("", text or "")


def _cut(text, balanced):
    out, start, depth, i = [], 0, 0, 0
    while i < len(text):
        c = text[i]
        if c in OPENERS:
            depth += 1
        elif c in CLOSERS:
            depth = max(0, depth - 1)
        elif c in TERMINATORS:
            j = i + 1
            while j < len(text) and (text[j] in TERMINATORS or text[j] in CLOSERS):
                if text[j] in CLOSERS:
                    depth = max(0, depth - 1)
                j += 1
            if depth == 0 or not balanced:
                out.append(text[start:j])
                start = j
            i = j
            continue
        i += 1
    out.append(text[start:])
    return out


def _balanced(text):
    depth = 0
    for c in text:
        if c in OPENERS:
            depth += 1
        elif c in CLOSERS:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def sentences(paragraph, english_split=None):
    """A paragraph's sentences, citation markers removed. english_split (a compiled pattern) splits a piece that is
    not itself Chinese the way the caller splits English."""
    text = re.sub(r"\s+", " ", strip_citations(paragraph)).strip()
    out = []
    for piece in _cut(text, _balanced(text)):
        piece = piece.strip()
        if not piece:
            continue
        if english_split is not None and not is_chinese(piece):
            out += [s.strip() for s in english_split.split(piece) if s.strip()]
        else:
            out.append(piece)
    return out


# --------------------------------------------------------------------------------------------- punctuation

DIGIT_GROUP_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
DASH = re.compile(r"——|―|---|\s--\s|\s[–—]\s|\s-\s")
# Every mark that gives the reader a place to breathe, for the longest run without one.
PUNCT = re.compile(r"——|[，、。！？；：“”‘’「」『』（）《》〈〉【】［］…·,.;:!?()\[\]\"—–]")


def commas(s):
    return s.count("，") + s.count("、") + s.count(",") - len(DIGIT_GROUP_COMMA.findall(s))


def colons(s):
    return s.count("：") + len(re.findall(r":(?!\d)", s))


def semicolons(s):
    return s.count("；") + s.count(";")


def dashes(s):
    return len(DASH.findall(s))


def parentheses(s):
    return s.count("（") + s.count("(")


def worded_parentheses(s):
    """Parentheses holding three or more Han characters: an aside (（含已发表的系统）), not a pointer or a number
    (（表3）, （见表3）, （2015）). The English reading asks for a lowercase word for the same reason."""
    return sum(1 for inner in re.findall(r"[（(]([^（）()]*)[）)]", s) if len(HAN.findall(inner)) >= 3)


def runs(s):
    """Lengths in units of the stretches between punctuation marks."""
    return [n for n in (length(part) for part in PUNCT.split(s)) if n]


# --------------------------------------------------------------------------------------------- word lists

_STOP = "，。；：！？、“”「」（）"
# Subordinate-clause markers, the counterpart of the English reading's subordinators. Order matters only where one
# entry contains another: the longer is tried first.
CLAUSE_MARKERS = [
    ("之所以", r"之所以"), ("虽然", r"虽然"), ("尽管", r"尽管"), ("因为", r"因为"), ("由于", r"由于"),
    ("如果", r"如果"), ("假如", r"假如"), ("倘若", r"倘若"), ("即使", r"即使"), ("即便", r"即便"),
    ("只要", r"只要"), ("除非", r"除非"), ("以便", r"以便"), ("以免", r"以免"), ("既然", r"既然"),
    ("无论", r"无论"), ("不论", r"不论"), ("一旦", r"一旦"),
    ("若", r"(?<![倘假如])若(?!干)"),
    # 当……时 within one clause; 当前, 相当, 应当, 当地, 当然, 当时, 当作 and the like are not it.
    ("当……时", rf"(?<![相适应正充担])当(?![前代地然今下中时初场即年日作成做])[^{_STOP}]{{1,20}}?时"),
]
# A sentence that opens with one of these holds a condition, a concession or a cause before its claim.
OPENER_MARKERS = [m for m, _ in CLAUSE_MARKERS if m not in ("以便", "以免")]
# Heads of a prepositional phrase. 在 counts only as 在……中/上/下/里/内/方面/之间/以来/期间 within one clause.
PREP_HEADS = [
    ("在……", rf"(?<![存现正所实自潜旨])在(?!于)[^{_STOP}]{{1,15}}?(?:过程中|方面|之间|以来|期间|中|上|下|里|内)"),
    ("对于", r"对于"), ("关于", r"关于"), ("通过", r"通过"), ("基于", r"基于"), ("根据", r"根据"),
    ("随着", r"随着"), ("鉴于", r"鉴于"), ("针对", r"针对"), ("围绕", r"围绕"), ("按照", r"按照"),
    ("依据", r"依据"), ("借助", r"借助"),
]
# Degree and hedge adverbs, the counterpart of the English reading's adverbs.
ADVERBS = [
    ("往往", r"往往"), ("普遍", r"普遍"), ("显著", r"显著"), ("明显", r"明显"), ("非常", r"非常"), ("十分", r"十分"),
    ("极为", r"极为"), ("极其", r"极其"), ("特别", r"特别"), ("尤其", r"尤其"), ("相当", r"相当(?!于)"),
    ("较为", r"较为"), ("比较", r"比较"), ("较", r"较"), ("更加", r"更加"),
    ("更", r"(?<!变)更(?!新|改|换|正|替|迭|名)"), ("最", r"最(?!终|后|初)"), ("通常", r"通常"), ("一般", r"一般"),
    ("大多", r"大多"), ("大都", r"大都"), ("基本上", r"基本上"), ("几乎", r"几乎"), ("甚至", r"甚至"),
    ("仍然", r"仍然"), ("已经", r"已经"), ("始终", r"始终"), ("总是", r"总是"), ("常常", r"常常"),
    ("经常", r"经常"), ("或许", r"或许"), ("也许", r"也许"), ("可能", r"可能(?!性)"), ("大致", r"大致"),
    ("相对", r"相对(?!于)"), ("略微", r"略微"), ("稍微", r"稍微"), ("仅仅", r"仅仅"), ("仅", r"(?<!不)仅"),
]
# The attributive 的 stands in for a modifier, as the English reading's suffix rules stand in for a tagger. 目的, 的确,
# 有的, 别的 are not it; 是……的 cannot be told apart and is counted.
MODIFIER = r"(?<![目有别似])的(?![确话])"
# Linking adverbials: a link to the sentence before, taken out of both sides before a rewrite is judged, as the English
# reading does. Enumerators (首先, 其次, 最后) are not links.
LINKS = ["然而", "但是", "不过", "因此", "所以", "因而", "于是", "此外", "另外", "同时", "例如", "比如", "总之",
         "换言之", "也就是说", "具体而言", "具体来说", "相反", "与此同时", "事实上", "实际上", "总体而言",
         "总的来说", "综上所述", "综上", "但"]
_LINK_ALT = "|".join(sorted(LINKS, key=len, reverse=True))
LINK_OPENER = re.compile(rf"^[“「]?(?:{_LINK_ALT})[，,]?")
MID_LINK = re.compile(rf"[，,](?:{_LINK_ALT})[，,]")


def _alternation(entries):
    return re.compile("|".join(f"(?P<g{i}>{p})" for i, (_, p) in enumerate(entries)))


_CLAUSE = _alternation(CLAUSE_MARKERS)
_PREP = _alternation(PREP_HEADS)
_ADVERB = _alternation(ADVERBS)
_MODIFIER = re.compile(MODIFIER)
_OPENER = re.compile(r"^[“「『（(]?\s*(?:" + "|".join(
    p for m, p in CLAUSE_MARKERS if m in OPENER_MARKERS) + ")")


def _tokens(rx, entries, s):
    return [entries[int(next(k for k, v in m.groupdict().items() if v is not None)[1:])][0] for m in rx.finditer(s)]


def clause_tokens(s):
    return _tokens(_CLAUSE, CLAUSE_MARKERS, s)


def prep_tokens(s):
    return _tokens(_PREP, PREP_HEADS, s)


def adverb_tokens(s):
    return _tokens(_ADVERB, ADVERBS, s)


def modifier_tokens(s):
    return ["的"] * len(_MODIFIER.findall(s))


def opener(s):
    return 1 if _OPENER.match(s) else 0


def links(s):
    m = LINK_OPENER.match(s)
    found = [m.group(0).strip("“「，,")] if m else []
    return found + [x.group(0).strip("，,") for x in MID_LINK.finditer(s)]


def unlinked(s):
    m = LINK_OPENER.match(s)
    if m and m.end() < len(s):
        s = s[m.end():]
    return MID_LINK.sub("，", s)


def features(s):
    """The English reading's features, read the Chinese way; "words" is the length in units."""
    return {"words": length(s), "clauses": len(clause_tokens(s)), "commas": commas(s), "colons": colons(s),
            "semicolons": semicolons(s), "dashes": dashes(s), "parentheses": parentheses(s),
            "adverbs": len(adverb_tokens(s)), "modifiers": len(modifier_tokens(s)),
            "prepositions": len(prep_tokens(s)), "opener": opener(s)}


# --------------------------------------------------------------------------------------------- comparing sentences

def content(s):
    """What two sentences share when one is a piece of the other: Han character pairs within a run of Han, and Latin
    words of three letters or more."""
    out = set()
    for run in re.findall(f"[{HAN_RANGE}]+", s):
        out |= {run[i:i + 2] for i in range(len(run) - 1)}
    out |= {w.lower() for w in re.findall(r"[A-Za-z]{3,}", s)}
    return out


def key(s):
    """A sentence on its letters, digits and Han characters alone, for finding one written twice."""
    return re.sub(f"[^a-z0-9{HAN_RANGE}]", "", strip_citations(s).lower())


def wording(s):
    return [u.lower() for u in units(strip_citations(s))]


# --------------------------------------------------------------------------------------------- what the reports say

def ceiling_note(ceiling):
    return ", ".join(f"{k} {v}" for k, v in ceiling.items())


LIMITS_SENTENCES = (
    "Chinese input (Han characters half of the units, or a quarter with Chinese punctuation): "
    "length is in characters, a Latin word or number "
    "counting as one; commas are ， 、 and ,, colons ： and :, semicolons ； and ;, dashes —— (a single — joining two "
    "terms is not counted), parentheses （ and (; clauses, prepositional phrases, adverbs, modifiers (the attributive "
    "的) and linking openers are matched from the word lists in chinese-prose.py, not by a word segmenter or a parser. "
    "Word thresholds are converted to characters at 1.6 per word (3 words -> 5, 31 -> 50) and count ceilings are the "
    "English ones: all are uncalibrated for Chinese, as no Chinese venue corpus exists yet. Not measured for Chinese: "
    "clauses with no marker word, the length of a modifier before its noun beyond the count of 的, adverbial 地, "
    "nouns used as modifiers, a run of clauses joined by commas beyond the commas it adds, an antecedent a removal "
    "took (该, 此, 这些), shares of a total, multiples of chance; the writing loop reads committed versions only")

LIMITS_STRUCTURE = (
    "Chinese input (Han characters half of the units, or a quarter with Chinese punctuation): "
    "lengths are in characters, a Latin word or number "
    "counting as one, and rates are per 100 characters; sentences are kept from 7 to 192 characters and long means "
    "56 or more (the English 4, 120 and 35 words at 1.6 characters per word, uncalibrated); clauses are the "
    "subordinate-clause markers of chinese-prose.py (a word list, not a parser); commas are ， 、 and ,; dashes ——; "
    "an unpunctuated run ends at any punctuation mark. The baseline must be Chinese documents; English ones are "
    "skipped. Not measured: clauses with no marker word, modifiers before a noun, topic-comment structure")
