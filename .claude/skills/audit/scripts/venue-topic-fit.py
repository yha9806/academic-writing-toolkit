#!/usr/bin/env python3
"""Where a manuscript's topic and contribution type sit among the papers a journal publishes.

    python3 venue-topic-fit.py fetch --issn <ISSN> [--from 2024-01-01] --out <corpus.json> [--dry-run]
    python3 venue-topic-fit.py neighbors --corpus <corpus.json> --title <text> [--abstract <file>] [--top 15] [--json]
    python3 venue-topic-fit.py sample --corpus <corpus.json> --n 100 --seed <int> --out <sheet.tsv>
    python3 venue-topic-fit.py tally --sheet <sheet.tsv> [--json]

build-venue-baseline.py and the prose audits answer whether a manuscript reads like the venue: sentence length,
punctuation, structure. They were built from the authors' preprints of accepted papers, which skew towards the
subfields whose authors post preprints, so they cannot say whether the manuscript is about what the venue publishes,
or whether it makes the kind of contribution the venue usually takes. This measures those two things on every
article the venue published in a window, from the registrar's records rather than from preprints.

fetch    Every article with the ISSN from OpenAlex: id, DOI, title, year and, where OpenAlex has it, the abstract.
         Publishers withhold many abstracts; the corpus says how many it has. The request carries the tool's name
         and nothing else: no e-mail address, no mailto parameter. --dry-run prints the first request and stops.
neighbors  TF-IDF cosine between the manuscript and each article, on titles (every article) and on title plus
         abstract (the articles that have one). It reports the nearest articles and where the manuscript's own
         nearest-neighbour similarity falls among the articles' nearest-neighbour similarities: a low percentile
         means its wording sits at the edge of what the venue publishes. Word overlap, not a judgement of fit.
sample   A seeded random sample of titles with an empty code column, for a person (or a model, recorded as such)
         to code by contribution type: M method, model or system; E evaluation or analysis of existing systems or
         benchmarks; D dataset or benchmark as the main contribution; S study of people, organisations or science
         that does not evaluate a system; R review. Coding from titles is quick and coarse; say so when citing it.
tally    Counts per code with Wilson 95% intervals. An uncoded row or an unknown code is an error, not a skip.

What this cannot tell you: whether the manuscript would be accepted. Every article in the corpus was accepted; the
rejected ones are not in it, so no share computed here is an acceptance rate.

Exit: 0 done; 2 nothing to work on (an empty corpus, a sheet with no rows, an uncoded or unknown code, an argument it
does not recognise). fetch exits 2 when the venue returns no article.
"""
import argparse
import csv
import datetime as dt
import json
import math
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

API = "https://api.openalex.org/works"
USER_AGENT = "academic-writing-toolkit venue-topic-fit"
CODES = {"M": "method, model or system", "E": "evaluation or analysis of existing systems",
         "D": "dataset or benchmark", "S": "study of people, organisations or science", "R": "review"}
STOP = set("""a an the of in on for to with by from and or but as at is are was were be been being this that these
those it its their our we they which who whom whose what when where how why than then there here into onto over
under via between among across through about not no can could may might will would should must do does did has have
had using based use new towards toward approach method study analysis""".split())


def die(msg):
    sys.stderr.write(f"venue-topic-fit: {msg}\n")
    sys.exit(2)


# ---------------------------------------------------------------- fetch

def abstract_from_index(inv):
    """OpenAlex stores an abstract as {word: [positions]}; rebuild the text in order."""
    words = sorted((p, w) for w, ps in (inv or {}).items() for p in ps)
    return " ".join(w for _, w in words)


