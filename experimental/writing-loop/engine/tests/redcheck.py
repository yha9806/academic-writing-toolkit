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
ROOT = ENGINE.parent  # experimental/writing-loop: engine/ and hooks/ are copied together, tests import both

# (step, file, old, new, test id). A bare file name is under engine/loop; a path with "/" is under ROOT.
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
    ('2.3', 'explain.py', '    if out["reading"] is None:\n        w = WILLOW.search(text)', '    if False:\n        w = WILLOW.search(text)',
     'test_explain.ParseTest.test_first_line_reading_counts_when_the_block_omits_it'),
    ('2.3', 'explain.py', 'if f and out[KEYS[f.group(1)]] is None and f.group(2):', 'if f and f.group(2):',
     'test_explain.ParseTest.test_first_occurrence_of_a_field_wins_and_empty_values_do_not_count'),
    ('2.3', 'explain.py', ' and a["session"] in h["sessions"]]', ']',
     'test_explain.BuildTest.test_replies_from_another_session_are_not_borrowed'),
    ('2.3', 'explain.py', 'out["over_limit"] = len(lines) > MAX_LINES', 'out["over_limit"] = False',
     'test_explain.ParseTest.test_more_than_six_lines_is_flagged_not_dropped'),
    ('2.4', 'health.py', 'if err and not err.get("cleared_at"):', 'if err:',
     'test_health.UpdateTest.test_a_failure_is_recorded_and_stays_visible_until_a_later_success'),
    ('2.4', 'health.py', '    if src.get("head") != head:', '    if False:',
     'test_health.HealthTest.test_a_new_commit_without_an_update_is_lag'),
    ('2.4', 'health.py', '    if src.get("transcripts") != now_files:', '    if False:',
     'test_health.HealthTest.test_a_grown_transcript_is_lag'),
    ('2.4', 'health.py', '    if not h.get("last_ok"):', '    if False:',
     'test_health.HealthTest.test_never_updated_is_a_problem_not_silence'),
    ('2.4', 'cli.py', '            dirty.touch()\n', '            pass\n',
     'test_health.UpdateTest.test_a_running_update_is_not_doubled_but_asked_to_go_round_again'),
    ('2.4', 'cli.py', 'if time.time() - lock.stat().st_mtime <= STALE_LOCK:', 'if True:',
     'test_health.UpdateTest.test_a_lock_left_by_a_killed_update_is_taken_over'),
    ('2.4', 'cli.py', '                    HL.record_error(ws, f"{type(e).__name__}：{e}")\n                    print(f"update 失败', '                    print(f"update 失败',
     'test_health.UpdateTest.test_a_failure_is_recorded_and_stays_visible_until_a_later_success'),
    ('2.1', 'hooks/loop_hook.py', '    prompt = payload.get("prompt")', '    prompt = payload.get("user_prompt")',
     'test_hooks.PromptTest.test_prompt_is_kept_verbatim_and_the_block_is_asked_for'),
    ('2.1', 'hooks/loop_hook.py', '    if not isinstance(prompt, str):\n        HL.record_event(', '    if not isinstance(prompt, str):\n        return None\n        HL.record_event(',
     'test_hooks.PromptTest.test_the_documentations_field_name_is_a_visible_error_not_silence'),
    ('2.1', 'hooks/loop_hook.py', '        if br == cfg["transcripts"]["git_branch"]:', '        if True:',
     'test_hooks.PromptTest.test_another_branch_or_directory_is_not_recorded'),
    ('2.1', 'hooks/loop_hook.py', '    elif tool == "Bash" and GIT_RE.search(', '    elif False and GIT_RE.search(',
     'test_hooks.TriggerTest.test_draft_and_ledger_writes_and_git_commands_ask_for_an_update'),
    ('2.1', 'hooks/loop_hook.py', '            if fnmatch.fnmatch(rel, cfg["draft"]["glob"]) or', '            if False or',
     'test_hooks.TriggerTest.test_draft_and_ledger_writes_and_git_commands_ask_for_an_update'),
    ('2.2', 'hooks/loop_hook.py', '            if t and _under(t, human):', '            if False:',
     'test_hooks.GuardTest.test_absolute_and_relative_writes_into_human_are_refused_and_recorded'),
    ('2.2', 'hooks/loop_hook.py', 'if seg.split()[0] not in READ_ONLY or writes_human:', 'if writes_human:',
     'test_hooks.GuardTest.test_shell_writes_naming_human_are_refused_including_the_home_form'),
    ('2.2', 'hooks/loop_hook.py', 'writes_human = any(', 'writes_human = False and any(',
     'test_hooks.GuardTest.test_reading_human_is_allowed_but_redirecting_into_it_is_not'),
    ('2.2', 'hooks/loop_hook.py', '        if not touched:\n            continue\n', '',
     'test_hooks.GuardTest.test_reading_human_is_allowed_but_redirecting_into_it_is_not'),
    ('2.2', 'hooks/loop_hook.py', '    p = os.path.expanduser(tok)', '    p = tok',
     'test_hooks.GuardTest.test_shell_writes_naming_human_are_refused_including_the_home_form'),
    ('2.2', 'hooks/loop_hook.py', '    path, root = _real(path), _real(root)', '    path, root = str(path), str(root)',
     'test_hooks.GuardTest.test_shell_writes_naming_human_are_refused_including_the_home_form'),
    ('2.5', 'index.py', 'json.dumps([salt, old, new, old_groups, new_groups]', 'json.dumps([salt, old, old_groups, new_groups]',
     'test_index.DiskCacheTest.test_a_rewritten_commit_does_not_reuse_the_old_alignment'),
    ('2.5', 'index.py', '            return json.loads(p.read_text(encoding="utf-8"))\n        except (OSError, ValueError):', '            return json.loads(p.read_text(encoding="utf-8"))\n        except OSError:',
     'test_index.DiskCacheTest.test_unreadable_cache_files_are_recomputed_not_trusted'),
    ('2.5', 'transcripts.py', 'known == [st.st_size, st.st_mtime_ns, False]', 'known[2] is False',
     'test_index.DiskCacheTest.test_a_session_file_that_gains_the_branch_is_read_again'),
    ('fix1', 'health.py', 'if e.get("kind") == kind and e.get("t", 0) > since]', 'if e.get("kind") == kind]',
     'test_health.AckTest.test_ack_clears_what_was_shown_but_keeps_the_record'),
    ('fix1', 'health.py', '    bad = _unacked(h, "hook_error")\n', '    bad = _unacked(h, "hook_error") + _unacked(h, "guard_denied")\n',
     'test_hooks.GuardTest.test_absolute_and_relative_writes_into_human_are_refused_and_recorded'),
    ('fix1', 'lintel.py', '"guard", source="tool", label="拦下", phase="human/", tag=f"{len(notices)} 项",\n            center="flagged", rank="none",', '"guard", source="tool", label="拦下", phase="human/", tag=f"{len(notices)} 项",\n            center="flagged", rank="anomaly",',
     'test_lintel.NewCardsTest.test_a_refused_write_is_a_notice_card_not_an_anomaly'),
    ('fix2', 'cli.py', '                if a.rebuild:\n', '                if True:\n',
     'test_lintel.ResidentTest.test_the_resident_producer_reads_the_index_and_does_not_rebuild_it'),
    ('fix2', 'cli.py', '    return "loop" in r.stdout and "lintel" in r.stdout', '    return True',
     'test_lintel.ResidentTest.test_a_pid_that_is_not_a_producer_does_not_count_as_one'),
    ('fix2', 'hooks/loop_hook.py', '    if LN.registered(LN.lintel_home(), LN.PRODUCER) and not', '    if not',
     'test_hooks.ProducerTest.test_the_resident_producer_is_started_only_when_lintel_registered_it'),
    ('fix3', 'lintel.py', '    if latest and latest.get("replies"):', '    if latest:',
     'test_lintel.NewCardsTest.test_a_reply_card_appears_and_changes_with_each_new_reply'),
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
    ignore = shutil.ignore_patterns("__pycache__", ".*")
    with tempfile.TemporaryDirectory() as b:
        # Baselines run in an unmutated copy laid out exactly like the mutated ones: a test that cannot even
        # run in a copy would otherwise "go red" for every mutation.
        base = Path(b) / "writing-loop"
        shutil.copytree(ROOT, base, ignore=ignore)
        for st, fname, old, new, test in mutations:
            if step and st != step:
                continue
            if test not in baseline:
                baseline[test] = _run_test(base / "engine", test, extra_paths)
            if not baseline[test]:
                print(f"[{st}] 基线就不通过  {test}（未注入故障时已失败，变红不说明任何事）")
                bad += 1
                continue
            bad += _mutate_and_run(st, fname, old, new, test, extra_paths, ignore)
    print(f"redcheck: {bad} 个变异没有被测试看见" if bad else "redcheck: 每个变异都让对应测试变红")
    return 1 if bad else 0


def _mutate_and_run(st, fname, old, new, test, extra_paths, ignore):
    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / "writing-loop"
        shutil.copytree(ROOT, root, ignore=ignore)
        dst = root / "engine"
        f = (root / fname) if "/" in fname else (dst / "loop" / fname)
        src = f.read_text(encoding="utf-8")
        if src.count(old) != 1:
            print(f"[{st}] {fname}: 变异锚点出现 {src.count(old)} 次（应为 1），无法注入")
            return 1
        f.write_text(src.replace(old, new), encoding="utf-8")
        red = not _run_test(dst, test, extra_paths)
        print(f"[{st}] {'变红' if red else '没变红'}  {test}  ← {fname}: {old[:50]!r}")
        return 0 if red else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
