#!/usr/bin/env python3
"""Set two versions of a passage before the author without saying which is which, and prove the order afterwards.

    python3 blind-pair.py prepare --first <file> --second <file> --out <dir> --secret <file> [--labels before,after]
    python3 blind-pair.py choose --out <dir> --pick A|B [--note "<what the author said>"]
    python3 blind-pair.py reveal --out <dir> --secret <file>

The prose audits measure a draft against published papers; they do not say whether the author finds it better. On
2026-10-28 an author read two versions of one related-work paragraph blind and chose the one from before the style
round, the version those audits had placed further outside the venue's range. A style round is therefore accepted by
a read like this one, not by the numbers.

prepare puts the two files in a random order (secrets.choice) as A.txt and B.txt in --out, and writes the order with
a random salt to --secret. --out also gets commitment.json: the sha256 of the secret line and of A.txt and B.txt. The
commitment exists before anyone reads, so once the secret is shown anyone can check that the order was not decided
after the choice and that neither text was swapped. The secret must not be inside --out, which is what the author is
given; keep it out of the author's sight (a git-ignored directory, or outside the repository).

choose records the pick (and the author's words, if any) in choice.json; it refuses a second pick. reveal refuses
until a pick is recorded, checks the secret against the commitment and the texts against their hashes, and writes
reveal.json with the mapping. It does not stop anyone from opening the secret file early; the commitment only makes
a changed order detectable.

Exit: 0 done; 2 a refusal (missing or existing files, a secret inside --out, a second pick, a reveal before a pick,
a secret or a text that does not match the commitment).
"""
import argparse
import hashlib
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


def die(msg):
    sys.stderr.write(f"blind-pair: {msg}\n")
    sys.exit(2)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inside(path, folder):
    path, folder = path.resolve(), folder.resolve()
    return path == folder or folder in path.parents


def committed(out):
    path = out / "commitment.json"
    if not path.is_file():
        die(f"no commitment.json in {out}: run prepare first")
    c = json.loads(path.read_text(encoding="utf-8"))
    for name in ("A", "B"):
        text = out / f"{name}.txt"
        if not text.is_file() or sha(text.read_bytes()) != c[f"{name}_sha256"]:
            die(f"{text} is missing or is not the text that was committed")
    return c


def prepare(a):
    first, second, out, secret = Path(a.first), Path(a.second), Path(a.out), Path(a.secret)
    labels = [x.strip() for x in a.labels.split(",")]
    if len(labels) != 2 or not all(labels) or labels[0] == labels[1] or any(c in "".join(labels) for c in ";="):
        die("--labels takes two different names separated by a comma, without ; or =")
    for f in (first, second):
        if not f.is_file():
            die(f"no file at {f}")
    texts = {labels[0]: first.read_bytes(), labels[1]: second.read_bytes()}
    if texts[labels[0]] == texts[labels[1]]:
        die("the two files are identical")
    if inside(secret, out):
        die(f"the secret {secret} is inside {out}, which is what the author is given")
    if secret.exists():
        die(f"{secret} already exists")
    if any((out / n).exists() for n in ("A.txt", "B.txt", "commitment.json", "choice.json", "reveal.json")):
        die(f"{out} already holds a blind pair")
    order = secrets.choice([labels, labels[::-1]])
    key = f"A={order[0]};B={order[1]};salt={secrets.token_hex(16)}"
    out.mkdir(parents=True, exist_ok=True)
    secret.parent.mkdir(parents=True, exist_ok=True)
    (out / "A.txt").write_bytes(texts[order[0]])
    (out / "B.txt").write_bytes(texts[order[1]])
    secret.write_text(key + "\n", encoding="utf-8")
    (out / "commitment.json").write_text(json.dumps({
        "commitment": sha(key.encode("utf-8")), "A_sha256": sha(texts[order[0]]), "B_sha256": sha(texts[order[1]]),
        "labels": sorted(labels), "prepared": now()}, indent=1) + "\n", encoding="utf-8")
    print(f"A.txt and B.txt are in {out}; the order is in {secret}, which the author must not see.")
    print(f"After the author has read both: blind-pair.py choose --out {out} --pick A|B --note \"<their words>\"")


def choose(a):
    out = Path(a.out)
    committed(out)
    if (out / "choice.json").exists():
        die(f"{out / 'choice.json'} already records a pick")
    (out / "choice.json").write_text(json.dumps({"pick": a.pick, "note": a.note, "chosen": now()},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"recorded: {a.pick}. Reveal with: blind-pair.py reveal --out {out} --secret <file>")


def reveal(a):
    out, secret = Path(a.out), Path(a.secret)
    c = committed(out)
    if not (out / "choice.json").is_file():
        die("no pick is recorded: run choose before reveal")
    if not secret.is_file():
        die(f"no secret at {secret}")
    key = secret.read_text(encoding="utf-8").strip()
    if sha(key.encode("utf-8")) != c["commitment"]:
        die("the secret does not match the commitment: the order cannot be shown to be the one fixed before the read")
    fields = dict(part.split("=", 1) for part in key.split(";"))
    pick = json.loads((out / "choice.json").read_text(encoding="utf-8"))
    result = {"key": key, "commitment": c["commitment"], "A": fields["A"], "B": fields["B"], "pick": pick["pick"],
              "picked": fields[pick["pick"]], "note": pick.get("note"), "chosen": pick["chosen"], "revealed": now()}
    (out / "reveal.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"A = {fields['A']}, B = {fields['B']}; the author picked {pick['pick']} = {fields[pick['pick']]}")
    print(f"secret: {key}  (sha256 {c['commitment']}, as committed)")


def main():
    ap = argparse.ArgumentParser(description="Blind read of two versions of a passage.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--first", required=True)
    p.add_argument("--second", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--secret", required=True)
    p.add_argument("--labels", default="first,second", help="names for the two files, in the order given")
    c = sub.add_parser("choose")
    c.add_argument("--out", required=True)
    c.add_argument("--pick", required=True, choices=["A", "B"])
    c.add_argument("--note", default="")
    r = sub.add_parser("reveal")
    r.add_argument("--out", required=True)
    r.add_argument("--secret", required=True)
    a = ap.parse_args()
    {"prepare": prepare, "choose": choose, "reveal": reveal}[a.cmd](a)


if __name__ == "__main__":
    main()
