"""Red check: each mutation breaks the engine in one known way; its named test must then fail.

  python3 engine/tests/redcheck.py [step]

A mutation whose test still passes means that test cannot see the fault it claims to guard.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]

# (step, file under engine/loop, old, new, test id)
MUTATIONS = [
    ("1.1", "doctor.py", 'for key in ("evidence_dir", "keymap_from"):', "for key in ():",
     "test_doctor.DoctorTest.test_each_wrong_path_is_named"),
    ("1.1", "cli.py", 'print(f"doctor: {len(problems)} 项读不到或不存在")\n        return 1', 'print(f"doctor: {len(problems)} 项读不到或不存在")\n        return 0',
     "test_doctor.DoctorTest.test_cli_exit_code"),
    ("1.2", "history.py", "aligner = aligner or A.align", "aligner = aligner or positional_aligner",
     "test_history.StableIdTest.test_moved_paragraph_keeps_ids"),
    ("1.2", "align.py", "if R >= JOIN_MIN and R >= single + JOIN_GAIN:", "if False:",
     "test_history.StableIdTest.test_split_and_merge_are_recognised"),
    ("1.2", "align.py", "if best and best[0] >= DERIVED_COVER:\n            derived.append", "if False:\n            derived.append",
     "test_history.StableIdTest.test_reused_text_across_a_gap_is_not_called_new"),
    ("1.2", "align.py", "need = min(MIN_RUN, len(pw))", "need = 1",
     "test_history.StableIdTest.test_scattered_common_words_are_not_reuse"),
    ("1.5", "transcripts.py", 'if att and att.get("type") == "queued_command"', 'if False and att and att.get("type") == "queued_command"',
     "test_transcripts.TranscriptReadTest.test_prompt_and_queued_messages_are_both_read"),
    ("1.5", "transcripts.py", 'key = (r["timestamp"], text)', 'key = (r["timestamp"], text, r.get("sessionId"))',
     "test_transcripts.TranscriptReadTest.test_copies_in_continued_sessions_count_once"),
    ("1.5", "transcripts.py", 'text = _REMINDER.sub("", raw).strip()', 'text = raw.strip()',
     "test_transcripts.TranscriptReadTest.test_injected_reminder_is_removed_and_counted"),
    ("1.5", "transcripts.py", 'k = f"origin:{kind}" if kind else _unclassified_kind(raw)\n                    uncl[k] = uncl.get(k, 0) + 1', 'pass',
     "test_transcripts.TranscriptReadTest.test_non_author_records_are_counted_not_dropped"),
    ("1.3", "changesets.py", "entering_or_leaving = sorted(w for w in shared if (w in df_prev) != (w in df_cur))", "entering_or_leaving = sorted(shared)",
     "test_changesets.TriggerTest.test_unrelated_message_is_not_a_trigger"),
    ("1.3", "changesets.py", "elif len(rare) >= MIN_SHARED_RARE:", "elif len(shared) >= MIN_SHARED_RARE:",
     "test_changesets.TriggerTest.test_unrelated_message_is_not_a_trigger"),
    ("1.3", "changesets.py", "    return words - STOP - PROCESS_WORDS", "    return words - STOP",
     "test_changesets.TriggerTest.test_unrelated_message_is_not_a_trigger"),
    ("1.3", "changesets.py", "if len(mids) > 1 or (mids and unknown):", "if len(mids) > 1:",
     "test_changesets.TriggerTest.test_mixed_commit_is_marked"),
    ("1.3", "changesets.py", "                if mid in known:", "                if True:",
     "test_changesets.TriggerTest.test_commit_trailer_must_point_to_a_real_message"),
    ("1.3", "changesets.py", "if entering_or_leaving:", "if False:",
     "test_changesets.TriggerTest.test_entering_word_attributes_the_row"),
    ("1.5", "threads.py", "if q in sn or (len(sn) >= 20 and sn in q):", "if False:",
     "test_threads.AttachTest.test_quoted_fragment_attaches"),
    ("1.5", "threads.py", 'if s and s["sid"] not in seen:', "if False:",
     "test_threads.AttachTest.test_label_attaches"),
    ("1.5", "threads.py", 'if v["time"] <= t:', "if True:",
     "test_threads.AttachTest.test_message_before_first_version_has_no_version"),
    ("1.5", "threads.py", 'if s and s["sid"] not in seen:', 'if s is None or s["sid"] not in seen:',
     "test_threads.AttachTest.test_label_that_does_not_exist_is_not_attached"),
    ("1.4", "checks.py", '        return {**out, "status": "not_found", "source_blob": blob}', '        return {**out, "status": "found", "source_blob": blob}',
     "test_checks.CheckTest.test_fabricated_span_is_not_found_and_only_its_sentence_changes"),
    ("1.4", "checks.py", 'json.dumps([norm(s["text"]), entries, blobs, maps_sig,', 'json.dumps([norm(s["text"]), blobs, maps_sig,',
     "test_checks.CheckTest.test_ledger_change_invalidates_the_cached_sentence"),
    ("1.4", "checks.py", "        if sig in cache:", "        if False:",
     "test_checks.CheckTest.test_only_changed_sentences_are_rechecked"),
    ("1.4", "checks.py", "            if weak_only[k] and False in dags:", "            if False:",
     "test_checks.CheckTest.test_dagger_and_missing_entries_are_reported"),
    ("1.4", "checks.py", "        if i < 0:\n            unattached.append(e)", "        if i < 0:\n            pass",
     "test_checks.CheckTest.test_missing_source_file_and_unattached_entry"),
    ("1.6", "index.py", '        elif p.read_bytes() != fresh[name]:', '        elif False:',
     "test_index.IndexTest.test_tampered_index_is_named_as_tampered"),
    ("1.6", "index.py", 'if (old.get("head"), old.get("transcripts")) != (new["head"], new["transcripts"]):', 'if False:',
     "test_index.IndexTest.test_new_commit_is_named_as_stale"),
    ("1.6", "index.py", 'chk = {k: v for k, v in chk.items() if k not in ("evaluated", "reused")}', 'chk = dict(chk)',
     "test_index.IndexTest.test_warm_and_cold_cache_give_the_same_bytes"),
    ("1.6", "index.py", '        if not p.exists():\n            diffs.append((name, "缺失"))', '        if not p.exists():\n            continue',
     "test_index.IndexTest.test_missing_index_file_is_reported"),
    ("4.2", "lintel.py", 'if "status" in body:', "if False:",
     "test_lintel.BuildTest.test_revision_ignores_the_clock"),
    ("4.2", "lintel.py", 'if old is not None and old.get("revision") == a["revision"] and not stale:',
     "if False:", "test_lintel.SyncTest.test_unchanged_content_is_not_rewritten"),
    ("4.2", "lintel.py", "stale = not p.exists() or now - p.stat().st_mtime > heartbeat / 2",
     "stale = not p.exists()", "test_lintel.SyncTest.test_heartbeat_rewrites_the_same_bytes_so_seen_is_not_reset"),
    ("4.2", "lintel.py", "        if p.name not in keep:", "        if False:",
     "test_lintel.SyncTest.test_a_problem_that_went_away_takes_its_card_with_it"),
    ("4.2", "lintel.py", 'center="flagged" if unknown else "assumed"', 'center="flagged"',
     "test_lintel.BuildTest.test_inferred_trigger_is_assumed_not_flagged"),
    ("v2-D5", "lintel.py", "    if not registered(home, producer):\n        raise NotRegistered", "    if False:\n        raise NotRegistered",
     "test_lintel.OffByDefaultTest.test_unregistered_producer_writes_nothing_and_creates_no_directory"),
    ("v2-D5", "lintel.py", "return isinstance(producers, dict) and producer in producers", "return producer in (producers or ())",
     "test_lintel.OffByDefaultTest.test_malformed_registry_counts_as_unregistered"),
    ("v2-D5", "cli.py", "            print(e, file=sys.stderr)\n            return 2", "            print(e, file=sys.stderr)\n            return 0",
     "test_lintel.CliOffByDefaultTest.test_cli_refuses_with_exit_2_and_creates_nothing"),
]


def _run_test(engine_dir, test, extra_paths=()):
    # AWT_LOOP_ENGINE tells out-of-tree tests (they locate the engine themselves) to use this copy,
    # otherwise they would import the unmutated engine and never go red.
    paths = [str(engine_dir), str(engine_dir / "tests"), *map(str, extra_paths)]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(paths), AWT_LOOP_ENGINE=str(engine_dir))
    r = subprocess.run([sys.executable, "-m", "unittest", test], cwd=engine_dir / "tests", env=env, capture_output=True)
    return r.returncode == 0


def run(step=None, mutations=None, extra_paths=()):
    mutations = MUTATIONS if mutations is None else mutations
    bad = 0
    baseline = {}
    for st, fname, old, new, test in mutations:
        if step and st != step:
            continue
        # A test that already fails on the unmodified engine would "go red" for any mutation: check it first.
        if test not in baseline:
            baseline[test] = _run_test(ENGINE, test, extra_paths)
        if not baseline[test]:
            print(f"[{st}] 基线就不通过  {test}（未注入故障时已失败，变红不说明任何事）")
            bad += 1
            continue
        with tempfile.TemporaryDirectory() as t:
            dst = Path(t) / "engine"
            shutil.copytree(ENGINE, dst, ignore=shutil.ignore_patterns("__pycache__"))
            f = dst / "loop" / fname
            src = f.read_text(encoding="utf-8")
            if src.count(old) != 1:
                print(f"[{st}] {fname}: 变异锚点出现 {src.count(old)} 次（应为 1），无法注入")
                bad += 1
                continue
            f.write_text(src.replace(old, new), encoding="utf-8")
            red = not _run_test(dst, test, extra_paths)
            print(f"[{st}] {'变红' if red else '没变红'}  {test}  ← {fname}: {old[:50]!r}")
            bad += 0 if red else 1
    print(f"redcheck: {bad} 个变异没有被测试看见" if bad else "redcheck: 每个变异都让对应测试变红")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
