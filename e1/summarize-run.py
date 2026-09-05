"""Summarise producer metrics and observed logs without changing any score."""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    root = args.run.resolve()
    metrics_path = root / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    arms = []
    sessions = []
    for arm in ("skills", "plain"):
        results = [result for result in metrics["results"] if result["arm"] == arm]
        outcomes = collections.Counter(outcome for result in results for outcome in result["taskOutcomes"])
        row = {
            "arm": arm, "sources": len(results),
            "sourceOpened": sum(result["sourceOpened"] for result in results),
            "notesPresent": sum(result["notes"]["present"] for result in results),
            "notesParseable": sum(result["notes"]["parseable"] for result in results),
            "draftsPresent": sum(result["unopenedCitations"]["draftPresent"] for result in results),
            "quotedSpans": sum(result["quoteFidelity"]["quotes"] for result in results),
            "matchedSpans": sum(result["quoteFidelity"]["matched"] for result in results),
            "pageCitedSpans": sum(result["pageAccuracy"]["cited"] for result in results),
            "correctPageSpans": sum(result["pageAccuracy"]["correct"] for result in results),
            "uncitedSpans": sum(result["pageAccuracy"]["uncited"] for result in results),
            "detectedDraftCitations": sum(result["unopenedCitations"]["citations"] for result in results),
            "unopenedDraftCitations": sum(len(result["unopenedCitations"]["unopened"]) for result in results),
            "taskOutcomes": dict(outcomes),
        }
        arms.append(row)
        for result in results:
            for log in sorted((root / result["artifacts"] / "sessions").rglob("*.jsonl")):
                events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
                usage = [event["data"]["usage"] for event in events if event.get("type") == "assistant/message" and "usage" in event.get("data", {})]
                calls = collections.Counter(event["data"]["name"] for event in events if event.get("type") == "tool/call")
                times = [event["time"] for event in events if isinstance(event.get("time"), (int, float))]
                ends = [event["data"]["reason"] for event in events if event.get("type") == "turn/end"]
                sessions.append({"source": result["id"], "arm": arm, "log": log.relative_to(root).as_posix(),
                                 "sha256": digest(log), "terminalReasons": ends, "toolCalls": dict(calls),
                                 "elapsedSeconds": round((max(times) - min(times)) / 1000, 3) if times else None,
                                 "assistantMessagesWithUsage": len(usage),
                                 "reportedInputTokens": sum(item.get("inputTokens", 0) for item in usage),
                                 "reportedOutputTokens": sum(item.get("outputTokens", 0) for item in usage)})
    failures = {}
    continuation = metrics.get("continuation")
    while continuation:
        for item in continuation.get("retriedTransportTasks", []):
            failures[item["failedLogSha256"]] = item
        continuation = continuation.get("earlierContinuation")
    summary = {"metricsSha256": digest(metrics_path), "status": metrics["status"], "evidenceClass": metrics["evidenceClass"],
               "model": metrics["model"], "harness": metrics["harness"], "arms": arms,
               "retainedSessionLogs": len(sessions), "uniqueSessionLogs": len({row["sha256"] for row in sessions}),
               "disclosedTransportRetries": list(failures.values()), "sessions": sessions,
               "notesErrors": {result["id"] + "/" + result["arm"]: result["notes"]["errors"] for result in metrics["results"]},
               "usageCaveat": "Counts are reported assistant-message usage, not bills. They exclude background title generation and requests without reported usage. Latency was not controlled."}
    (root / "analysis.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Machine-generated observation summary", "", "Derived from the producer's metrics and retained logs; no scores were edited.", "",
             "| arm | sources opened | notes present | notes lint pass | drafts present | matched / detected quotes | page-adjacent citations | detected draft citations |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in arms:
        n = row["sources"]
        lines.append("| {arm} | {sourceOpened}/{n} | {notesPresent}/{n} | {notesParseable}/{n} | {draftsPresent}/{n} | {matchedSpans}/{quotedSpans} | {pageCitedSpans} | {detectedDraftCitations} |".format(n=n, **row))
    lines.extend(["", "Task outcomes:", ""])
    for row in arms:
        lines.append("- " + row["arm"] + ": " + ", ".join(key + "=" + str(value) for key, value in sorted(row["taskOutcomes"].items())))
    lines.extend(["", "Interpretation limits:", "",
                  "- A completed headless task does not establish a conforming or author-accepted file.",
                  "- Zero detected quotes/page citations is not perfect fidelity; adjacent-page syntax coverage is limited.",
                  "- Quote matching uses the exact returned PDF extraction, normalised for whitespace and typography. Column interleaving, hyphenation and altered wording can all cause nonmatches; these counts do not establish semantic falsity.",
                  "- Zero unopened citations with zero detected draft citations supplies no evidence of correct referencing.",
                  "- Three convenience-sampled papers, one local model, a fixed order and no replication do not establish general skill efficacy or causality.",
                  "- Model failures remain in the table. A disclosed local transport retry is separate from the twelve retained task observations.",
                  "", "Retained session logs: " + str(len(sessions)) + "; unique log hashes: " + str(summary["uniqueSessionLogs"]) + ".",
                  "", "Metrics SHA-256: `" + summary["metricsSha256"] + "`.", ""])
    (root / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("status", "evidenceClass", "arms", "retainedSessionLogs", "uniqueSessionLogs", "disclosedTransportRetries")}, indent=2))


if __name__ == "__main__":
    main()