def fetch(issn, since, out, dry_run=False):
    params = {"filter": f"primary_location.source.issn:{issn},from_publication_date:{since},type:article",
              "select": "id,doi,title,publication_year,abstract_inverted_index", "per-page": "200", "cursor": "*"}
    works = []
    while True:
        url = API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if dry_run:
            print(json.dumps({"url": url, "headers": dict(req.header_items())}))
            return 0
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        for w in d.get("results") or []:
            works.append({"id": w.get("id"), "doi": w.get("doi"), "title": w.get("title") or "",
                          "year": w.get("publication_year"),
                          "abstract": abstract_from_index(w.get("abstract_inverted_index"))})
        nxt = (d.get("meta") or {}).get("next_cursor")
        if not nxt or not d.get("results"):
            break
        params["cursor"] = nxt
        time.sleep(1)
    if not works:
        die(f"OpenAlex returned no article for ISSN {issn} since {since}")
    rec = {"retrieved": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "api": API,
           "filter": params["filter"], "n": len(works), "with_abstract": sum(1 for w in works if w["abstract"]),
           "works": works}
    Path(out).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    print(f"{len(works)} articles, {rec['with_abstract']} with an abstract -> {out}")
    return 0


def load_corpus(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"cannot read the corpus {path}: {e}")
    works = [w for w in (d.get("works") or []) if (w.get("title") or "").strip()]
    if not works:
        die(f"the corpus {path} holds no article with a title")
    return d, works


# ---------------------------------------------------------------- TF-IDF

def tokens(text):
    return [w for w in re.findall(r"[a-z][a-z0-9-]+", (text or "").lower()) if w not in STOP and len(w) > 2]


def vectors(docs):
    """Sublinear TF-IDF with smoothed IDF, L2-normalised, as {term: weight} per document."""
    tfs = [Counter(tokens(d)) for d in docs]
    df = Counter(t for tf in tfs for t in tf)
    n = len(docs)
    idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
    out = []
    for tf in tfs:
        v = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        out.append({t: x / norm for t, x in v.items()})
    return out


def similarities(vecs, q):
    """Cosine of q with every vector, and each vector's highest cosine with any other (through an inverted index)."""
    index = defaultdict(list)
    for i, v in enumerate(vecs):
        for t, x in v.items():
            index[t].append((i, x))
    to_q = [0.0] * len(vecs)
    for t, x in q.items():
        for i, y in index.get(t, ()):
            to_q[i] += x * y
    best = []
    for i, v in enumerate(vecs):
        acc = defaultdict(float)
        for t, x in v.items():
            for j, y in index[t]:
                if j != i:
                    acc[j] += x * y
        best.append(max(acc.values(), default=0.0))
    return to_q, best


def neighbors(corpus, title, abstract, top):
    _, works = load_corpus(corpus)
    out = {"title": title}
    sets = [("titles", works, lambda w: w["title"], title)]
    with_abs = [w for w in works if (w.get("abstract") or "").strip()]
    if abstract is not None and with_abs:
        sets.append(("title_abstract", with_abs, lambda w: w["title"] + " " + w["abstract"], title + " " + abstract))
    for name, ws, text, query in sets:
        vecs = vectors([text(w) for w in ws] + [query])
        q = vecs.pop()
        to_q, best = similarities(vecs, q)
        ours = max(to_q, default=0.0)
        below = sum(1 for b in best if b < ours)
        order = sorted(range(len(ws)), key=lambda i: -to_q[i])[:top]
        out[name] = {"n": len(ws), "ours_nearest": round(ours, 3),
                     "articles_nearest_median": round(sorted(best)[len(best) // 2], 3),
                     "ours_percentile": round(100 * below / len(best), 1),
                     "top": [{"similarity": round(to_q[i], 3), "year": ws[i].get("year"), "doi": ws[i].get("doi"),
                              "title": ws[i]["title"]} for i in order]}
    return out


# ---------------------------------------------------------------- sample and tally

def sample(corpus, n, seed, out):
    _, works = load_corpus(corpus)
    if n <= 0:
        die("--n must be positive")
    rng = random.Random(seed)
    picks = rng.sample(range(len(works)), min(n, len(works)))
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writerow(["i", "year", "doi", "title", "code"])
        for k, i in enumerate(picks, 1):
            w.writerow([k, works[i].get("year"), works[i].get("doi") or "", re.sub(r"\s+", " ", works[i]["title"]), ""])
    print(f"{len(picks)} titles (seed {seed}) -> {out}; code each as one of " + ", ".join(CODES))
    return 0


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - r) / d, 3), round((c + r) / d, 3))


