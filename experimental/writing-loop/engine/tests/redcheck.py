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
    ("B", "inbox.py", "if cand.exists() and cand not in seen:", "if False:",
     "test_inbox.InboxTest.test_a_dropped_folder_becomes_a_workspace_with_its_tex_files"),
    ("B", "inbox.py", 'if h == "Abstract":', 'if False:',
     "test_inbox.InboxTest.test_section_rules_follow_the_headings_with_the_abstract_flat"),
    ("A", "history.py", 's["line"] = text.count("\\n", 0, m.start()) + 1', 's["line"] = 1',
     "test_history.LocateTest.test_sentences_carry_the_file_and_line_where_they_start"),
    ("A", "lintel.py", 'where = " · ".join(x for x in (sec, f"第 {r[\'par\']} 段" if r.get("par") else None, at) if x)', 'where = sec',
     "test_lintel.LocateRowsTest.test_rows_carry_where_copy_and_both_texts"),
    ("1.1", "doctor.py", 'for key in ("evidence_dir", "keymap_from"):', "for key in ():",
     "test_doctor.DoctorTest.test_each_wrong_path_is_named"),
    ("1.1", "cli.py", 'print(f"doctor: {len(problems)} 项读不到或不存在")\n        return 1', 'print(f"doctor: {len(problems)} 项读不到或不存在")\n        return 0',
     "test_doctor.DoctorTest.test_cli_exit_code"),
    ("1.1", "doctor.py", "if not hits and history:", "if not hits and history and False:",
     "test_doctor.DoctorTest.test_a_rebound_workspace_whose_history_is_elsewhere_is_not_a_fault"),
    ("1.1", "doctor.py", "        elif not hits:\n            bad(", "        elif False:\n            bad(",
     "test_doctor.DoctorTest.test_a_rebound_workspace_whose_history_is_elsewhere_is_not_a_fault"),
    ("F3", "gitio.py", "    b = _batches.get(str(repo))\n    if b is None:", "    b = None\n    if b is None:",
     "test_gitio.BatchTest.test_inside_a_batch_reading_objects_starts_no_process"),
    ("F3", "gitio.py", '        return got[0] if got else None', '        return got[0] if got and got[1] == "blob" else None',
     "test_gitio.BatchTest.test_batch_answers_exactly_what_single_calls_answer"),
    ("F3", "gitio.py", "        _batches.pop(key, None)  # already gone if it broke mid-block", "        del _batches[key]",
     "test_gitio.BatchTest.test_a_batch_that_dies_falls_back_to_single_calls"),
    ("F3", "index.py", 'with gitio.batch(cfg["repo"]):', "if True:",
     "test_index.IndexTest.test_building_the_index_reads_blobs_without_a_process_each"),
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
     "test_lintel.OneActivityTest.test_revision_ignores_the_clock"),
    ("4.2", "lintel.py", 'if old is not None and old.get("revision") == a["revision"] and not stale:',
     "if False:", "test_lintel.SyncTest.test_unchanged_content_is_not_rewritten"),
    ("4.2", "lintel.py", "stale = not p.exists() or now - p.stat().st_mtime > heartbeat / 2",
     "stale = not p.exists()", "test_lintel.SyncTest.test_heartbeat_rewrites_the_same_bytes_so_seen_is_not_reset"),
    ("4.2", "lintel.py", "        if p.name not in keep and p.stem in LEGACY_IDS:", "        if False:",
     "test_lintel.SyncTest.test_a_card_from_the_old_six_card_producer_is_removed_but_another_manuscript_is_not"),
    ("4.2", "lintel.py", "        if p.name not in keep and p.stem in LEGACY_IDS:", "        if p.name not in keep:",
     "test_lintel.SyncTest.test_a_card_from_the_old_six_card_producer_is_removed_but_another_manuscript_is_not"),
    ("4.2", "lintel.py", '    elif lc and not lc["traced"]:', "    elif False:",
     "test_lintel.OneActivityTest.test_an_untraced_change_is_time_sensitive"),
    ("4.2", "lintel.py", 'label = _fit(lc["label"], LABEL_MAX) if lc.get("label") else "改了"', 'label = lc["label"] if lc.get("label") else "改了"',
     "test_lintel.OneActivityTest.test_the_wing_is_the_reason_claude_wrote_else_the_count"),
    ("4.2", "lintel.py", '    if problems:\n        text = "；".join(problems)[:20000]\n        label, tone, center, rank, flagged = "跑挂了"',
     '    if False:\n        text = "；".join(problems)[:20000]\n        label, tone, center, rank, flagged = "跑挂了"',
     "test_lintel.OneActivityTest.test_a_fault_outranks_a_change"),
    ("4.2", "lintel.py", '    return [a]', '    return [a, dict(a, id="draft")]',
     "test_lintel.OneActivityTest.test_one_activity_whatever_the_state"),
    ("4.2", "lintel.py", '    a = _prune(a)', '    a = a',
     "test_lintel.OneActivityTest.test_no_none_reaches_the_host"),
    ("4.2", "index.py", '    triggers = [t for t in c.get("triggers", ()) if isinstance(t, str) and t.startswith("h-")]',
     '    triggers = [t for t in c.get("triggers", ()) if isinstance(t, str)] or ["h-guess"]',
     "test_lintel.SummaryViewTest.test_untraced_changeset_guesses_nothing"),
    ("2.3", "explain.py", 'KEYS = {"读成": "reading", "改了": "changed", "依据": "basis", "标签": "label"}',
     'KEYS = {"读成": "reading", "改了": "changed", "依据": "basis"}',
     "test_explain.ParseTest.test_the_label_line_is_the_notch_wing_and_stays_short_in_the_record"),
    ("v2-D5", "lintel.py", "    if not registered(home, producer):\n        raise NotRegistered", "    if False:\n        raise NotRegistered",
     "test_lintel.OffByDefaultTest.test_unregistered_producer_writes_nothing_and_creates_no_directory"),
    ("v2-D5", "lintel.py", "return isinstance(producers, dict) and producer in producers", "return producer in (producers or ())",
     "test_lintel.OffByDefaultTest.test_malformed_registry_counts_as_unregistered"),
    ("v2-D5", "cli.py", "            print(e, file=sys.stderr)\n            return 2", "            print(e, file=sys.stderr)\n            return 0",
     "test_lintel.CliOffByDefaultTest.test_cli_refuses_with_exit_2_and_creates_nothing"),
    ('2.3', 'explain.py', '    if out["reading"] is None:\n        w = willow_reading(text)', '    if False:\n        w = willow_reading(text)',
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
    ('2.1', 'hooks/loop_hook.py', '            if _is_draft(rel, cfg["draft"]["glob"]) or', '            if False or',
     'test_hooks.TriggerTest.test_draft_and_ledger_writes_and_git_commands_ask_for_an_update'),
    ('2.2', 'hooks/loop_hook.py', '            if t and _under(t, human):', '            if False:',
     'test_hooks.GuardTest.test_absolute_and_relative_writes_into_human_are_refused_and_recorded'),
    ('2.2', 'hooks/loop_hook.py', 'if _command_name(words[0]) not in READ_ONLY or writes_human:', 'if writes_human:',
     'test_hooks.GuardTest.test_shell_writes_naming_human_are_refused_including_the_home_form'),
    ('2.2', 'hooks/loop_hook.py', 'writes_human = any(', 'writes_human = False and any(',
     'test_hooks.GuardTest.test_reading_human_is_allowed_but_redirecting_into_it_is_not'),
    ('2.2', 'hooks/loop_hook.py', '        if not touched:\n            continue\n', '',
     'test_hooks.GuardTest.test_reading_human_is_allowed_but_redirecting_into_it_is_not'),
    ('quote', 'hooks/loop_hook.py', '    if q:\n        return SEGMENTS.split(cmd)', '    if True:\n        return SEGMENTS.split(cmd)',
     'test_hooks.GuardTest.test_a_read_is_split_and_named_the_way_the_shell_does_it'),
    ('quote', 'hooks/loop_hook.py', '    return base if d in SYSTEM_BIN else _unquote(word)', '    return _unquote(word)',
     'test_hooks.GuardTest.test_a_read_is_split_and_named_the_way_the_shell_does_it'),
    ('quote', 'hooks/loop_hook.py', 'if ">" in w and set(w) <= OPERATOR]', 'if ">" in w]',
     'test_hooks.GuardTest.test_a_read_is_split_and_named_the_way_the_shell_does_it'),
    ('quote', 'hooks/loop_hook.py', '    return base if d in SYSTEM_BIN else _unquote(word)', '    return base',
     'test_hooks.GuardTest.test_quotes_do_not_hide_a_write'),
    ('quote', 'hooks/loop_hook.py', 'if not words or SUBSTITUTION.search(seg):', 'if not words:',
     'test_hooks.GuardTest.test_quotes_do_not_hide_a_write'),
    ('quote', 'hooks/loop_hook.py', '(c == "&" and cmd[i - 1:i] not in (">", "<") and cmd[i + 1:i + 2] != ">")', 'False',
     'test_hooks.GuardTest.test_quotes_do_not_hide_a_write'),
    ('quote', 'hooks/loop_hook.py', '    return [_unquote(words[i + 1]) for i, w', '    return [words[i + 1] for i, w',
     'test_hooks.GuardTest.test_quotes_do_not_hide_a_write'),
    ('2.1', 'hooks/loop_hook.py', '    return rel in glob if isinstance(glob, list) else fnmatch.fnmatch(rel, glob)', '    return fnmatch.fnmatch(rel, glob)',
     'test_hooks.TriggerTest.test_a_draft_made_of_several_files_is_matched_file_by_file'),
    ('envelope', 'hooks/loop_hook.py', 'r"bash-input|bash-stdout|bash-stderr|"', 'r""',
     'test_hooks.PromptTest.test_a_shell_command_run_with_bang_is_not_recorded_as_the_authors_words'),
    ('envelope', 'transcripts.py', '                    if raw.lstrip().startswith("<bash-input>"):', '                    if False:',
     'test_transcripts.TranscriptReadTest.test_a_shell_command_run_with_bang_is_not_an_authors_message'),
    ('envelope', 'hooks/loop_hook.py', '    if ENVELOPE.match(prompt):\n', '    if False:\n',
     'test_hooks.PromptTest.test_system_envelopes_are_not_recorded_as_the_authors_words'),
    ('envelope', 'hooks/loop_hook.py', '        return reminder  # the turn it starts can still edit the draft', '        return None',
     'test_hooks.PromptTest.test_system_envelopes_are_not_recorded_as_the_authors_words'),
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
    ('fix1', 'lintel.py', '{"label": "拦下", "value": str(len(notices))', '{"label": "拦下", "value": "0"',
     'test_lintel.OneActivityTest.test_passive_things_stay_off_the_wings'),
    ('fix2', 'cli.py', '                if a.rebuild:\n', '                if True:\n',
     'test_lintel.ResidentTest.test_the_resident_producer_reads_the_index_and_does_not_rebuild_it'),
    ('fix2', 'cli.py', '    return "loop" in r.stdout and "lintel" in r.stdout', '    return True',
     'test_lintel.ResidentTest.test_a_pid_that_is_not_a_producer_does_not_count_as_one'),
    ('fix2', 'hooks/loop_hook.py', '    if LN.registered(LN.lintel_home(), LN.PRODUCER) and not', '    if not',
     'test_hooks.ProducerTest.test_the_resident_producer_is_started_only_when_lintel_registered_it'),
    ('latex', 'text.py', '    tex = _TEX_COMMENT.sub("", tex)\n', '',
     'test_latex.LatexTest.test_sections_and_comments'),
    ('latex', 'text.py', '_TEX_COMMENT = re.compile(r"(?<!\\\\)%.*$", re.M)', '_TEX_COMMENT = re.compile(r"%.*$", re.M)',
     'test_latex.LatexTest.test_only_the_chosen_sections_become_sentences'),
    ('latex', 'history.py', 'md = "\\n\\n".join(t for _, t in texts)', 'md = gitio.show(repo, c["sha"], paths[0])',
     'test_latex.MultiFileTest.test_a_commit_to_either_file_is_a_new_version_of_one_draft'),
    ('latex', 'history.py', '    return list(g) if isinstance(g, list) else [f":(glob){g}"]', '    return [f":(glob){g}"]',
     'test_latex.MultiFileTest.test_a_commit_to_either_file_is_a_new_version_of_one_draft'),
    ('rebind', 'explain.py', '        if not line.strip() or WILLOW_STOP.match(line):', '        if WILLOW_STOP.match(line):',
     'test_explain.ParseTest.test_a_reading_written_over_several_lines_is_read_to_its_end'),
    ('rebind', 'explain.py', '        if cur is None or h.get("channel", "prompt") != "queued":', '        if True:',
     'test_explain.BuildTest.test_a_message_typed_mid_turn_does_not_take_the_turns_block'),
    ('rebind', 'transcripts.py', ' + [(s["git_branch"], str(s["cwd_prefix"])) for s in t.get("also", [])]', '',
     'test_hooks.AlsoSourceTest.test_an_also_source_is_read_but_the_hooks_do_not_act_on_it'),
    # 总览（lintel 分镜 ㊸–㊽，作者 09-21）
    ('overview', 'overview.py', 'if cur and v["time"] - cur[-1]["time"] >= gap_days * 86400:', 'if False:',
     'test_overview.StagesTest.test_a_gap_of_three_days_or_more_starts_a_stage'),
    ('overview', 'overview.py', '            if len(empty) >= gap_days:', '            if False:',
     'test_overview.StagesTest.test_a_long_empty_run_folds_into_one_gap_bar'),
    ('overview', 'overview.py', '    if not cur or action not in cur["actions"]:', '    if not cur:',
     'test_overview.AlignmentTest.test_an_action_the_panel_did_not_offer_writes_nothing'),
    ('overview', 'overview.py', '            args += ["--credits", str(cpath)]', '            pass',
     'test_overview.AlignmentTest.test_marking_a_method_credit_takes_the_sentence_out_of_missing'),
    ('overview', 'overview.py', 'cells.append({"title": "稿件仓 issue", "text": "取不到", "sub": "gh 没登录或断网，不写数"})',
     'cells.append({"title": "稿件仓 issue", "text": "已关 0 / 共 0", "sub": ""})',
     'test_overview.TodoTest.test_issues_that_cannot_be_asked_say_so_instead_of_zero'),
    ('overview', 'inbox.py', '        if _kind(p) == "action":\n            continue', '        if False:\n            continue',
     'test_overview.InboxActionTest.test_loop_inbox_does_not_refuse_an_action_as_a_bad_drop'),
    ('overview', 'inbox.py', 'if not isinstance(d, dict) or d.get("kind") != "action" or d.get("activity") != activity:',
     'if not isinstance(d, dict) or d.get("kind") != "action":',
     'test_overview.InboxActionTest.test_actions_for_another_manuscript_are_left_alone'),
    ('overview', 'lintel.py', '"rows": _rows(h, names) or None, "sections": secs([h["id"]])}', '"rows": _rows(h, names) or None}',
     'test_overview.PanelTest.test_overview_rides_on_the_detail_and_history_rows_name_their_sections'),
]


def _run_test(engine_dir, test, extra_paths=()):
    # AWT_LOOP_ENGINE tells out-of-tree tests (they locate the engine themselves) to use this copy,
    # otherwise they would import the unmutated engine and never go red.
    paths = [str(engine_dir), str(engine_dir / "tests"), *map(str, extra_paths)]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(paths), AWT_LOOP_ENGINE=str(engine_dir))
    # the copy has no repository root around it; the overview runs the toolkit's claim-ledger audit from the real one
    env.setdefault("LOOP_CLAIM_AUDIT", str(ENGINE.parents[2] / ".claude/skills/audit/scripts/audit-claim-ledger.py"))
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