def tally(sheet):
    try:
        with open(sheet, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    except OSError as e:
        die(f"cannot read the sheet {sheet}: {e}")
    if not rows:
        die(f"{sheet} has no rows")
    codes = [(r.get("code") or "").strip().rstrip("?") for r in rows]
    bad = [(r.get("i"), c) for r, c in zip(rows, codes) if c not in CODES]
    if bad:
        die(f"{len(bad)} row(s) uncoded or with an unknown code (first: row {bad[0][0]} {bad[0][1]!r}); "
            f"codes are {', '.join(CODES)}")
    n = len(codes)
    c = Counter(codes)
    doubtful = sum(1 for r in rows if (r.get("code") or "").strip().endswith("?"))
    return {"n": n, "doubtful": doubtful,
            "codes": {k: {"meaning": CODES[k], "count": c[k], "share": round(c[k] / n, 3), "wilson95": wilson(c[k], n)}
                      for k in CODES}}


def main():
    ap = argparse.ArgumentParser(description="Topic and contribution type against a venue's published articles.")
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch")
    f.add_argument("--issn", required=True)
    f.add_argument("--from", dest="since", default="2024-01-01")
    f.add_argument("--out", required=True)
    f.add_argument("--dry-run", action="store_true")
    nb = sub.add_parser("neighbors")
    nb.add_argument("--corpus", required=True)
    nb.add_argument("--title", required=True)
    nb.add_argument("--abstract")
    nb.add_argument("--top", type=int, default=15)
    nb.add_argument("--json", action="store_true")
    sp = sub.add_parser("sample")
    sp.add_argument("--corpus", required=True)
    sp.add_argument("--n", type=int, default=100)
    sp.add_argument("--seed", type=int, required=True)
    sp.add_argument("--out", required=True)
    tl = sub.add_parser("tally")
    tl.add_argument("--sheet", required=True)
    tl.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "fetch":
        if not re.fullmatch(r"\d{4}-\d{3}[\dXx]", a.issn):
            die(f"not an ISSN: {a.issn}")
        return fetch(a.issn, a.since, a.out, a.dry_run)
    if a.cmd == "neighbors":
        abstract = None
        if a.abstract:
            try:
                abstract = Path(a.abstract).read_text(encoding="utf-8")
            except OSError as e:
                die(f"cannot read the abstract {a.abstract}: {e}")
        if not tokens(a.title):
            die("the title has no content word to compare")
        out = neighbors(a.corpus, a.title, abstract, a.top)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=1))
        else:
            for name in ("titles", "title_abstract"):
                if name not in out:
                    continue
                o = out[name]
                print(f"{name}: {o['n']} articles; nearest {o['ours_nearest']} "
                      f"(articles' own nearest, median {o['articles_nearest_median']}; "
                      f"the manuscript is above {o['ours_percentile']}% of them)")
                for r in o["top"]:
                    print(f"  {r['similarity']:.3f} {r['year']} {r['title'][:120]}")
            print("Word overlap only; every article here was accepted, so nothing here is an acceptance rate.")
        return 0
    if a.cmd == "sample":
        return sample(a.corpus, a.n, a.seed, a.out)
    if a.cmd == "tally":
        out = tally(a.sheet)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=1))
        else:
            print(f"{out['n']} coded titles ({out['doubtful']} marked doubtful with '?')")
            for k, v in out["codes"].items():
                print(f"  {k} {v['meaning']}: {v['count']} ({v['share']:.0%}, 95% {v['wilson95'][0]:.0%}-{v['wilson95'][1]:.0%})")
        return 0
    die("give a command: fetch, neighbors, sample or tally")


if __name__ == "__main__":
    sys.exit(main())
