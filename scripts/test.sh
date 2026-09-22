#!/usr/bin/env bash
# scripts/test.sh — runs the regression test suite (199 automated tests, labelled T2-T210: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features + T45-T49 reference metadata + T50 canonical skills tree + T54-T58 release governance + T59 docs consistency + T60 Markdown BibTeX + T61-T63 productization + T64-T72 thesis control + T73 lost-in-conversation bench + T74-T111 revision escalation and human gates + T112-T115 argument and clean-room review governance + T116-T124 project-intent control + T125-T126 verify-refs parser + T127-T128 prose fingerprint + T129-T130 claim positioning + T131-T134 estimator alignment + T137 lightweight author control + T138 Harvard/Markdown claim positioning + T139-T140 and T203 fingerprint baseline precondition + T142-T147 claim ledger + T148-T153 commit gate + T154-T157 fails-closed registry + T158-T162 review findings + T163-T168 and T198-T202 number ledger + T169-T171 audits that name what they did not read + T172-T174 claim-positioning precision + T175-T177 venue baseline construction + T178-T183 session scan + T184 the header's own count + T185-T187 the public-content audit reports what it read + T188-T189 the scripts/ audits fail closed and the docs' skill count is derived + T190 every path the README's structure block names exists + T191-T193 writing loop, experimental + T194-T195 method credits in the full claim-ledger scan + T204-T210 changed-sentence audit) for academic-writing-toolkit. Tests whose body reaches into archive/skills/ run only with AWT_TEST_RETIRED=1.
# Self-contained; saves and restores any state it mutates.
# Exit 0 if all tests pass, 1 if any fail. CI-suitable.
# Note: pipefail is intentionally NOT enabled. Several tests assert that a
# command exits non-zero (doctor on drift, sync on missing markers, make
# init without a tty) and then grep for the expected error message. Under
# pipefail the command's non-zero exit would trump grep's success and the
# pipeline would always evaluate as failure.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Several tests run doctor inside a throwaway copy of the repository, which has
# no project-local .venv. Doctor asks the export converter whether it can
# convert, so without this the copies fall back to the system interpreter and
# report a broken export the test did not introduce. Declared here rather than
# by loosening what those tests assert.
if [ -z "${AWT_PYTHON:-}" ]; then
    for _candidate in "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/.venv/Scripts/python.exe"; do
        [ -x "$_candidate" ] && { export AWT_PYTHON="$_candidate"; break; }
    done
fi
# Doctor asks the export converter whether it can convert, and several tests
# run doctor. Without a backend anywhere those tests fail as "T2 symlink
# corruption + repair", which points at nothing. Say it here instead.
if ! "${AWT_PYTHON:-python3}" "$REPO_ROOT/.claude/skills/export/scripts/convert_to_docx.py" --check >/dev/null 2>&1; then
    printf "\033[31merror:\033[0m the export converter has no conversion backend, so the tests that run doctor cannot pass.\n" >&2
    printf "       fix: make setup   (or: python3 -m venv .venv && .venv/bin/pip install -r .claude/skills/export/scripts/requirements.txt)\n" >&2
    exit 2
fi
source "$SCRIPT_DIR/lib.sh"

cd "$REPO_ROOT"

PASSES=0
FAIL_LIST=()

# A green suite total says how many tests ran, not what they cover. A large
# share of these exercise validators for bundles retired under archive/skills/,
# kept on purpose (README: history; validators run with `make test-all`) but
# easy to read as coverage of the live toolkit: "all N passed" was read that
# way once by the person writing this, with the split line printed right
# above it. The runner sorts each test by whether its body reaches into
# archive/skills/. Retired tests run only when AWT_TEST_RETIRED=1 (CI sets it);
# by default they stay registered and counted, and the summary says how many
# did not run, so the headline number is the live one. (This comment once
# said "59 of these"; nothing counted that either.)
RETIRED_PASSES=0
LIVE_PASSES=0
RETIRED_SKIPPED=0
RUN_RETIRED="${AWT_TEST_RETIRED:-0}"

_test_surface() {
    local body
    body=$(declare -f "$1" 2>/dev/null)
    case "$body" in
        *"archive/skills/"*) printf 'retired' ;;
        *) printf 'live' ;;
    esac
}

run_test() {
    local name="$1"
    local fn="$2"
    local surface
    surface=$(_test_surface "$fn")
    if [[ "$surface" == "retired" && "$RUN_RETIRED" != "1" ]]; then
        RETIRED_SKIPPED=$((RETIRED_SKIPPED+1))
        return 0
    fi
    if "$fn"; then
        pass "$name"
        PASSES=$((PASSES+1))
        if [[ "$surface" == "retired" ]]; then
            RETIRED_PASSES=$((RETIRED_PASSES+1))
        else
            LIVE_PASSES=$((LIVE_PASSES+1))
        fi
    else
        fail "$name"
        FAIL_LIST+=("$name")
    fi
}

_make_tmp_repo() {
    local tmp
    tmp=$(mktemp -d) || return 1
    cp -R \
        "$REPO_ROOT/scripts" \
        "$REPO_ROOT/templates" \
        "$REPO_ROOT/.claude" \
        "$REPO_ROOT/.agents" \
        "$REPO_ROOT/CLAUDE.md" \
        "$REPO_ROOT/AGENTS.md" \
        "$REPO_ROOT/GEMINI.md" \
        "$tmp" || return 1
    printf '%s\n' "$tmp"
}

# --- T2: symlink corruption recovery ----------------------------------------
test_T2() {
    local tmp skill
    tmp=$(_make_tmp_repo) || return 1
    skill=$(find "$tmp/.claude/skills" -maxdepth 1 -mindepth 1 -type d | head -1 | xargs basename)
    [[ -z "$skill" ]] && return 1

    rm -rf "$tmp/.agents/skills/$skill"
    mkdir -p "$tmp/.agents/skills/$skill"
    cp "$tmp/.claude/skills/$skill/SKILL.md" "$tmp/.agents/skills/$skill/SKILL.md" 2>/dev/null || true

    # doctor should fail (we expect non-zero exit)
    if (cd "$tmp" && bash scripts/doctor.sh >/dev/null 2>&1); then
        rm -rf "$tmp"
        return 1
    fi

    if ! (cd "$tmp" && bash scripts/repair.sh >/dev/null 2>&1); then
        rm -rf "$tmp"
        return 1
    fi

    # doctor should now pass — note: only the symlink check matters; if deps fail, that's not a T2 failure
    if test -L "$tmp/.agents/skills/$skill" && \
       [[ "$(readlink "$tmp/.agents/skills/$skill")" == "../../.claude/skills/$skill" ]]; then
        rm -rf "$tmp"
        return 0
    fi
    rm -rf "$tmp"
    return 1
}

# --- T3: sync drift detection ------------------------------------------------
test_T3() {
    local agents_backup
    agents_backup=$(mktemp)
    cp AGENTS.md "$agents_backup"

    echo "stray line for T3" >> AGENTS.md
    if bash scripts/doctor.sh 2>&1 | grep -q "config sync — AGENTS.md or GEMINI.md drifted"; then
        bash scripts/sync-config.sh >/dev/null 2>&1
        local restored_ok=0
        if diff -q AGENTS.md "$agents_backup" >/dev/null; then restored_ok=1; fi
        # Belt-and-braces: ensure backup state is on disk regardless of sync's
        # success, so a future sync regression cannot leave AGENTS.md corrupted.
        cp "$agents_backup" AGENTS.md
        rm -f "$agents_backup"
        [[ $restored_ok -eq 1 ]]
        return $?
    fi
    cp "$agents_backup" AGENTS.md
    rm -f "$agents_backup"
    return 1
}

# --- T4: CLAUDE.md edit propagation -----------------------------------------
test_T4() {
    local backup
    backup=$(mktemp)
    cp CLAUDE.md "$backup"

    # Use a marker that's unlikely to collide with real content
    local sentinel="T4_TEST_TOKEN_$$"
    echo "<!-- $sentinel -->" >> CLAUDE.md
    # Move sentinel into the SHARED block: place it just before SHARED:END.
    # On awk failure the && short-circuits the mv, but we must still clean
    # up CLAUDE.md.tmp ourselves — otherwise it lingers as untracked junk
    # and the next doctor/sync run trips on it.
    if awk -v s="<!-- $sentinel -->" '
        $0 == "<!-- SHARED:END -->" { print s }
        { print }
    ' "$backup" > CLAUDE.md.tmp; then
        mv CLAUDE.md.tmp CLAUDE.md
    else
        rm -f CLAUDE.md.tmp
        cp "$backup" CLAUDE.md
        rm -f "$backup"
        return 1
    fi

    bash scripts/sync-config.sh >/dev/null 2>&1
    local agents_has gemini_has
    grep -q "$sentinel" AGENTS.md && agents_has=1 || agents_has=0
    grep -q "$sentinel" GEMINI.md && gemini_has=1 || gemini_has=0

    cp "$backup" CLAUDE.md
    rm -f "$backup"
    bash scripts/sync-config.sh >/dev/null 2>&1
    [[ $agents_has -eq 1 && $gemini_has -eq 1 ]]
}

# --- T5: marker missing → sync aborts ---------------------------------------
test_T5() {
    local backup tmp
    backup=$(mktemp)
    tmp=$(mktemp -d)
    cp CLAUDE.md "$backup"

    grep -v "SHARED:START" "$backup" > CLAUDE.md
    if bash scripts/sync-config.sh CLAUDE.md "$tmp" 2>&1 | grep -q "expected exactly one"; then
        local exit_correct=1
    else
        local exit_correct=0
    fi

    cp "$backup" CLAUDE.md
    rm -rf "$backup" "$tmp"
    [[ $exit_correct -eq 1 ]]
}

# --- T8: idempotency ---------------------------------------------------------
test_T8() {
    bash scripts/sync-config.sh >/dev/null 2>&1
    local hash1 hash2
    hash1=$(cat AGENTS.md GEMINI.md | shasum | cut -d' ' -f1)
    bash scripts/sync-config.sh >/dev/null 2>&1
    hash2=$(cat AGENTS.md GEMINI.md | shasum | cut -d' ' -f1)
    [[ "$hash1" == "$hash2" ]]
}

# --- T9: make init aborts in non-interactive mode ---------------------------
test_T9() {
    if make init < /dev/null 2>&1 | grep -q "make init requires a tty"; then
        return 0
    fi
    return 1
}

# --- T10: core.fileMode auto-fix --------------------------------------------
test_T10() {
    local orig
    orig=$(git config --get core.fileMode || echo "__UNSET__")
    git config --unset core.fileMode 2>/dev/null || true

    bash scripts/repair.sh >/dev/null 2>&1
    local after
    after=$(git config --get core.fileMode || echo "__UNSET__")

    # Restore (or leave at false if it was unset; false is the desired state anyway)
    if [[ "$orig" != "__UNSET__" && "$orig" != "false" ]]; then
        git config core.fileMode "$orig"
    fi

    [[ "$after" == "false" ]]
}

# --- T11: no CLAUDE_SKILL_DIR in skill files --------------------------------
test_T11() {
    # No CLAUDE_SKILL_DIR references in skill prose or user docs.
    # Return 0/1 (run_test handles output) to match T2-T10 style.
    ! grep -rq 'CLAUDE_SKILL_DIR' "$REPO_ROOT/.claude/skills/" "$REPO_ROOT/docs/skills/"
}

# --- T12: no export_output in skill files -----------------------------------
test_T12() {
    # No export_output references in skill prose or user docs
    ! grep -rq 'export_output' "$REPO_ROOT/.claude/skills/" "$REPO_ROOT/docs/skills/"
}

# --- T13: no `revisiting` status enum ---------------------------------------
test_T13() {
    # No `revisiting` status anywhere — only `reading | completed | integrated`
    # docs/superpowers/ contains internal design specs that may legitimately describe
    # the bug; only skill docs and README are user-facing.
    ! grep -rqE '\brevisiting\b' "$REPO_ROOT/README.md" "$REPO_ROOT/.cursor/" "$REPO_ROOT/docs/skills/" "$REPO_ROOT/.claude/skills/" 2>/dev/null
}

# --- T14: no deprecated vocab in /map+/note ---------------------------------
test_T14() {
    # No deprecated vocab (argue|cite|data|method) in matrix-cell context
    # within /map skill files and the /note user doc's standard-types section.
    local files=(
        "$REPO_ROOT/.claude/skills/map/SKILL.md"
        "$REPO_ROOT/docs/skills/04-map.md"
    )
    # Scope to lines containing | (table-cell delimiter) to skip prose like
    # "data consistency" or "must cite the source".
    if grep -E '\|.*\b(argue|cite|data|method)\b' "${files[@]}" 2>/dev/null | grep -q .; then
        return 1
    fi
    # Also check the /note user doc for the 6-element list as "standard types"
    ! grep -qE '`(argue|cite|data|method)`' "$REPO_ROOT/docs/skills/02-note.md"
}

# --- T15: no compile_pdf.py references --------------------------------------
test_T15() {
    # No compile_pdf.py references in user-facing docs — that script does not exist.
    # docs/superpowers/ contains internal design specs that may legitimately describe
    # the bug; only skill docs and README are user-facing.
    ! grep -rq 'compile_pdf.py' "$REPO_ROOT/docs/skills/" "$REPO_ROOT/README.md"
}

# --- T16: no PDF export claim in setup docs ---------------------------------
test_T16() {
    # No "Word/PDF" or "to Word and PDF" in setup docs — /export only produces .docx + .zip
    ! grep -lE '(Word/PDF|to Word and PDF)' "$REPO_ROOT"/docs/setup-*.md 2>/dev/null | grep -q .
}

# --- T17: Python 3.8 import safety ------------------------------------------
test_T17() {
    local script="$REPO_ROOT/.claude/skills/export/scripts/convert_to_docx.py"
    grep -q '^from __future__ import annotations$' "$script" || return 1
    if command -v python3.8 >/dev/null 2>&1; then
        python3.8 -c "import importlib.util as u; s=u.spec_from_file_location('m','$script'); m=u.module_from_spec(s); s.loader.exec_module(m)" 2>/dev/null || return 1
    fi
    return 0
}

# --- T18: allowed-tools sanity (/map + /verify) -----------------------------
test_T18() {
    # /map needs Write (line 62 says "use Write if creating new")
    grep -qE '^allowed-tools:.*\bWrite\b' "$REPO_ROOT/.claude/skills/map/SKILL.md" || return 1
    # /verify needs Read (Edit requires prior Read per harness contract)
    grep -qE '^allowed-tools:.*\bRead\b' "$REPO_ROOT/archive/skills/verify/SKILL.md" || return 1
    return 0
}

# --- Citation tests (T19-T31): C-rest /audit citation enhancement ----------
# Each test invokes scripts/audit-citations.py against a fixture under
# tests/citation/fixtures/<name>/ and asserts on the JSON output's exit
# code + at least one issue with the expected `kind`. Stdlib only.

# Helper: run audit-citations.py and assert (exit code, kind) — prints
# nothing on success; non-zero return propagates failure to run_test.
_assert_citation() {
    local fixture="$1"
    local style_arg="$2"   # may be empty string when --style omitted
    local expected_exit="$3"
    local expected_kind="$4"
    local out rc
    if [[ -n "$style_arg" ]]; then
        out=$(python3 scripts/audit-citations.py \
            --base-dir "tests/citation/fixtures/$fixture" \
            --style "$style_arg" --json 2>&1)
    else
        out=$(python3 scripts/audit-citations.py \
            --base-dir "tests/citation/fixtures/$fixture" --json 2>&1)
    fi
    rc=$?
    if [[ "$rc" -ne "$expected_exit" ]]; then
        echo "  expected exit $expected_exit, got $rc for fixture $fixture" >&2
        echo "$out" >&2
        return 1
    fi
    if [[ -n "$expected_kind" ]]; then
        echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
kind = sys.argv[1]
issues = [i for i in d['issues'] if i['kind'] == kind]
if not issues:
    print('expected kind=' + kind + ', got kinds=' + str(sorted(set(i['kind'] for i in d['issues']))), file=sys.stderr)
    sys.exit(1)
" "$expected_kind" || return 1
    fi
    return 0
}

test_T19() { _assert_citation phantom harvard 1 phantom; }
test_T20() { _assert_citation unused harvard 1 unused; }
test_T21() { _assert_citation mixed_style "" 1 style-outlier; }
test_T22() { _assert_citation format_apa_in_harvard_project harvard 1 format-comma; }
test_T23() { _assert_citation format_harvard_in_apa_project apa 1 format-comma; }
test_T24() { _assert_citation source_lint_fail harvard 1 notes-source-malformed; }
test_T25() { _assert_citation multi_author_etal apa 1 format-etal-threshold; }
test_T26() { _assert_citation clean_chicago_ad chicago-author-date 0 ""; }
test_T27() { _assert_citation unused_mla mla 1 unused; }
test_T28() { _assert_citation numeric_gap ieee 1 numeric-gap; }
test_T29() { _assert_citation clean_vancouver vancouver 0 ""; }
test_T30() { _assert_citation clean_gb_2015 gb-t-7714-2015 0 ""; }
test_T31() { _assert_citation multi_author_etal harvard 1 format-etal-threshold; }

# --- T32: repair reports unwritable .agents clearly -------------------------
test_T32() {
    local tmp skill out rc
    tmp=$(_make_tmp_repo) || return 1
    skill=$(find "$tmp/.claude/skills" -maxdepth 1 -mindepth 1 -type d | head -1 | xargs basename)
    [[ -z "$skill" ]] && return 1

    rm -rf "$tmp/.agents/skills/$skill"
    mkdir -p "$tmp/.agents/skills/$skill"
    cp "$tmp/.claude/skills/$skill/SKILL.md" "$tmp/.agents/skills/$skill/SKILL.md" 2>/dev/null || true
    chmod 555 "$tmp/.agents" "$tmp/.agents/skills"

    out=$(cd "$tmp" && bash scripts/repair.sh 2>&1)
    rc=$?

    chmod 755 "$tmp/.agents" "$tmp/.agents/skills" 2>/dev/null || true
    rm -rf "$tmp"

    [[ "$rc" -eq 2 ]] || return 1
    echo "$out" | grep -q "cannot repair broken skill symlinks"
}

# --- T33-T44: public toolkit cleanup + writing-quality utilities ------------

test_T33() {
    python3 scripts/audit-public-content.py --base-dir . --json >/dev/null
}

test_T34() {
    [[ ! -e "$REPO_ROOT/docs/superpowers" ]]
}

test_T35() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter

The color of this programme will analyze behavior.
EOF
    out=$(python3 scripts/audit-british-english.py --base-dir "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert {i['current'] for i in d['issues']} >= {'color','analyze','behavior'}"
}

test_T36() {
    local tmp
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter

The color of this programme will analyze behavior.
EOF
    python3 scripts/audit-british-english.py --base-dir "$tmp" --fix >/dev/null || { rm -rf "$tmp"; return 1; }
    grep -q "colour" "$tmp/chapters/ch01.md" || { rm -rf "$tmp"; return 1; }
    grep -q "analyse" "$tmp/chapters/ch01.md" || { rm -rf "$tmp"; return 1; }
    grep -q "behaviour" "$tmp/chapters/ch01.md" || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
}

test_T37() {
    local out rc
    out=$(python3 scripts/audit-citations.py \
        --base-dir tests/citation/fixtures/format_apa_in_harvard_project \
        --style harvard --fix-safe --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('fixes'); assert any(f['replacement'] == '(Smith 2024)' for f in d['fixes'])"
}

test_T38() {
    local tmp
    tmp=$(mktemp -d) || return 1
    cp -R tests/citation/fixtures/format_apa_in_harvard_project/. "$tmp/"
    python3 scripts/audit-citations.py --base-dir "$tmp" --style harvard --fix-safe --apply --json >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    grep -q "(Smith 2024)" "$tmp/chapters/ch01.md"
    local ok=$?
    rm -rf "$tmp"
    return "$ok"
}

test_T39() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter

This is a short paragraph.

Furthermore, this paragraph starts with a transition but gives no clear topic sentence.

Furthermore, this paragraph repeats the same transition and remains isolated from the previous point.
EOF
    out=$(python3 scripts/audit-logic.py --base-dir "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'short-paragraph' in kinds and 'repeated-transition' in kinds"
}

test_T40() {
    local tmp
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs"
    cat > "$tmp/refs/paper.bib" <<'EOF'
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools},
  doi = {10.1000/example}
}
EOF
    python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --json >/dev/null
    local ok=$?
    rm -rf "$tmp"
    return "$ok"
}

test_T41() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs"
    cat > "$tmp/refs/bad.bib" <<'EOF'
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools},
  arxiv_id = {bad-id}
}

@article{smith2024,
  title = {Duplicate Key},
  author = {Jones, Alex},
  year = {2024},
  journal = {Journal of Tools}
}
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/bad.bib" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'duplicate-key' in kinds and 'arxiv-invalid' in kinds"
}

test_T42() {
    local skill_dir skill mode
    while IFS= read -r -d '' skill_dir; do
        skill="$(basename "$skill_dir")"
        [[ -f "$REPO_ROOT/.claude/skills/$skill/SKILL.md" ]] || return 1
        [[ -L "$REPO_ROOT/.agents/skills/$skill" ]] || return 1
        [[ "$(readlink "$REPO_ROOT/.agents/skills/$skill")" == "../../.claude/skills/$skill" ]] || return 1
        mode="$(git -C "$REPO_ROOT" ls-files -s ".agents/skills/$skill" | awk '{print $1}')"
        [[ "$mode" == "120000" ]] || return 1
    done < <(find "$REPO_ROOT/.claude/skills" -maxdepth 1 -mindepth 1 -type d -print0 | sort -z)
}

test_T43() {
    grep -q "/verify-refs" "$REPO_ROOT/README.md" || return 1
    grep -q "/read" "$REPO_ROOT/README.md" || return 1
    grep -q "/note" "$REPO_ROOT/README.md" || return 1
    grep -q "/map" "$REPO_ROOT/README.md" || return 1
    grep -q "/integrate" "$REPO_ROOT/README.md" || return 1
    grep -q "/review" "$REPO_ROOT/README.md" || return 1
    grep -q "/audit" "$REPO_ROOT/README.md" || return 1
    grep -q "/export" "$REPO_ROOT/README.md" || return 1
    grep -q "local agent skill" "$REPO_ROOT/README.md" || return 1
    grep -q "test-catalogue.mjs" "$REPO_ROOT/README.md" || return 1
    grep -q ".claude/skills/verify-refs/scripts/verify-refs.py --bib" "$REPO_ROOT/README.md" || return 1
    grep -q -- "--metadata-dir" "$REPO_ROOT/README.md" || return 1
    ! grep -q "room for explicit online checks" "$REPO_ROOT/README.md" || return 1
    ! grep -R -q "docs/superpowers" "$REPO_ROOT/README.md" "$REPO_ROOT/docs" "$REPO_ROOT/.claude/skills" || return 1
    # "8 academic writing skills" was the stale count once and was banned here;
    # eight is the count now, and T189 derives it from disk instead.
}

test_T44() {
    python3 scripts/audit-public-content.py --base-dir "$REPO_ROOT" >/dev/null
}

test_T45() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs" "$tmp/meta/crossref" "$tmp/meta/semantic-scholar"
    cat > "$tmp/refs/paper.bib" <<'EOF'
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane and Jones, Alex},
  year = {2024},
  journal = {Journal of Tools},
  doi = {10.1000/example}
}
EOF
    cat > "$tmp/meta/crossref/10.1000_example.json" <<'EOF'
{"message":{"title":["A Generic Toolkit Study"],"author":[{"family":"Smith"},{"family":"Jones"}],"published-print":{"date-parts":[[2024]]},"container-title":["Journal of Tools"]}}
EOF
    cat > "$tmp/meta/semantic-scholar/10.1000_example.json" <<'EOF'
{"title":"A Generic Toolkit Study","authors":[{"name":"Jane Smith"},{"name":"Alex Jones"}],"year":2024,"venue":"Journal of Tools"}
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['metadata_checks']; assert d['verified'][0]['entry']=='smith2024'"
}

test_T46() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs" "$tmp/meta/crossref" "$tmp/meta/semantic-scholar"
    cat > "$tmp/refs/paper.bib" <<'EOF'
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools},
  doi = {10.1000/example}
}
EOF
    cat > "$tmp/meta/crossref/10.1000_example.json" <<'EOF'
{"message":{"title":["A Completely Different Article"],"author":[{"family":"Smith"}],"published-print":{"date-parts":[[2024]]},"container-title":["Journal of Tools"]}}
EOF
    cat > "$tmp/meta/semantic-scholar/10.1000_example.json" <<'EOF'
{"title":"A Generic Toolkit Study","authors":[{"name":"Jane Smith"}],"year":2024,"venue":"Journal of Tools"}
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='metadata-title-low-similarity' for i in d['issues'])"
}

test_T47() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs" "$tmp/meta/crossref" "$tmp/meta/semantic-scholar"
    cat > "$tmp/refs/paper.bib" <<'EOF'
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools},
  doi = {10.1000/example}
}
EOF
    cat > "$tmp/meta/crossref/10.1000_example.json" <<'EOF'
{"message":{"title":["A Generic Toolkit Study"],"author":[{"family":"Smith"}],"published-print":{"date-parts":[[2020]]},"container-title":["Journal of Tools"]}}
EOF
    cat > "$tmp/meta/semantic-scholar/10.1000_example.json" <<'EOF'
{"title":"A Generic Toolkit Study","authors":[{"name":"Jane Smith"}],"year":2024,"venue":"Journal of Tools"}
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='metadata-year-mismatch' for i in d['issues'])"
}

test_T48() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs" "$tmp/meta/arxiv" "$tmp/meta/semantic-scholar"
    cat > "$tmp/refs/paper.bib" <<'EOF'
@misc{smith2024,
  title = {A Generic Preprint Study},
  author = {Smith, Jane},
  year = {2024},
  eprint = {2401.12345}
}
EOF
    cat > "$tmp/meta/arxiv/2401.12345.xml" <<'EOF'
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>A Generic Preprint Study</title>
    <published>2024-01-02T00:00:00Z</published>
    <author><name>Jane Smith</name></author>
  </entry>
</feed>
EOF
    cat > "$tmp/meta/semantic-scholar/2401.12345.json" <<'EOF'
{"title":"A Generic Preprint Study","authors":[{"name":"Jane Smith"}],"year":2024,"venue":"arXiv"}
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(v['source']=='arxiv' for v in d['verified'])"
}


test_T125() {
    # red-first: unbraced numeric fields must parse (regex parser regression)
    local tmp; tmp="$(mktemp -d)"
    cat > "$tmp/refs.bib" <<'BIB'
@article{plain2024,
  title = {Plain Year Entry},
  author = {Smith, Jane},
  year = 2024,
  journal = {Journal of Tools}
}
BIB
    out="$(python3 "$REPO_ROOT/.claude/skills/verify-refs/scripts/verify-refs.py" --bib "$tmp/refs.bib" --json)" || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
    ! echo "$out" | grep -q "missing-required-field" || return 1
}

test_T126() {
    # red-first: brace-protected values must not truncate at inner braces
    local tmp; tmp="$(mktemp -d)"
    cat > "$tmp/refs.bib" <<'BIB'
@article{nested2024,
  title = {The {AWT} Story: Nested {Braces} Survive},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools}
}
BIB
    out="$(python3 - "$tmp/refs.bib" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vr", ".claude/skills/verify-refs/scripts/verify-refs.py")
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
entries = vr.parse_bibtex(open(sys.argv[1]).read())
print(entries[0]["fields"]["title"])
PY
)" || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
    [[ "$out" == "The {AWT} Story: Nested {Braces} Survive" ]] || return 1
}

test_T49() {
    python3 .claude/skills/verify-refs/scripts/verify-refs.py --help | grep -q -- "--online" || return 1
    python3 .claude/skills/verify-refs/scripts/verify-refs.py --help | grep -q -- "--metadata-dir"
}

test_T60() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/refs"
    cat > "$tmp/refs/papers.md" <<'EOF'
# References

```bibtex
@article{smith2024,
  title = {A Generic Toolkit Study},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Tools},
  doi = {10.1000/example}
}
```
EOF
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py "$tmp/refs/papers.md" --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['entries'] == 1 and not d['issues']"
}

test_T61() {
    local demo="$REPO_ROOT/examples/demo-project"
    local use_cases="$REPO_ROOT/docs/use-cases"

    [[ -f "$demo/README.md" ]] || return 1
    [[ -f "$demo/CLAUDE.md" ]] || return 1
    [[ -f "$demo/AGENTS.md" ]] || return 1
    [[ -f "$demo/GEMINI.md" ]] || return 1
    [[ -f "$demo/chapters/ch01.md" ]] || return 1
    [[ -f "$demo/literature/reading_notes/smith2024_NOTES.md" ]] || return 1
    [[ -f "$demo/literature/reading_notes/jones2023_NOTES.md" ]] || return 1
    [[ -f "$demo/references.bib" ]] || return 1

    [[ -f "$use_cases/README.md" ]] || return 1
    [[ -f "$use_cases/write-literature-review.md" ]] || return 1
    [[ -f "$use_cases/audit-thesis-citations.md" ]] || return 1
    [[ -f "$use_cases/verify-references-before-submission.md" ]] || return 1
    [[ -f "$use_cases/prepare-release-governance-packet.md" ]] || return 1

    grep -q "agent-native" "$REPO_ROOT/README.md" || return 1
    grep -q "local-first" "$REPO_ROOT/README.md" || return 1
    grep -q "10-minute demo" "$REPO_ROOT/README.md" || return 1
    grep -q "docs/use-cases" "$REPO_ROOT/README.md" || return 1
    grep -q "examples/demo-project" "$REPO_ROOT/README.md" || return 1
}

test_T62() {
    local demo="$REPO_ROOT/examples/demo-project"
    local out

    python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$demo/references.bib" --json >/dev/null || return 1
    python3 archive/skills/evidence-review/scripts/check_review_package.py "$demo" --strict >/dev/null || return 1
    out=$(python3 archive/skills/release-governance/scripts/check_release_packet.py "$demo" --json) || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0"
}

test_T63() {
    python3 - "$REPO_ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = [
    root / "README.md",
    root / "docs/use-cases/README.md",
    root / "docs/use-cases/write-literature-review.md",
    root / "docs/use-cases/audit-thesis-citations.md",
    root / "docs/use-cases/verify-references-before-submission.md",
    root / "docs/use-cases/prepare-release-governance-packet.md",
    root / "examples/demo-project/README.md",
]
pattern = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
missing = []
for path in files:
    if not path.is_file():
        missing.append(str(path.relative_to(root)))
        continue
    text = path.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        candidate = (path.parent / target).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            missing.append(f"{path.relative_to(root)} -> {target}")
            continue
        if not candidate.exists():
            missing.append(f"{path.relative_to(root)} -> {target}")
if missing:
    raise SystemExit("\n".join(missing))
PY
}

_write_valid_project_intent_layer() {
    local root="$1"
    mkdir -p "$root/thesis_control"
    cat > "$root/thesis_control/project_intent.csv" <<'EOF'
intent_id,intent_version,supersedes_intent_id,primary_domain,research_object,core_research_question,target_venue,must_include_concepts,excluded_reframes,amendment_reason,approval_evidence,human_approved,status
pi-project-001,1,,academic writing control,AI-assisted manuscript revision,How can authors keep manuscript revisions aligned with their approved research intent?,research methods readers,author intent;research question;scope boundary,do not replace the primary research object with a generic tooling survey,initial project intent,explicit fixture author approval,true,active
EOF
    cat > "$root/thesis_control/manuscript_contracts.csv" <<'EOF'
manuscript_id,intent_id,manuscript_version,supersedes_manuscript_id,title,abstract_focus,primary_domain,research_object,research_question,contribution_scope,structure_summary,change_summary,human_approved,status
mc-project-001,pi-project-001,1,,Author-controlled manuscript revision,Bounded revision control for AI-assisted academic writing,academic writing control,AI-assisted manuscript revision,How can authors keep manuscript revisions aligned with their approved research intent?,structural governance without claims of scholarly truth,intent then section contracts then audits,initial manuscript contract,true,active
EOF
    cat > "$root/thesis_control/global_thesis_audits.csv" <<'EOF'
global_audit_id,intent_id,manuscript_id,manuscript_version,title_alignment,abstract_alignment,primary_domain_alignment,research_object_alignment,research_question_alignment,contribution_alignment,structure_alignment,detected_reframe,reframe_summary,human_review_required,human_decision,status
ga-project-001,pi-project-001,mc-project-001,1,aligned,aligned,aligned,aligned,aligned,aligned,aligned,false,no project-level drift detected,false,accept,passed
EOF
}

_make_valid_thesis_control_packet() {
    local tmp="$1"
    mkdir -p "$tmp/thesis_control" "$tmp/chapters"
    cat > "$tmp/chapters/ch02.md" <<'EOF'
# Chapter 2

Local-first writing workflows can make source notes inspectable, but this section only claims that file-based records improve traceability within one project. It does not claim that such workflows improve scholarly quality by themselves.
EOF
    _write_valid_project_intent_layer "$tmp"
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,manuscript_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch02-s1,mc-project-001,chapters/ch02.md,Local workflow control,This unit argues that file-based records improve traceability within one writing project by keeping notes and claims inspectable.,single-project workflow traceability only,file-based records improve traceability;the workflow does not prove scholarly quality,do not claim quality improvement;preserve single-project boundary
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,global_audit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch02-s1,ga-project-001,ri-ch02-traceability,1,clarify topic sentence in first paragraph,make the traceability claim clearer without changing its scope,do not add quality improvement claims;do not remove single-project boundary,check following paragraph for repeated boundary language,spine sentence preserved;no new unsupported claim,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,accept,false,passed
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
EOF
}

_make_valid_argument_packet() {
    local tmp="$1"
    mkdir -p "$tmp/evidence"
    cat > "$tmp/evidence/intent_register.csv" <<'EOF'
intent_id,paper_title,central_problem,target_venue,target_readers,field_positioning,core_gap,current_dominant_narrative,narrative_to_correct,why_now,main_contribution_ids,boundary_statement,success_criterion,reviewer_risk_level,notes
I1,Example paper,Current reviews lack traceable argument checks,Example venue,reviewers and authors,writing tools,Gap-contribution and claim-evidence links are implicit,Manuscripts can be judged by citation count alone,Argument systems need explicit links,Review workflows increasingly use agents,C1,This is a governance aid not a scientific validity guarantee,All main claims are source anchored,medium,fixture
EOF
    cat > "$tmp/evidence/contribution_chain.csv" <<'EOF'
contribution_id,intent_id,gap_id,gap_statement,gap_type,why_gap_matters,insight,contribution_statement,contribution_type,method_or_artifact_id,primary_claim_ids,required_evidence_type,current_evidence_ids,evidence_coverage,limitation,boundary_language,reviewer_defense_note
C1,I1,G1,Manuscript claims often lack explicit hierarchy,governance_gap,Flat claims hide weak evidence,Argument structure can be checked separately from scientific validity,We provide an argument-governance schema,governance_framework,AG1,CL1,governance schema evidence,E1,adequate,Does not prove manuscript quality,Validates structure only,Checker reports structural issues
EOF
    cat > "$tmp/evidence/claim_hierarchy.csv" <<'EOF'
claim_id,parent_claim_id,root_intent_id,contribution_id,section_id,claim_level,claim_role,claim_text,depends_on_claim_ids,evidence_requirement,evidence_ids,citation_keys,evidence_status,evidence_strength,support_balance,system_role,overclaim_risk,boundary_language,revision_action
CL0,,I1,,intro,paper_thesis,interpretive_claim,Argument systems need explicit governance,,packet evidence,E1,,verified_full_text_supported,adequate,adequately_supported,states_implication,low,Within the packet scope,none
CL1,CL0,I1,C1,intro,contribution_claim,artifact_claim,The schema links gaps contributions claims and evidence,,schema evidence,E1,,governance_support_only,adequate,adequately_supported,answers_gap,low,Structure only,none
CL2,CL1,I1,C1,methods,paragraph_claim,method_claim,The checker validates required links,,script evidence,E1,,governance_support_only,adequate,adequately_supported,justifies_method,low,It does not judge science,none
EOF
    cat > "$tmp/evidence/argument_system_map.csv" <<'EOF'
node_id,parent_node_id,node_type,node_label,linked_gap_id,linked_contribution_id,linked_claim_id,linked_evidence_ids,section_id,status,risk_level,notes
N1,,intent,Argument governance,,,,,intro,active,medium,root
N2,N1,gap,Implicit argument links,G1,,,,intro,active,medium,gap
N3,N2,contribution,Schema,,C1,CL1,E1,methods,active,low,contribution
EOF
    cat > "$tmp/evidence/reviewer_attack_matrix.csv" <<'EOF'
attack_id,target_type,target_id,reviewer_question,attack_category,severity,likely_reviewer_profile,current_defense,evidence_needed,current_evidence_ids,defense_strength,revision_needed,response_strategy,owner,status
A1,contribution,C1,Is this governance rather than validity?,scope_boundary,medium,methods reviewer,Boundary language states structure only,script and schema,E1,adequate,no,Keep limitation explicit,author,open
EOF
}

test_T64() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['edit_contracts'] == 1"
}

test_T65() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,The edit now claims the workflow improves final thesis quality,The boundary moved from one project to all thesis writing,workflow improves final thesis quality,related caution paragraph still says quality is not proven,accept,false,passed
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-human-review','unsafe-accept','unsupported-claim-passed','missed-adjacent-passed'} <= kinds"
}

test_T66() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that author control requires visible edit boundaries before rewriting begins.
The claim is local to this project and does not assert that every thesis workflow needs the same structure.
EOF

    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 3 \
        --end-line 4 \
        --unit-id ch01-control \
        --copy-source \
        --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json > "$tmp/check.json" || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$out" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
check = json.loads((root / "check.json").read_text(encoding="utf-8"))
assert payload["unit_id"] == "ch01-control"
assert check["issue_count"] == 0
assert check["summary"]["drift_audits"] == 0
assert (root / "source_excerpts/ch01-control.md").is_file()
assert Path(payload["review_packet"]).is_file()
contracts = list(csv.DictReader((root / "thesis_control/edit_contracts.csv").open(encoding="utf-8")))
assert contracts[0]["human_approved"] == "false"
assert contracts[0]["status"] == "draft"
assert "AUTHOR_REVIEW_REQUIRED" in contracts[0]["allowed_changes"]
PY
    rm -rf "$tmp"
}

test_T67() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that applied thesis edits require drift audits before acceptance.
EOF
    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-applied \
        --copy-source \
        --json >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp/thesis_control/edit_contracts.csv" <<'PY'
import csv
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open(encoding="utf-8")))
rows[0]["human_approved"] = "true"
rows[0]["status"] = "applied"
with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
PY
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'missing-drift-audit' in kinds"
}

test_T68() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that scaffolded control packets must refer to real prose.
EOF
    : > "$tmp/chapters/empty.md"

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 99 \
        --end-line 99 \
        --unit-id beyond-start >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 1 \
        --end-line 99 \
        --unit-id beyond-end >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/empty.md \
        --unit-id empty-source >/dev/null 2>&1
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -ne 0 ]]
}

test_T69() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that control-packet identifiers must be safe stable ids.
EOF

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ../escape \
        --copy-source >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id safe-unit \
        --contract-id 'bad/id' >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    mkdir -p "$tmp/manual/thesis_control"
    cat > "$tmp/manual/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
../escape,chapters/ch01.md,Unsafe id,This unit has an unsafe id.,single unit only,unsafe id should fail,do not accept path-like ids
EOF
    cat > "$tmp/manual/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
bad/id,../escape,bad/issue,1,local change,clarify prose,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$tmp/manual/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
bad/audit,bad/id,none,none,none,none,accept,false,passed
EOF
    cat > "$tmp/manual/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp/manual" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'invalid-unit-id','invalid-contract-id','invalid-audit-id'} <= kinds"
}

test_T70() {
    local tmp out rc abs_source
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/project/chapters" "$tmp/outside" "$tmp/manual/thesis_control"
    cat > "$tmp/project/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that source paths in control packets must be inspectable.
EOF
    abs_source="$tmp/project/chapters/ch01.md"

    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp/project" \
        --source "$abs_source" \
        --output-dir "$tmp/outside" \
        --unit-id outside-source >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    cat > "$tmp/manual/thesis_control/spine_cards.csv" <<EOF
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
missing,chapters/missing.md,Missing path,This unit points at a missing path.,one unit only,path must exist,do not accept missing paths
absolute,$abs_source,Absolute path,This unit points at an absolute path.,one unit only,path must be relative,do not accept absolute paths
traversal,../outside.md,Traversal path,This unit points outside the packet root.,one unit only,path must stay inside root,do not accept traversal paths
EOF
    cat > "$tmp/manual/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-missing,missing,ri-missing,1,local change,clarify prose,do not broaden,check neighbours,spine preserved,false,draft
ec-absolute,absolute,ri-absolute,1,local change,clarify prose,do not broaden,check neighbours,spine preserved,false,draft
ec-traversal,traversal,ri-traversal,1,local change,clarify prose,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$tmp/manual/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
EOF
    cat > "$tmp/manual/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp/manual" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert sum(1 for i in d['issues'] if i['kind'] == 'invalid-source-path') == 3"
}

test_T71() {
    local tmp repo_root
    tmp=$(mktemp -d) || return 1
    repo_root="$PWD"
    mkdir -p "$tmp/project/chapters"
    cat > "$tmp/project/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that relative output directories should produce valid packets.
EOF
    (
        cd "$tmp" || exit 1
        python3 "$repo_root/archive/skills/thesis-control/scripts/scaffold_thesis_control.py" project \
            --source chapters/ch01.md \
            --output-dir out \
            --unit-id relative-out \
            --copy-source \
            --json >/dev/null &&
        python3 "$repo_root/archive/skills/thesis-control/scripts/check_thesis_control.py" out --strict --json > check.json
    ) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp/check.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert payload["issue_count"] == 0
assert payload["summary"]["spine_cards"] == 1
PY
    rm -rf "$tmp"
}

test_T72() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/thesis_control" "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that every edit contract must remain bound to a spine card.
EOF
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch01,chapters/ch01.md,Contract binding,This unit argues that contracts need spine bindings.,one unit only,contracts must bind to spine cards,do not allow orphan contracts
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-missing,,ri-missing,1,local change,clarify prose,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'missing-unit-id' in kinds"
}

test_T73() {
    local bench="$REPO_ROOT/examples/lost-in-conversation-bench"
    local case

    [[ -f "$bench/README.md" ]] || return 1
    [[ -f "$bench/cases/index.md" ]] || return 1
    [[ -f "$bench/chapters/desensitized_section.md" ]] || return 1
    [[ -f "$bench/requirements/multi_turn_requirements.md" ]] || return 1
    [[ -f "$bench/requirements/consolidated_prompt.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_a_edited_section.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_a_review.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_b_edited_section.md" ]] || return 1
    [[ -f "$bench/baselines/baseline_b_review.md" ]] || return 1
    [[ -f "$bench/comparison_report.md" ]] || return 1
    [[ -f "$bench/treatment/source_excerpts/lost-conversation-section.md" ]] || return 1
    [[ -f "$bench/treatment/edited_section.md" ]] || return 1
    [[ -f "$bench/treatment/review_report.md" ]] || return 1

    python3 scripts/check_lost_in_conversation_bench.py "$bench" >/dev/null || return 1
    for case in \
        "$bench" \
        "$bench/cases/method-limitation-boundary" \
        "$bench/cases/evidence-boundary-literature"
    do
        python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$case/treatment" --strict >/dev/null || return 1
    done
}

test_T74() {
    python3 - "$REPO_ROOT/archive/skills/thesis-control/SKILL.md" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
start = text.index("## Revision Escalation Rule")
end = text.index("\n## Output Patterns", start)
section = text[start:end]
required_clauses = (
    "same revision issue",
    "revision_issue_id",
    "three unsuccessful attempts",
    "operational escalation threshold",
    "Only count an attempt when its drift decision is `revise` or `rollback` and its audit status is `failed`.",
    "Only applied contracts count as unsuccessful attempts.",
    "Clarifying discussion, pending human reviews, and unexecuted proposals do not count.",
    "Do not apply a fourth prose patch",
    "Only an escalation whose trigger set exactly matches one completed group of three unsuccessful contracts may close that group.",
    "One escalation cannot close more than one group.",
    "An earlier escalation with fewer than three trigger contracts does not close or pre-authorise a later completed group.",
    "Escalate earlier",
    "section spine cannot be stated consistently",
    "requested claim lacks supporting evidence",
    "claim, caveat, or scope boundary outside the contract",
    "latest author-approved version cannot be identified",
    "conflicting requirements indicate version contamination",
    "spine card, evidence boundaries, current contract, and latest author-approved version",
    "underspecified or conflicting intent",
    "local execution failure",
    "structural mismatch",
    "evidence gap",
    "version contamination",
    "latest author-approved version",
    "local patch",
    "section-level restructure",
    "full reframing",
    "Create a separate branch or manuscript version only when the approved scope requires structural work.",
    "revision_escalations.csv",
)
missing = [phrase for phrase in required_clauses if phrase not in section]
if missing:
    raise SystemExit("missing revision-escalation guidance: " + ", ".join(missing))
PY
}

_make_revision_escalation_packet() {
    local tmp="$1"
    local escalation_mode="${2:-none}"
    mkdir -p "$tmp/thesis_control" "$tmp/chapters"
    cat > "$tmp/chapters/ch03.md" <<'EOF'
# Chapter 3

This section argues that repeated revisions need a durable stop-and-diagnose gate.
EOF
    _write_valid_project_intent_layer "$tmp"
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,manuscript_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch03,mc-project-001,chapters/ch03.md,Revision control,This unit argues that repeated revisions need a durable escalation gate.,one section only,revision attempts require a stop gate,do not broaden beyond revision control
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,global_audit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ga-project-001,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-002,ch03,ga-project-001,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-003,ch03,ga-project-001,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-004,ch03,ga-project-001,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,true,failed
da-002,ec-002,none,none,none,none,rollback,true,failed
da-003,ec-003,none,none,none,none,revise,true,failed
da-004,ec-004,none,none,none,none,accept,false,passed
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
EOF
    if [[ "$escalation_mode" == "approved" ]]; then
        cat >> "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003,3,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF
    fi
}

test_T75() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-revision-escalation','revision-escalation-required'} <= kinds"
}

test_T76() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['revision_escalations'] == 1"
}

test_T77() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-002,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-003,ch03,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-004,ch03,ri-ch03-clarity,5,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-unknown,3,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'duplicate-revision-attempt','nonsequential-revision-attempt','unknown-trigger-contract'} <= kinds"
}

test_T78() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that scaffolded attempts need stable revision identities.
EOF
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-control \
        --revision-issue-id ri-ch01-clarity \
        --attempt-no 1 \
        --copy-source \
        --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$out" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
contracts = list(csv.DictReader((root / "thesis_control/edit_contracts.csv").open(encoding="utf-8")))
assert contracts[0]["revision_issue_id"] == "ri-ch01-clarity"
assert contracts[0]["attempt_no"] == "1"
assert Path(payload["revision_escalations"]).is_file()
with (root / "thesis_control/revision_escalations.csv").open(encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    assert "trigger_contracts" in (reader.fieldnames or [])
    assert list(reader) == []
PY
    rm -rf "$tmp"
}

test_T79() {
    local tmp out second
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters" "$tmp/thesis_control"
    printf '# Chapter 1\n\nLegacy applied contract.\n' > "$tmp/chapters/ch01.md"
    printf '# Chapter 2\n\nLegacy draft contract.\n' > "$tmp/chapters/ch02.md"
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch01,chapters/ch01.md,Chapter 1,Keep the first argument stable,one chapter,one claim,do not broaden
ch02,chapters/ch02.md,Chapter 2,Keep the second argument stable,one chapter,one claim,do not broaden
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-legacy-001,ch01,clarify prose,improve clarity,do not broaden,check neighbours,spine preserved,true,applied
ec-legacy-002,ch02,clarify prose,improve clarity,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-legacy-001,ec-legacy-001,none,none,none,none,accept,false,passed
EOF
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    second=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$out" "$second" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
second = json.loads(sys.argv[3])
rows = list(csv.DictReader((root / "thesis_control/edit_contracts.csv").open(encoding="utf-8")))
assert payload["contracts_upgraded"] == 2
assert second["contracts_upgraded"] == 0
assert second["escalation_file"] == "unchanged"
assert [row["attempt_no"] for row in rows] == ["1", "1"]
assert rows[0]["revision_issue_id"] != rows[1]["revision_issue_id"]
assert (root / "thesis_control/revision_escalations.csv").is_file()
PY
    rm -rf "$tmp"
}

test_T80() {
    local fixture blocked approved rc
    fixture="$REPO_ROOT/examples/thesis-control-revision-escalation"
    blocked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$fixture/blocked" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || return 1
    echo "$blocked" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-revision-escalation','revision-escalation-required'} <= kinds" || return 1

    approved=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$fixture/approved" --strict --json) || return 1
    echo "$approved" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['revision_escalations'] == 1"
}

test_T81() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-002,ch03,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-003,ch03,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-004,ch03,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-005,ch03,ri-ch03-clarity,5,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-006,ch03,ri-ch03-clarity,6,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-007,ch03,ri-ch03-clarity,7,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,true,failed
da-002,ec-002,none,none,none,none,rollback,true,failed
da-003,ec-003,none,none,none,none,revise,true,failed
da-004,ec-004,none,none,none,none,revise,true,failed
da-005,ec-005,none,none,none,none,rollback,true,failed
da-006,ec-006,none,none,none,none,revise,true,failed
da-007,ec-007,none,none,none,none,accept,false,passed
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); messages=' '.join(i['message'] for i in d['issues']); assert 'ec-004, ec-005, ec-006' in messages and any(i['kind'] == 'revision-escalation-required' for i in d['issues'])"
}

test_T82() {
    local tmp legacy strict rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters" "$tmp/thesis_control"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This legacy packet predates revision tracking but remains structurally inspectable.
EOF
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch01,chapters/ch01.md,Legacy packet,This unit records a legacy control packet.,one unit only,legacy packets remain readable,do not infer revision families
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-legacy,ch01,clarify prose,improve clarity,do not broaden,check neighbours,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-legacy,ec-legacy,none,none,none,none,accept,false,passed
EOF

    legacy=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    echo "$legacy" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['revision_tracking'] is False" || {
        rm -rf "$tmp"
        return 1
    }

    strict=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$strict" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-column','missing-file'} <= kinds"
}

test_T83() {
    local tmp pending resolved rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,accept,false,needs_review
EOF

    pending=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || {
        rm -rf "$tmp"
        return 1
    }
    echo "$pending" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'pending-human-review' for i in d['issues'])" || {
        rm -rf "$tmp"
        return 1
    }

    sed -i.bak 's/,needs_review$/,passed/' "$tmp/thesis_control/drift_audits.csv"
    resolved=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$resolved" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0"
}

test_T84() {
    local tmp pending failed rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    sed -i.bak '/^da-003,/ s/,failed$/,needs_review/' "$tmp/thesis_control/drift_audits.csv"

    pending=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || {
        rm -rf "$tmp"
        return 1
    }
    echo "$pending" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'pending-human-review' in kinds and 'missing-revision-escalation' not in kinds and 'revision-escalation-required' not in kinds" || {
        rm -rf "$tmp"
        return 1
    }

    sed -i.bak '/^da-003,/ s/,needs_review$/,failed/' "$tmp/thesis_control/drift_audits.csv"
    failed=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$failed" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-revision-escalation','revision-escalation-required'} <= kinds"
}

test_T85() {
    local tmp mismatch rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"

    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,false,passed
EOF
    mismatch=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || {
        rm -rf "$tmp"
        return 1
    }
    echo "$mismatch" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'invalid-audit-outcome' for i in d['issues'])" || {
        rm -rf "$tmp"
        return 1
    }

    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,accept,false,failed
EOF
    mismatch=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$mismatch" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'invalid-audit-outcome' for i in d['issues'])"
}

test_T86() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-002,ch03,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-003,ch03,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-004,ch03,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-005,ch03,ri-ch03-clarity,5,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-006,ch03,ri-ch03-clarity,6,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-007,ch03,ri-ch03-clarity,7,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,true,failed
da-002,ec-002,none,none,none,none,rollback,true,failed
da-003,ec-003,none,none,none,none,revise,true,failed
da-004,ec-004,none,none,none,none,revise,true,failed
da-005,ec-005,none,none,none,none,rollback,true,failed
da-006,ec-006,none,none,none,none,revise,true,failed
da-007,ec-007,none,none,none,none,accept,false,passed
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-all-six,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003;ec-004;ec-005;ec-006,6,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); messages=' '.join(i['message'] for i in d['issues']); kinds={i['kind'] for i in d['issues']}; assert 'ec-004, ec-005, ec-006' in messages and 'revision-escalation-required' in kinds"
}

test_T87() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,global_audit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ga-project-001,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,false,draft
ec-002,ch03,ga-project-001,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,approved
ec-003,ch03,ga-project-001,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,false,rejected
ec-004,ch03,ga-project-001,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,false,failed
da-002,ec-002,none,none,none,none,rollback,false,failed
da-003,ec-003,none,none,none,none,revise,false,failed
da-004,ec-004,none,none,none,none,accept,false,passed
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0"
}

test_T88() {
    local tmp invalid first second duplicate checked rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/chapters/ch01.md" <<'EOF'
# Chapter 1

This section argues that scaffolded revision attempts must remain sequential.
EOF

    invalid=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-control \
        --contract-id ec-ch01-002 \
        --revision-issue-id ri-ch01-clarity \
        --attempt-no 2 \
        --copy-source \
        --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 && ! -e "$tmp/thesis_control" && ! -e "$tmp/source_excerpts" ]] || {
        rm -rf "$tmp"
        return 1
    }
    [[ "$invalid" == *"unique and sequential from 1"* ]] || {
        rm -rf "$tmp"
        return 1
    }

    first=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-control \
        --contract-id ec-ch01-001 \
        --revision-issue-id ri-ch01-clarity \
        --attempt-no 1 \
        --copy-source \
        --json) || {
        rm -rf "$tmp"
        return 1
    }
    second=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-control \
        --contract-id ec-ch01-002 \
        --revision-issue-id ri-ch01-clarity \
        --attempt-no 2 \
        --copy-source \
        --force \
        --json) || {
        rm -rf "$tmp"
        return 1
    }

    duplicate=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ch01-control \
        --contract-id ec-ch01-003 \
        --revision-issue-id ri-ch01-clarity \
        --attempt-no 2 \
        --copy-source \
        --force \
        --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 && "$duplicate" == *"unique and sequential from 1"* ]] || {
        rm -rf "$tmp"
        return 1
    }

    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$first" "$second" "$checked" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
first = json.loads(sys.argv[2])
second = json.loads(sys.argv[3])
checked = json.loads(sys.argv[4])
rows = list(csv.DictReader((root / "thesis_control/edit_contracts.csv").open(encoding="utf-8")))
assert first["attempt_no"] == 1
assert second["attempt_no"] == 2
assert [row["attempt_no"] for row in rows] == ["1", "2"]
assert checked["issue_count"] == 0
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T89() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003;ec-003,3,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'duplicate-trigger-contract' for i in d['issues'])"
}

test_T90() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    cat >> "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
re-002,ri-ch03-clarity,cycle_gate,ec-003;ec-001;ec-002,3,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'duplicate-escalation-trigger-set' for i in d['issues'])"
}

test_T91() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"

    python3 - "$tmp" <<'PY'
import csv
import sys
from pathlib import Path

control = Path(sys.argv[1]) / "thesis_control"
cases = (
    ("spine_cards.csv", "unit_id", None, None),
    ("edit_contracts.csv", "human_approved", "false", "true"),
    ("drift_audits.csv", "status", None, None),
    ("revision_escalations.csv", "human_approved", None, None),
)
for filename, duplicate, first_value, second_value in cases:
    path = control / filename
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    header = rows[0]
    source_index = header.index(duplicate)
    header.append(duplicate)
    for row in rows[1:]:
        if first_value is not None:
            row[source_index] = first_value
        row.append(second_value if second_value is not None else row[source_index])
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)
PY

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); duplicates=[i for i in d['issues'] if i['kind']=='duplicate-column']; assert len(duplicates)==4"
}

test_T92() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp/base"

    python3 - "$tmp" "$REPO_ROOT/archive/skills/thesis-control/scripts/check_thesis_control.py" <<'PY'
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
checker = Path(sys.argv[2])
base = root / "base"

cases = {}

extra = root / "extra-cell"
shutil.copytree(base, extra)
path = extra / "thesis_control/spine_cards.csv"
lines = path.read_text(encoding="utf-8").splitlines()
lines[1] += ",EXTRA"
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
cases[extra] = "row-width-mismatch"

missing = root / "missing-cell"
shutil.copytree(base, missing)
path = missing / "thesis_control/edit_contracts.csv"
with path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.reader(handle))
rows[1] = rows[1][:-1]
with path.open("w", newline="", encoding="utf-8") as handle:
    csv.writer(handle).writerows(rows)
cases[missing] = "row-width-mismatch"

truncated = root / "truncated-row"
shutil.copytree(base, truncated)
path = truncated / "thesis_control/drift_audits.csv"
header = path.read_text(encoding="utf-8").splitlines()[0]
path.write_text(header + "\nda-001,ec-001\n", encoding="utf-8")
cases[truncated] = "row-width-mismatch"

invalid_quote = root / "invalid-quote"
shutil.copytree(base, invalid_quote)
path = invalid_quote / "thesis_control/revision_escalations.csv"
header = path.read_text(encoding="utf-8").splitlines()[0]
path.write_text(header + '\n"unterminated,ri-ch02-traceability\n', encoding="utf-8")
cases[invalid_quote] = "csv-parse-error"

for case, expected_kind in cases.items():
    result = subprocess.run(
        [sys.executable, str(checker), str(case), "--strict", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1, (case.name, result.returncode, result.stdout, result.stderr)
    assert "Traceback" not in result.stderr, (case.name, result.stderr)
    payload = json.loads(result.stdout)
    kinds = {issue["kind"] for issue in payload["issues"]}
    assert expected_kind in kinds, (case.name, expected_kind, kinds)
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T93() {
    local tmp legacy strict rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,trigger_contracts,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-001,ri-ch03-clarity,ec-001;ec-002;ec-003,local_execution_failure,local_patch,preserve the section spine and improve clarity,previous edits did not meet the clarity acceptance check,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF

    legacy=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    echo "$legacy" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count']==0" || {
        rm -rf "$tmp"
        return 1
    }

    strict=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$strict" | python3 -c "import json,sys; d=json.load(sys.stdin); missing={i['message'] for i in d['issues'] if i['kind']=='missing-column'}; assert any('escalation_kind' in m for m in missing) and any('approved_after_attempt' in m for m in missing)"
}

test_T94() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    sed -i.bak '/^ec-004,/ s/,true,applied$/,false,draft/' "$tmp/thesis_control/edit_contracts.csv"
    sed -i.bak '/^da-003,/ s/,revise,true,failed$/,accept,false,passed/' "$tmp/thesis_control/drift_audits.csv"
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003,3,local_execution_failure,local_patch,preserve the section spine and improve clarity,third attempt has not failed,chapters/ch03.md before ec-001,apply one consolidated contract,true,approved
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='premature-cycle-gate-approval' for i in d['issues'])"
}

test_T95() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp"
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-early,ri-ch03-clarity,early_diagnostic,ec-001;ec-002;ec-003,,local_execution_failure,local_patch,preserve the section spine and improve clarity,diagnosis began before the completed group,chapters/ch03.md before ec-001,inspect the issue before another edit,true,approved
EOF

    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'invalid-early-diagnostic-trigger-count','revision-escalation-required'} <= kinds"
}

test_T96() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp/base"

    python3 - "$tmp" "$REPO_ROOT/archive/skills/thesis-control/scripts/check_thesis_control.py" <<'PY'
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
checker = Path(sys.argv[2])
base = root / "base"
header = "escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status\n"
tail = ",local_execution_failure,local_patch,preserve the section spine,previous edits failed,chapters/ch03.md before ec-001,apply one bounded contract,true,approved\n"

cases = {
    "wrong-boundary": (
        "re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003,2" + tail,
        "invalid-approved-after-attempt",
    ),
    "oversized": (
        "re-001,ri-ch03-clarity,cycle_gate,ec-001;ec-002;ec-003;ec-004,4" + tail,
        "invalid-cycle-gate-trigger-count",
    ),
}

for name, (row, expected_kind) in cases.items():
    case = root / name
    shutil.copytree(base, case)
    (case / "thesis_control/revision_escalations.csv").write_text(header + row, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(checker), str(case), "--strict", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1, (name, result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    kinds = {issue["kind"] for issue in payload["issues"]}
    assert expected_kind in kinds, (name, expected_kind, kinds)
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

_tree_digest() {
    python3 - "$1" <<'PY'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
if root.exists():
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(str(stat.S_IMODE(mode)).encode("ascii") + b"\0")
        if path.is_symlink():
            digest.update(b"L" + os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"F" + path.read_bytes())
        elif path.is_dir():
            digest.update(b"D")
print(digest.hexdigest())
PY
}

test_T97() {
    local tmp before after out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters" "$tmp/thesis_control" "$tmp/source_excerpts"
    printf '# Chapter\n\nnew source\n' > "$tmp/chapters/ch.md"
    printf 'KEEP ORIGINAL\n' > "$tmp/source_excerpts/ch.md"
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,bad_column
EOF

    before=$(_tree_digest "$tmp") || {
        rm -rf "$tmp"
        return 1
    }
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md \
        --unit-id ch \
        --revision-issue-id ri-ch \
        --attempt-no 1 \
        --copy-source \
        --force \
        --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" ]] || return 1
    [[ "$out" == *"missing column"* ]]
}

test_T98() {
    local tmp case_dir before after rc
    tmp=$(mktemp -d) || return 1

    case_dir="$tmp/review-collision"
    mkdir -p "$case_dir/chapters" "$case_dir/thesis_control"
    printf '# Chapter\n\nsource\n' > "$case_dir/chapters/ch.md"
    printf 'KEEP PACKET\n' > "$case_dir/thesis_control/ch_review_packet.md"
    before=$(_tree_digest "$case_dir") || return 1
    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$case_dir" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --copy-source --json >/dev/null 2>&1
    rc=$?
    after=$(_tree_digest "$case_dir")
    [[ "$rc" -eq 1 && "$before" == "$after" ]] || {
        rm -rf "$tmp"
        return 1
    }

    case_dir="$tmp/spine-collision"
    mkdir -p "$case_dir/chapters" "$case_dir/thesis_control"
    printf '# Chapter\n\nsource\n' > "$case_dir/chapters/ch.md"
    cat > "$case_dir/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch,chapters/ch.md,Chapter,existing spine,one unit,claim,boundary
EOF
    before=$(_tree_digest "$case_dir") || return 1
    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$case_dir" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --copy-source --json >/dev/null 2>&1
    rc=$?
    after=$(_tree_digest "$case_dir")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" ]]
}

test_T99() {
    local tmp first second checked
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    printf '# Chapter\n\nsource\n' > "$tmp/chapters/ch.md"

    first=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --attempt-no 1 --copy-source --json) || {
        rm -rf "$tmp"
        return 1
    }
    second=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --attempt-no 2 --copy-source --force --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$first" "$second" "$checked" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
first = json.loads(sys.argv[2])
second = json.loads(sys.argv[3])
checked = json.loads(sys.argv[4])
rows = list(csv.DictReader((root / "thesis_control/edit_contracts.csv").open(encoding="utf-8")))
assert first["contract_id"] == "ec-ch-001"
assert second["contract_id"] == "ec-ch-002"
assert [(row["contract_id"], row["attempt_no"]) for row in rows] == [
    ("ec-ch-001", "1"),
    ("ec-ch-002", "2"),
]
assert checked["issue_count"] == 0
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T100() {
    local tmp before after out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters" "$tmp/thesis_control"
    printf '# Chapter\n\nsource\n' > "$tmp/chapters/ch.md"
    _write_valid_project_intent_layer "$tmp"
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,manuscript_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,global_audit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status,owner_note
ec-a-001,a,ga-project-001,ri-a,1,scope,allowed,forbidden,adjacent,checks,false,draft,keep-a
ec-b-001,b,ga-project-001,ri-b,1,scope,allowed,forbidden,adjacent,checks,false,draft,keep-b
EOF
    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --attempt-no 1 --copy-source --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" ]] || return 1
    [[ "$out" == *"unsupported column"*"owner_note"* ]]
}

_make_migration_v2_packet() {
    local root="$1"
    mkdir -p "$root/chapters" "$root/thesis_control"
    printf '# Chapter\n\nBounded migration fixture.\n' > "$root/chapters/ch.md"
    _write_valid_project_intent_layer "$root"
    cat > "$root/thesis_control/spine_cards.csv" <<'EOF'
unit_id,manuscript_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch,mc-project-001,chapters/ch.md,Chapter,Preserve the bounded claim,one section,one claim,do not broaden
EOF
    cat > "$root/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,global_audit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch,ga-project-001,ri-ch-clarity,1,clarify,improve wording,do not broaden,check neighbours,spine preserved,true,applied
ec-002,ch,ga-project-001,ri-ch-clarity,2,clarify,improve wording,do not broaden,check neighbours,spine preserved,true,applied
ec-003,ch,ga-project-001,ri-ch-clarity,3,clarify,improve wording,do not broaden,check neighbours,spine preserved,true,applied
ec-004,ch,ga-project-001,ri-ch-clarity,4,clarify,improve wording,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$root/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,revise,true,failed
da-002,ec-002,none,none,none,none,rollback,true,failed
da-003,ec-003,none,none,none,none,revise,true,failed
EOF
}

_write_valid_cycle_gate() {
    local root="$1"
    cat > "$root/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-cycle,ri-ch-clarity,cycle_gate,ec-001;ec-002;ec-003,3,local_execution_failure,local_patch,preserve the spine,three attempts did not converge,chapters/ch.md before ec-001,apply one bounded contract,true,approved
EOF
}

test_T101() {
    local tmp before after out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters" "$tmp/thesis_control"
    printf '# Chapter\n\nLegacy source.\n' > "$tmp/chapters/ch.md"
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch,chapters/ch.md,Chapter,Preserve the claim,one section,one claim,do not broaden
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-legacy,ch,clarify,improve wording,do not broaden,check neighbours,spine preserved,false,draft
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,trigger_contracts,human_approved,human_approved,status
re-bad,ri-legacy,ec-legacy,false,true,draft
EOF

    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" ]] || return 1
    [[ "$out" == *"duplicate column"* ]]
}

test_T102() {
    local tmp case_dir before after out rc
    tmp=$(mktemp -d) || return 1

    case_dir="$tmp/partial-header"
    mkdir -p "$case_dir/chapters" "$case_dir/thesis_control"
    printf '# Chapter\n\nSource.\n' > "$case_dir/chapters/ch.md"
    cat > "$case_dir/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch,ri-ch,clarify,improve wording,do not broaden,check neighbours,spine preserved,false,draft
EOF
    before=$(_tree_digest "$case_dir") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$case_dir")
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"author decision"* ]] || {
        rm -rf "$tmp"
        return 1
    }

    case_dir="$tmp/partial-value"
    _make_migration_v2_packet "$case_dir"
    sed -i.bak '/^ec-002,/ s/,2,/, ,/' "$case_dir/thesis_control/edit_contracts.csv"
    rm -f "$case_dir/thesis_control/edit_contracts.csv.bak"
    before=$(_tree_digest "$case_dir") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$case_dir")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"author decision"* ]]
}

test_T103() {
    local tmp out checked
    tmp=$(mktemp -d) || return 1
    _make_migration_v2_packet "$tmp"
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,trigger_contracts,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status,decision_note
re-early,ri-ch-clarity,ec-001;ec-002,local_execution_failure,local_patch,preserve the spine,earlier wording did not converge,chapters/ch.md before ec-001,diagnose before retry,true,approved,keep-early
re-cycle,ri-ch-clarity,ec-001;ec-002;ec-003,local_execution_failure,local_patch,preserve the spine,three attempts did not converge,chapters/ch.md before ec-001,apply one bounded contract,true,approved,keep-cycle
EOF

    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$out" "$checked" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
checked = json.loads(sys.argv[3])
path = root / "thesis_control/revision_escalations.csv"
with path.open(encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
assert payload["schema_version"] == 3
assert payload["escalation_file"] == "upgraded"
assert checked["issue_count"] == 0
assert [(row["escalation_kind"], row["approved_after_attempt"]) for row in rows] == [
    ("early_diagnostic", ""),
    ("cycle_gate", "3"),
]
assert [row["decision_note"] for row in rows] == ["keep-early", "keep-cycle"]
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T104() {
    local tmp base case_dir before after out rc
    tmp=$(mktemp -d) || return 1
    base="$tmp/base"
    _make_migration_v2_packet "$base"

    for case_name in oversized incomplete cross_issue; do
        case_dir="$tmp/$case_name"
        cp -R "$base" "$case_dir"
        case "$case_name" in
            oversized)
                triggers='ec-001;ec-002;ec-003;ec-004'
                ;;
            incomplete)
                triggers='ec-001;ec-002;ec-003'
                sed -i.bak '/^da-003,/ s/,failed$/,needs_review/' "$case_dir/thesis_control/drift_audits.csv"
                rm -f "$case_dir/thesis_control/drift_audits.csv.bak"
                ;;
            cross_issue)
                triggers='ec-001;ec-004'
                sed -i.bak '/^ec-004,/ s/ri-ch-clarity,4/ri-other,1/' "$case_dir/thesis_control/edit_contracts.csv"
                rm -f "$case_dir/thesis_control/edit_contracts.csv.bak"
                ;;
        esac
        cat > "$case_dir/thesis_control/revision_escalations.csv" <<EOF
escalation_id,revision_issue_id,trigger_contracts,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-bad,ri-ch-clarity,$triggers,local_execution_failure,local_patch,preserve the spine,revisions did not converge,chapters/ch.md before ec-001,diagnose before retry,true,approved
EOF
        before=$(_tree_digest "$case_dir") || return 1
        out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
        rc=$?
        after=$(_tree_digest "$case_dir")
        [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"ambiguous"* ]] || {
            rm -rf "$tmp"
            return 1
        }
    done
    rm -rf "$tmp"
}

test_T105() {
    local tmp first second before after_first after_second checked
    tmp=$(mktemp -d) || return 1
    _make_migration_v2_packet "$tmp"
    python3 - "$tmp" <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "thesis_control"
contract_path = root / "edit_contracts.csv"
with contract_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
columns = list(rows[0]) + ["owner_note"]
for index, row in enumerate(rows, start=1):
    row["owner_note"] = f"keep-{index}"
with contract_path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

(root / "revision_escalations.csv").write_text(
    "escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status,coordinator_note\n"
    "re-cycle,ri-ch-clarity,cycle_gate,ec-001;ec-002;ec-003,3,local_execution_failure,local_patch,preserve the spine,three attempts did not converge,chapters/ch.md before ec-001,apply one bounded contract,true,approved,keep-gate\n",
    encoding="utf-8",
)
PY
    before=$(_tree_digest "$tmp") || return 1
    first=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after_first=$(_tree_digest "$tmp")
    second=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after_second=$(_tree_digest "$tmp")
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$first" "$second" "$checked" "$before" "$after_first" "$after_second" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
first = json.loads(sys.argv[2])
second = json.loads(sys.argv[3])
checked = json.loads(sys.argv[4])
with (root / "thesis_control/edit_contracts.csv").open(encoding="utf-8") as handle:
    contracts = list(csv.DictReader(handle))
with (root / "thesis_control/revision_escalations.csv").open(encoding="utf-8") as handle:
    escalations = list(csv.DictReader(handle))
assert sys.argv[5] == sys.argv[6] == sys.argv[7]
assert first["contracts_upgraded"] == second["contracts_upgraded"] == 0
assert first["escalation_file"] == second["escalation_file"] == "unchanged"
assert [row["owner_note"] for row in contracts] == ["keep-1", "keep-2", "keep-3", "keep-4"]
assert escalations[0]["coordinator_note"] == "keep-gate"
assert checked["issue_count"] == 0
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T106() {
    local tmp conflict duplicate out checked rc
    tmp=$(mktemp -d) || return 1

    conflict="$tmp/conflict"
    _make_migration_v2_packet "$conflict"
    _write_valid_cycle_gate "$conflict"
    printf 'da-004,ec-001,none,none,none,none,accept,false,passed\n' >> "$conflict/thesis_control/drift_audits.csv"
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$conflict" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || {
        rm -rf "$tmp"
        return 1
    }
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind'] == 'conflicting-resolved-audits' for i in d['issues'])" || {
        rm -rf "$tmp"
        return 1
    }

    duplicate="$tmp/duplicate-failure"
    _make_migration_v2_packet "$duplicate"
    _write_valid_cycle_gate "$duplicate"
    printf 'da-004,ec-001,none,none,none,none,rollback,true,failed\n' >> "$duplicate/thesis_control/drift_audits.csv"
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$duplicate" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$checked" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0"
}

test_T107() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_migration_v2_packet "$tmp"
    sed -i.bak '/^ec-004,/ s/,false,draft$/,true,approved/' "$tmp/thesis_control/edit_contracts.csv"
    rm -f "$tmp/thesis_control/edit_contracts.csv.bak"
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
re-cycle,ri-ch-clarity,cycle_gate,ec-003;ec-001;ec-002,3,local_execution_failure,local_patch,preserve the spine,three attempts did not converge,chapters/ch.md before ec-001,apply one bounded contract,true,approved
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'misordered-cycle-gate-triggers','revision-escalation-required'} <= kinds"
}

test_T108() {
    local tmp before after out rc
    tmp=$(mktemp -d) || return 1
    _make_migration_v2_packet "$tmp"
    _write_valid_cycle_gate "$tmp"
    printf 'da-001,ec-002,none,none,none,none,rollback,true,failed\n' >> "$tmp/thesis_control/drift_audits.csv"
    printf '# New unit\n\nNew bounded source.\n' > "$tmp/chapters/new.md"
    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/new.md --unit-id new --revision-issue-id ri-new \
        --copy-source --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" ]] || return 1
    [[ "$out" == *"duplicate-audit-id"* ]]
}

test_T109() {
    local tmp project outside before after out rc
    tmp=$(mktemp -d) || return 1

    project="$tmp/scaffold-project"
    outside="$tmp/scaffold-outside"
    mkdir -p "$project/chapters" "$outside"
    printf '# Chapter\n\nSource.\n' > "$project/chapters/ch.md"
    ln -s "$outside" "$project/thesis_control"
    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$project" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --copy-source --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"symlink"* ]] || {
        rm -rf "$tmp"
        return 1
    }

    project="$tmp/migration-project"
    outside="$tmp/migration-outside"
    _make_migration_v2_packet "$project"
    mv "$project/thesis_control" "$outside"
    ln -s "$outside" "$project/thesis_control"
    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$project" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"symlink"* ]]
}

test_T110() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" "$REPO_ROOT/archive/skills/thesis-control/scripts" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
import thesis_control_io as control_io

first = root / "a.csv"
second = root / "b.csv"
first.write_bytes(b"old-a\n")
second.write_bytes(b"old-b\n")
real_replace = control_io.os.replace
failed = False

def flaky_replace(source, target):
    global failed
    if Path(target) == second and not failed:
        failed = True
        raise OSError("injected replace failure")
    return real_replace(source, target)

control_io.os.replace = flaky_replace
try:
    control_io.atomic_write_batch({first: b"new-a\n", second: b"new-b\n"})
except OSError as exc:
    assert "injected replace failure" in str(exc)
else:
    raise AssertionError("atomic_write_batch unexpectedly succeeded")
finally:
    control_io.os.replace = real_replace

assert first.read_bytes() == b"old-a\n"
assert second.read_bytes() == b"old-b\n"
assert sorted(path.name for path in root.iterdir()) == ["a.csv", "b.csv"]

real_stage = control_io._stage_bytes
stage_calls = 0

def flaky_stage(path, content, mode):
    global stage_calls
    stage_calls += 1
    if stage_calls == 2:
        raise PermissionError("injected staging permission failure")
    return real_stage(path, content, mode)

control_io._stage_bytes = flaky_stage
try:
    control_io.atomic_write_batch({first: b"stage-a\n", second: b"stage-b\n"})
except PermissionError as exc:
    assert "injected staging permission failure" in str(exc)
else:
    raise AssertionError("atomic_write_batch unexpectedly staged every target")
finally:
    control_io._stage_bytes = real_stage

assert first.read_bytes() == b"old-a\n"
assert second.read_bytes() == b"old-b\n"
assert sorted(path.name for path in root.iterdir()) == ["a.csv", "b.csv"]

packet = root / "packet"
(packet / "thesis_control").mkdir(parents=True)
(packet / "thesis_control/spine_cards.csv").write_bytes(b"\xff\xfe")
for name, header in {
    "edit_contracts.csv": "contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status\n",
    "drift_audits.csv": "audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status\n",
    "revision_escalations.csv": "escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status\n",
}.items():
    (packet / "thesis_control" / name).write_text(header, encoding="utf-8")
checker = Path(sys.argv[2]) / "check_thesis_control.py"
result = subprocess.run(
    [sys.executable, str(checker), str(packet), "--strict", "--json"],
    text=True,
    capture_output=True,
    check=False,
)
assert result.returncode == 1, (result.stdout, result.stderr)
assert "Traceback" not in result.stdout + result.stderr
payload = json.loads(result.stdout)
assert any(issue["kind"] == "csv-decode-error" for issue in payload["issues"])
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T111() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_migration_v2_packet "$tmp"
    _write_valid_cycle_gate "$tmp"
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-empty-decision,ec-001,none,none,none,none,,true,failed
da-empty-status,ec-002,none,none,none,none,revise,true,
da-invalid-both,ec-003,none,none,none,none,maybe,true,done
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$out" != *"Traceback"* ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; locations={i['location'] for i in d['issues']}; assert {'invalid-drift-decision','invalid-audit-status'} <= kinds; assert 'thesis_control/drift_audits.csv:row 2' in locations and 'thesis_control/drift_audits.csv:row 3' in locations"
}

test_T116() {
    local fixture blocked aligned rc
    fixture="$REPO_ROOT/examples/project-intent-drift-gate"
    blocked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$fixture/blocked" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || return 1
    echo "$blocked" | python3 -c "import json,sys; d=json.load(sys.stdin); assert {i['kind'] for i in d['issues']} == {'global-thesis-gate-required'}" || return 1

    aligned=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$fixture/aligned" --strict --json) || return 1
    echo "$aligned" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['project_intent_tracking'] is True"
}

test_T117() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    cp -R "$REPO_ROOT/examples/project-intent-drift-gate/blocked/." "$tmp" || return 1
    cat > "$tmp/thesis_control/global_thesis_audits.csv" <<'EOF'
global_audit_id,intent_id,manuscript_id,manuscript_version,title_alignment,abstract_alignment,primary_domain_alignment,research_object_alignment,research_question_alignment,contribution_alignment,structure_alignment,detected_reframe,reframe_summary,human_review_required,human_decision,status
ga-heritage-001,pi-heritage-001,mc-heritage-001,1,drifted,drifted,drifted,drifted,drifted,drifted,drifted,true,visual heritage moved from the primary research domain to a stress-test example,false,accept,passed
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-global-human-review','unsafe-global-pass','invalid-global-pass','global-thesis-gate-required'} <= kinds"
}

test_T118() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    rm -f \
        "$tmp/thesis_control/project_intent.csv" \
        "$tmp/thesis_control/manuscript_contracts.csv" \
        "$tmp/thesis_control/global_thesis_audits.csv"
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); missing={i['message'] for i in d['issues'] if i['kind']=='missing-file'}; assert {'missing project_intent.csv','missing manuscript_contracts.csv','missing global_thesis_audits.csv'} <= missing"
}

test_T119() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    cat >> "$tmp/thesis_control/project_intent.csv" <<'EOF'
pi-project-002,2,,general AI tooling,tool adoption across disciplines,How are general AI tools adopted?,general technology readers,tool adoption,do not retain the original research object,unrecorded reframe,author approval claimed,true,active
EOF
    out=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'multiple-active-intents','missing-intent-amendment','active-project-intent-required'} <= kinds"
}

test_T120() {
    local tmp out checked
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    printf '# Chapter\n\nBounded source.\n' > "$tmp/chapters/ch.md"
    out=$(python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/ch.md --copy-source --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$out" "$checked" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
payload = json.loads(sys.argv[2])
checked = json.loads(sys.argv[3])
intent = next(csv.DictReader((root / "thesis_control/project_intent.csv").open(encoding="utf-8")))
manuscript = next(csv.DictReader((root / "thesis_control/manuscript_contracts.csv").open(encoding="utf-8")))
audit = next(csv.DictReader((root / "thesis_control/global_thesis_audits.csv").open(encoding="utf-8")))
assert payload["schema_version"] == 4
assert checked["issue_count"] == 0
assert (intent["status"], intent["human_approved"]) == ("draft", "false")
assert (manuscript["status"], manuscript["human_approved"]) == ("draft", "false")
assert (audit["status"], audit["human_decision"]) == ("needs_review", "pending")
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T121() {
    local tmp checked
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    printf '# First\n\nFirst bounded source.\n' > "$tmp/chapters/first.md"
    printf '# Second\n\nSecond bounded source.\n' > "$tmp/chapters/second.md"
    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/first.md --copy-source --json >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp/thesis_control" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
for name in ("project_intent.csv", "manuscript_contracts.csv", "global_thesis_audits.csv"):
    path = root / name
    header = path.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(header + "\n", encoding="utf-8")
PY
    python3 archive/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/second.md --copy-source --json >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$checked" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['project_intents'] == d['summary']['manuscript_contracts'] == d['summary']['global_thesis_audits'] == 1"
}

_make_legacy_v3_project_intent_packet() {
    local root="$1"
    _make_valid_thesis_control_packet "$root"
    rm -f \
        "$root/thesis_control/project_intent.csv" \
        "$root/thesis_control/manuscript_contracts.csv" \
        "$root/thesis_control/global_thesis_audits.csv"
    python3 - "$root" <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "thesis_control"
for filename, removed in (
    ("spine_cards.csv", "manuscript_id"),
    ("edit_contracts.csv", "global_audit_id"),
):
    path = root / filename
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = [field for field in (reader.fieldnames or []) if field != removed]
    for row in rows:
        row.pop(removed, None)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
PY
}

test_T122() {
    local tmp first second before after checked rc
    tmp=$(mktemp -d) || return 1
    _make_legacy_v3_project_intent_packet "$tmp" || {
        rm -rf "$tmp"
        return 1
    }
    first=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    before=$(_tree_digest "$tmp") || return 1
    second=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after=$(_tree_digest "$tmp")
    checked=$(python3 archive/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    python3 - "$tmp" "$first" "$second" "$checked" "$before" "$after" "$rc" <<'PY'
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
first = json.loads(sys.argv[2])
second = json.loads(sys.argv[3])
checked = json.loads(sys.argv[4])
assert first["status"] == "upgraded_blocked"
assert first["author_action_required"] is True
assert second["status"] == "unchanged"
assert sys.argv[5] == sys.argv[6]
assert sys.argv[7] == "1"
kinds = {issue["kind"] for issue in checked["issues"]}
assert {"global-thesis-gate-required", "active-project-intent-required", "active-manuscript-contract-required"} <= kinds
with (root / "thesis_control/spine_cards.csv").open(encoding="utf-8") as handle:
    assert "manuscript_id" in (csv.DictReader(handle).fieldnames or [])
with (root / "thesis_control/edit_contracts.csv").open(encoding="utf-8") as handle:
    assert "global_audit_id" in (csv.DictReader(handle).fieldnames or [])
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T123() {
    local tmp before after out rc
    tmp=$(mktemp -d) || return 1
    _make_legacy_v3_project_intent_packet "$tmp" || {
        rm -rf "$tmp"
        return 1
    }
    printf 'intent_id\n' > "$tmp/thesis_control/project_intent.csv"
    before=$(_tree_digest "$tmp") || return 1
    out=$(python3 archive/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"partial project-intent schema"* ]]
}

test_T124() {
    local tmp
    tmp=$(mktemp -d) || return 1
    _make_legacy_v3_project_intent_packet "$tmp" || {
        rm -rf "$tmp"
        return 1
    }
    python3 - "$tmp" "$REPO_ROOT/archive/skills/thesis-control/scripts" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
from upgrade_thesis_control_project_intent import upgrade

root = Path(sys.argv[1])
alias = root.parent / f"{root.name}-path-alias"
try:
    alias.symlink_to(root, target_is_directory=True)
    payload = upgrade(alias)
finally:
    alias.unlink(missing_ok=True)
assert payload["status"] == "upgraded_blocked"
assert payload["author_action_required"] is True
assert Path(payload["project_intent"]).resolve() == (root / "thesis_control/project_intent.csv").resolve()
PY
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T112() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    _make_valid_argument_packet "$tmp"
    python3 archive/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --json >/dev/null
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T113() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_argument_packet "$tmp"
    sed 's/adequately_supported/unsupported/' "$tmp/evidence/claim_hierarchy.csv" > "$tmp/evidence/claim_hierarchy.tmp"
    mv "$tmp/evidence/claim_hierarchy.tmp" "$tmp/evidence/claim_hierarchy.csv"
    out=$(python3 archive/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='weak-main-claim-support' for i in d['issues'])"
}

test_T114() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/review_packet/evidence"
    cat > "$tmp/review_packet/manuscript.md" <<'EOF'
# Manuscript

This is a fixture manuscript.
EOF
    cat > "$tmp/review_packet/references.bib" <<'EOF'
@article{smith2024,title={Fixture},author={Smith, Jane},year={2024},journal={Journal}}
EOF
    cat > "$tmp/review_packet/evidence/claim_register.csv" <<'EOF'
claim_id,claim_text
C1,Fixture claim
EOF
    cat > "$tmp/review_packet/review_manifest.yaml" <<'EOF'
review_mode: self_review_clean_room
allowed_sources:
  - manuscript.md
  - references.bib
  - evidence/claim_register.csv
forbidden_sources:
  - prior_chat_memory
  - unstated_project_assumptions
  - model_background_knowledge_as_evidence
  - unpublished_notes_not_listed_in_manifest
EOF
    python3 archive/skills/self-review/scripts/check_self_review_packet.py "$tmp/review_packet" --json >/dev/null
    rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T115() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/review_packet"
    cat > "$tmp/review_packet/manuscript.md" <<'EOF'
# Manuscript
EOF
    cat > "$tmp/review_packet/review_manifest.yaml" <<'EOF'
review_mode: self_review_clean_room
allowed_sources:
  - manuscript.md
  - prior_chat_memory
forbidden_sources:
  - prior_chat_memory
EOF
    out=$(python3 archive/skills/self-review/scripts/check_self_review_packet.py "$tmp/review_packet" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'forbidden-source-allowed' in kinds and 'missing-required-forbidden-source' in kinds"
}

test_T50() {
    # Single canonical skills tree (v0.1 design §13): every .claude/skills
    # entry is exposed 1:1 through the repo-root .agents/skills links (dsh,
    # Codex, and Claude Code all read the same files), every link resolves
    # to a real SKILL.md, and no stray link points anywhere else.
    local canonical linked name
    canonical=$(ls "$REPO_ROOT/.claude/skills" | sort)
    linked=$(ls "$REPO_ROOT/.agents/skills" | sort)
    [[ "$canonical" == "$linked" ]] || return 1
    for name in $linked; do
        [[ -L "$REPO_ROOT/.agents/skills/$name" ]] || return 1
        [[ -f "$REPO_ROOT/.agents/skills/$name/SKILL.md" ]] || return 1
    done
}

test_T138() {
    # A Markdown thesis chapter cites in Harvard author-year form and never
    # names a bib key. Before this test the audit saw no citation at all
    # there: every advertised term was "unsourced" and every bib entry
    # "dangling". Now Harvard forms count for proximity, bib entries match by
    # first-author surname + year, and a "Keywords:" line advertises terms.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/chapters"
    cat > "$tmp/references.bib" <<'EOF'
@article{smith2024archive, title={The Archive}, author={Smith, Jane and Doe, John}, year={2024}, journal={J. Mem.}}
@book{jones2021memory, title={Contested Memory}, author={Alex Jones}, year={2021}, publisher={Press}}
EOF
    cat > "$tmp/chapters/ch1.md" <<'EOF'
# Chapter 1

Keywords: Shortcut Learning, Construct Validity

The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short.

Construct validity is invoked throughout, yet this paragraph names no source for it at all,
which is exactly the finding the audit exists to surface in a thesis workspace.

The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short. The pool holds many images and the queries are short.

Shortcut learning is the central worry of this chapter, as Smith (2024) argues at length
and as later work confirms (Smith and Doe, 2024, p. 12).
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py --base-dir "$tmp/chapters" --bib "$tmp/references.bib" --json 2>&1)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
unsourced=[i['detail'] for i in d['issues'] if i['kind']=='unsourced-keyword']
dangling=[i['detail'] for i in d['issues'] if i['kind']=='dangling-entry']
assert unsourced==['Construct Validity'], unsourced   # Shortcut Learning is sourced by Harvard cites
assert dangling==['jones2021memory'], dangling           # smith2024 is cited by surname+year, never by key
"
}

_make_valid_release_packet() {
    local tmp="$1"
    mkdir -p "$tmp/release"
    cat > "$tmp/release/release_scope.md" <<'EOF'
# Release Scope

Scope date: 2026-05-31
Paper/artifact: Generic review packet
Deadline/use: collaborator handoff
Included refs: refs/heads/main at abcdef1234567890
Excluded refs: none
Open question: whether one optional figure should stay local-only
EOF
    cat > "$tmp/release/canonical_refs.csv" <<'EOF'
ref_name,sha,date,status,canonical_for,caveat
main,abcdef1234567890,2026-05-31,clean,manuscript,none
EOF
    cat > "$tmp/release/local_asset_inventory.csv" <<'EOF'
path,status,file_count,size,role,release_action
figures/source/tracked.png,tracked,1,42K,figure source,keep tracked
EOF
    cat > "$tmp/release/artifact_anchors.csv" <<'EOF'
artifact_id,source_ref,source_path,count_or_checksum,evidence_state,verified_by,claim_supported
fig1,main,figures/source/tracked.png,sha256:abc,verified_artifact,manual checksum,figure provenance
EOF
    cat > "$tmp/release/evidence_gates.csv" <<'EOF'
gate_id,artifact_id,evidence_state,human_confirmed,reviewer,review_date,validator,status
gate1,fig1,human_final,true,Reviewer One,2026-05-31,manual packet review,passed
EOF
    cat > "$tmp/release/claim_ledger.csv" <<'EOF'
claim_id,claim_text,artifact_ids,evidence_state,denominator,scope_boundary,human_gate_required,status
c1,The figure is anchored to a tracked source artifact,fig1,verified_artifact,one figure,provenance only,false,supported
EOF
    cat > "$tmp/release/verification_report.md" <<'EOF'
# Verification Report

Verification:
- packet validator -> clean

Residual risk:
- Optional figure still needs owner decision before submission.
EOF
}

test_T54() {
    local tmp
    tmp=$(mktemp -d) || return 1
    _make_valid_release_packet "$tmp"
    python3 archive/skills/release-governance/scripts/check_release_packet.py "$tmp" >/dev/null
    local rc=$?
    rm -rf "$tmp"
    return "$rc"
}

test_T55() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_release_packet "$tmp"
    sed 's/verified_artifact/agent_final/' "$tmp/release/artifact_anchors.csv" > "$tmp/release/artifact_anchors.tmp"
    mv "$tmp/release/artifact_anchors.tmp" "$tmp/release/artifact_anchors.csv"
    out=$(python3 archive/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'invalid-evidence-state' in kinds"
}

test_T56() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_release_packet "$tmp"
    cat > "$tmp/release/claim_ledger.csv" <<'EOF'
claim_id,claim_text,artifact_ids,evidence_state,denominator,status
c1,The figure is anchored to a tracked source artifact,fig1,verified_artifact,one figure,supported
EOF
    out=$(python3 archive/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'missing-columns' in kinds"
}

test_T57() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_release_packet "$tmp"
    printf '\nLocal cache: /tmp/private-release-cache\n' >> "$tmp/release/verification_report.md"
    printf '\nFollow-up: todo before sharing\n' >> "$tmp/release/release_scope.md"
    out=$(python3 archive/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'local-absolute-path' in kinds and 'placeholder-text' in kinds"
}

test_T58() {
    ! grep -Eq '\b(subprocess|socket|requests|urllib|http\.client|ftplib)\b' archive/skills/release-governance/scripts/check_release_packet.py
}

test_T59() {
    local setup_docs=(
        "$REPO_ROOT/docs/setup-claude-code.md"
        "$REPO_ROOT/docs/setup-codex-cli.md"
        "$REPO_ROOT/docs/setup-gemini-cli.md"
        "$REPO_ROOT/docs/setup-openclaw.md"
    )

    local stale_phrase="11 public academic writing skill"
    ! grep -R -q "${stale_phrase}s" "${setup_docs[@]}" || return 1

    # Compare advertised skill tables with the canonical catalogue. Requiring
    # retired names made a stale guide pass and an accurate guide fail.
    python3 - "$REPO_ROOT" "${setup_docs[@]}" <<'PY' || return 1
import re
import sys
from pathlib import Path
root = Path(sys.argv[1])
expected = {p.parent.name for p in (root / '.claude/skills').glob('*/SKILL.md')}
assert expected, 'canonical skill catalogue is empty'
for name in sys.argv[2:]:
    text = Path(name).read_text(encoding='utf-8')
    rows = re.findall(r'^\|\s*`?/?([a-z][a-z-]*)`?\s*\|', text, re.M)
    assert len(rows) == len(expected) and set(rows) == expected, '{}: advertised skills drifted from canonical catalogue'.format(name)
PY

    # The README pins where each product line ended: the dsh distribution at
    # its last tag with the decision record that retired it, and the previous
    # product at the last release that carried its surfaces.
    grep -q "v0.6.0-rc.2" "$REPO_ROOT/README.md" || return 1
    grep -q "docs/specs/2026-09-20-retire-dsh-line-design.md" "$REPO_ROOT/README.md" || return 1
    grep -q "v0.5.0" "$REPO_ROOT/README.md" || return 1
}
test_T137() {
    grep -q "old-versus-proposed" archive/skills/thesis-control/SKILL.md || return 1
    grep -q "old-versus-proposed" archive/skills/manuscript-reframe/SKILL.md || return 1
    grep -q "intended use" archive/skills/argument-governance/SKILL.md || return 1
    grep -q "unfamiliar human" archive/skills/self-review/SKILL.md || return 1
    grep -q "evidence -> disclaimer" archive/skills/logic-review/SKILL.md || return 1
    grep -q "Evidence baseline" archive/skills/release-governance/references/release_workflow_templates.md
}

# ----------------------------------------------------------------------------
header "Running spec §6 acceptance tests..."
header ""

# T1 (fresh-clone simulation) and T6 (PATH manipulation) and T7 (EDITOR=true)
# are skipped here because they require either a separate clone or PATH/env
# mutation that would interfere with parallel test runs.
# Run those manually per spec §6 if desired; they document the contract but
# aren't part of the automated harness.

# --- Session scan -----------------------------------------------------------
# Two sessions of the same agent changed what the other should do next without
# either noticing: one swept the other's uncommitted edits into its commit from
# the same working tree; one merged and deleted a branch the other still meant
# to push. scripts/session-scan.py asks the questions that catch both, against
# the remote as ls-remote reports it, and says what it could not check.

_scan_git() { git -c user.name=t -c user.email=t@e -c init.defaultBranch=main "$@"; }

_scan_fixture() {
    # $1: root. remote.git (bare); A on main, pushed; B, a worktree on topic, pushed.
    local root="$1"
    _scan_git init -q --bare "$root/remote.git" || return 1
    _scan_git init -q "$root/A" || return 1
    ( cd "$root/A" && echo a > a && _scan_git add a && _scan_git commit -qm base \
        && _scan_git remote add origin "$root/remote.git" && _scan_git push -qu origin main ) >/dev/null 2>&1 || return 1
    ( cd "$root/A" && _scan_git worktree add -q "$root/B" -b topic ) >/dev/null 2>&1 || return 1
    ( cd "$root/B" && echo b > b && _scan_git add b && _scan_git commit -qm topic1 \
        && _scan_git push -qu origin topic ) >/dev/null 2>&1 || return 1
}

test_T178() {
    # A scan that cannot see a remote has not scanned: exit 2, never 0.
    local tmp status
    tmp=$(mktemp -d) || return 1
    python3 scripts/session-scan.py --repo "$tmp" >/dev/null 2>&1; status=$?
    [ "$status" = "2" ] || { echo "not a repository: expected exit 2, got $status"; return 1; }
    _scan_git init -q "$tmp/r" || return 1
    python3 scripts/session-scan.py --repo "$tmp/r" >/dev/null 2>&1; status=$?
    [ "$status" = "2" ] || { echo "no remote: expected exit 2, got $status"; return 1; }
    _scan_git -C "$tmp/r" remote add origin "$tmp/nowhere.git"
    python3 scripts/session-scan.py --repo "$tmp/r" >/dev/null 2>&1; status=$?
    [ "$status" = "2" ] || { echo "unreachable remote: expected exit 2, got $status"; return 1; }
    python3 scripts/session-scan.py --repo "$tmp/r" --zzz-not-a-real-flag >/dev/null 2>&1; status=$?
    [ "$status" != "0" ] || { echo "unknown flag: expected non-zero, got 0"; return 1; }
    rm -rf "$tmp"
}

test_T179() {
    # Incident: another session merged topic into main, pushed, and deleted the
    # remote branch. The session still on topic learns that from the remote,
    # not from its tracking refs, which still show the branch.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    _scan_fixture "$tmp" || { echo "fixture failed"; return 1; }
    ( cd "$tmp" && _scan_git clone -q remote.git C && cd C && _scan_git merge -q --no-ff origin/topic -m "merge topic" \
        && _scan_git push -q origin main && _scan_git push -q origin --delete topic ) >/dev/null 2>&1 || { echo "other session failed"; return 1; }
    out=$(python3 scripts/session-scan.py --repo "$tmp/B" --json 2>&1); status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'upstream-gone' in kinds, kinds
assert 'stale-tracking-ref' in kinds, kinds
assert 'foreign-commit-in-push-range' not in kinds, kinds   # the range is an estimate here, and says so
assert any('estimate' in n for n in d['not_checked']), d['not_checked']
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T180() {
    # A commit another worktree made enters this branch through a merge: a push
    # would carry it. This worktree's own HEAD reflog is the witness.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    _scan_fixture "$tmp" || { echo "fixture failed"; return 1; }
    ( cd "$tmp/A" && echo x > x && _scan_git add x && _scan_git commit -qm "x on main, unpushed" ) >/dev/null 2>&1 || return 1
    ( cd "$tmp/B" && _scan_git merge -q main -m "merge main into topic" ) >/dev/null 2>&1 || return 1
    out=$(python3 scripts/session-scan.py --repo "$tmp/B" --json 2>&1); status=$?
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
foreign=[f for f in d['findings'] if f['kind']=='foreign-commit-in-push-range']
assert len(foreign)==1 and 'x on main' in foreign[0]['detail'], foreign
assert len(d['push_range'])==2 and sum(c['here'] for c in d['push_range'])==1, d['push_range']
" || { rm -rf "$tmp"; return 1; }
    [ "$status" = "1" ] || { rm -rf "$tmp"; echo "expected exit 1, got $status"; return 1; }
    # Control: in A the unpushed commit is A's own.
    out=$(python3 scripts/session-scan.py --repo "$tmp/A" --json 2>&1); status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count']==0, d['findings']
assert len(d['push_range'])==1 and d['push_range'][0]['here'], d['push_range']
" || return 1
    [ "$status" = "0" ] || { echo "control: expected exit 0, got $status"; return 1; }
}

test_T181() {
    # Incident: a file another session edited is staged as if it were this
    # session's. Its mtime predates the session. Without a session start the
    # scan cannot tell, and says so instead of passing.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    _scan_fixture "$tmp" || { echo "fixture failed"; return 1; }
    ( cd "$tmp/A" && echo old > old.txt && touch -t 202601010100 old.txt && _scan_git add old.txt && echo new > new.txt ) || return 1
    out=$(python3 scripts/session-scan.py --repo "$tmp/A" --since "2026-06-01 00:00" --json 2>&1); status=$?
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
staged=[f for f in d['findings'] if f['kind']=='staged-before-session']
assert len(staged)==1 and staged[0]['detail'].startswith('old.txt'), d['findings']
assert not [f for f in d['findings'] if f['kind']=='dirty-before-session'], d['findings']   # new.txt is fresh
" || { rm -rf "$tmp"; return 1; }
    [ "$status" = "1" ] || { rm -rf "$tmp"; echo "expected exit 1, got $status"; return 1; }
    out=$(python3 scripts/session-scan.py --repo "$tmp/A" --json 2>&1); status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count']==0, d['findings']
assert any('session start unknown' in n for n in d['not_checked']), d['not_checked']
" || return 1
    [ "$status" = "0" ] || { echo "no start: expected exit 0, got $status"; return 1; }
}

test_T182() {
    # The session start comes from the transcript's first user record, not the
    # file's birth time; other transcripts that name this repository since then
    # are counted, the scan's own is not, and a sibling path is not this one.
    local tmp out status ago
    tmp=$(mktemp -d) || return 1
    _scan_fixture "$tmp" || { echo "fixture failed"; return 1; }
    mkdir -p "$tmp/transcripts/proj" || return 1
    ago=$(python3 -c "from datetime import datetime,timezone,timedelta;print((datetime.now(timezone.utc)-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'))")
    printf '{"type":"summary"}\n{"type":"user","timestamp":"%s"}\n' "$ago" > "$tmp/transcripts/proj/own.jsonl"
    printf '{"type":"user","timestamp":"%s"}\n{"type":"assistant","text":"cd %s && git commit"}\n' "$ago" "$tmp/A" > "$tmp/transcripts/proj/other.jsonl"
    printf '{"type":"assistant","text":"cd %s-sibling && ls"}\n' "$tmp/A" > "$tmp/transcripts/proj/sibling.jsonl"
    ( cd "$tmp/A" && echo old > old.txt && touch -t 202601010100 old.txt ) || return 1
    out=$(python3 scripts/session-scan.py --repo "$tmp/A" --transcript "$tmp/transcripts/proj/own.jsonl" \
        --transcripts-dir "$tmp/transcripts" --json 2>&1); status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
names=[t['path'].rsplit('/',1)[-1] for t in d['transcripts']]
assert names==['other.jsonl'], names
assert [f['kind'] for f in d['findings'] if f['kind']=='dirty-before-session']==['dirty-before-session'], d['findings']
assert d['since'] is not None and d['hard_finding_count']==0, d
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T183() {
    # A branch whose upstream is a different branch. The range is counted
    # against the upstream, so the headline answers a question nobody asked;
    # and under push.default=upstream a bare push sends these commits there.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    _scan_fixture "$tmp" || { echo "fixture failed"; return 1; }
    ( cd "$tmp/B" && _scan_git branch --set-upstream-to=origin/main topic ) >/dev/null 2>&1 || return 1
    # One commit after topic was pushed, so the two counts genuinely differ:
    # 1 against origin/topic, 2 against origin/main, which is what the headline
    # counts. A first version of this test asserted numbers taken from the real
    # repository instead of derived from this fixture, and failed on both.
    ( cd "$tmp/B" && echo b2 > b2 && _scan_git add b2 && _scan_git commit -qm topic2 ) >/dev/null 2>&1 || return 1
    out=$(python3 scripts/session-scan.py --repo "$tmp/B" --json 2>&1); status=$?
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=[f for f in d['findings'] if f['kind']=='upstream-is-a-different-branch']
assert len(m)==1 and not m[0]['hard'], d['findings']          # simple refuses: a prompt
assert 'push.default=simple' in m[0]['detail'], m[0]['detail']
assert d['same_name_ahead']=='1', d['same_name_ahead']         # what an explicit push carries
assert len(d['push_range'])==2, d['push_range']                # what the headline counted
" || { rm -rf "$tmp"; return 1; }
    [ "$status" = "0" ] || { rm -rf "$tmp"; echo "expected exit 0, got $status"; return 1; }
    # push.default=upstream sends them to the other branch: that is a hard finding.
    ( cd "$tmp/B" && _scan_git config push.default upstream ) || { rm -rf "$tmp"; return 1; }
    out=$(python3 scripts/session-scan.py --repo "$tmp/B" --json 2>&1); status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=[f for f in d['findings'] if f['kind']=='upstream-is-a-different-branch']
assert len(m)==1 and m[0]['hard'], d['findings']
assert 'SENDS' in m[0]['detail'], m[0]['detail']
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T184() {
    # The header says how many tests this file runs. Nothing counted it, and
    # retiring a skill removed two without touching the line: it claimed 176
    # where 174 ran. A number in this toolkit's own documentation that nothing
    # checks is the same shape as a check that examines nothing.
    local head claimed actual highest last
    head=$(sed -n '2p' "$REPO_ROOT/scripts/test.sh")
    claimed=$(printf '%s' "$head" | sed -n 's/.*(\([0-9]\{1,\}\) automated tests.*/\1/p')
    actual=$(grep -c '^run_test ' "$REPO_ROOT/scripts/test.sh")
    [ -n "$claimed" ] || { echo "the header does not state a test count"; return 1; }
    [ "$claimed" = "$actual" ] || { echo "header claims $claimed tests, $actual run_test lines"; return 1; }
    # and the range it names ends at the highest test actually registered
    highest=$(printf '%s' "$head" | sed -n 's/.*labelled T2-T\([0-9]\{1,\}\):.*/\1/p')
    last=$(grep -oE '^run_test "T[0-9]+' "$REPO_ROOT/scripts/test.sh" | grep -oE '[0-9]+' | sort -n | tail -1)
    [ -n "$highest" ] || { echo "the header does not state a range"; return 1; }
    [ "$highest" = "$last" ] || { echo "header says the range ends at T$highest, highest registered is T$last"; return 1; }
}

# --- T185-T187: the public-content audit reports what it read ---------------

test_T185() {
    # A base-dir with none of the public surfaces under it used to print
    # `issue_count: 0` and exit 0, the same line as a clean tree. A scan that
    # read nothing is not a clean scan.
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    out=$(python3 "$REPO_ROOT/scripts/audit-public-content.py" --base-dir "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [ "$rc" = "2" ] || { echo "expected exit 2 on an empty base-dir, got $rc"; return 1; }
    grep -q "nothing checked" <<<"$out" || return 1
}

test_T186() {
    # The count is the number of files read, and no file is skipped for its
    # encoding: a Latin-1 file with a residue on its second line is reported,
    # at that line. The old reader decoded as UTF-8 and skipped it silently.
    local tmp rc tok
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/docs/sub" "$tmp/docs/__pycache__" "$tmp/scripts"
    printf 'hello\n' > "$tmp/README.md"
    printf 'a\n' > "$tmp/docs/a.md"
    printf 'b\n' > "$tmp/docs/sub/b.md"
    printf 'x\n' > "$tmp/scripts/x.py"
    printf 'cached\n' > "$tmp/docs/__pycache__/c.pyc"
    tok=$(printf '%s%s' 'Judge' '++')   # joined at run time so this file does not match itself
    printf 'caf\xe9\nsee %s here\n' "$tok" > "$tmp/docs/l1.md"
    python3 "$REPO_ROOT/scripts/audit-public-content.py" --base-dir "$tmp" --json > "$tmp/out.json" 2>/dev/null
    rc=$?
    [ "$rc" = "1" ] || { rm -rf "$tmp"; echo "expected exit 1 with a planted residue, got $rc"; return 1; }
    python3 - "$tmp/out.json" "$tok" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
tok = sys.argv[2]
assert d["files_scanned"] == 5, d["files_scanned"]
assert d["roots_present"] == ["README.md", "docs", "scripts"], d["roots_present"]
assert "CLAUDE.md" in d["roots_missing"], d["roots_missing"]
assert d["nothing_checked"] is False, d
assert d["issue_count"] == 1, d["issues"]
issue = d["issues"][0]
assert issue["location"] == "docs/l1.md:2", issue
assert issue["token"] == tok, issue
PY
    rc=$?
    rm -rf "$tmp"
    [ "$rc" = "0" ] || return 1
}

test_T187() {
    # On the real tree the count is compared with something counted
    # independently: at least every SKILL.md and every script under scripts/.
    # The two roots the audit exists for must be among those present.
    local tmp floor rc
    tmp=$(mktemp) || return 1
    python3 "$REPO_ROOT/scripts/audit-public-content.py" --base-dir "$REPO_ROOT" --json > "$tmp" 2>/dev/null || { rm -f "$tmp"; return 1; }
    floor=$(( $(find "$REPO_ROOT/.claude/skills" -name SKILL.md | wc -l) + $(find "$REPO_ROOT/scripts" -maxdepth 1 -name '*.py' | wc -l) ))
    python3 - "$tmp" "$floor" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
floor = int(sys.argv[2])
assert floor >= 10, floor
assert d["files_scanned"] >= floor, (d["files_scanned"], floor)
for root in (".claude/skills", "scripts"):
    assert root in d["roots_present"], d["roots_present"]
PY
    rc=$?
    rm -f "$tmp"
    [ "$rc" = "0" ] || return 1
}

# --- T188-T189: the scripts/ audits fail closed; the docs' skill count is derived

test_T188() {
    # The three project audits under scripts/ were outside the fails-closed
    # registry and exited 0 with `issue_count: 0` on a base-dir with no
    # chapters and no notes: the same line as a clean manuscript. A run that
    # read nothing is not a clean run.
    local tmp s rc out
    tmp=$(mktemp -d) || return 1
    for s in audit-citations.py audit-british-english.py audit-logic.py; do
        out=$(python3 "$REPO_ROOT/scripts/$s" --base-dir "$tmp" --json 2>&1)
        rc=$?
        [ "$rc" = "2" ] || { rm -rf "$tmp"; echo "$s: expected exit 2 on an empty base-dir, got $rc"; return 1; }
        grep -q "nothing checked" <<<"$out" || { rm -rf "$tmp"; echo "$s: exit 2 without saying nothing was checked"; return 1; }
    done
    rm -rf "$tmp"
}

test_T189() {
    # The docs say how many skills ship, and nothing derived that number:
    # after one skill was retired, "nine" and "9 skills" were fixed by hand in
    # five places and "9-skill" survived in four more. The count is read from
    # disk here, and every numbered mention of the catalogue in the live docs
    # (dated records under docs/specs, docs/research and docs/product excepted)
    # has to match it.
    local n out rc
    n=$(find "$REPO_ROOT/.claude/skills" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
    [ "$n" -ge 5 ] || { echo "only $n skill directories; below that this check proves nothing"; return 1; }
    out=$(python3 - "$REPO_ROOT" "$n" <<'PY'
import re, sys, pathlib
root, n = pathlib.Path(sys.argv[1]), int(sys.argv[2])
words = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
num = r"(\d+|" + "|".join(words) + r")"
pats = [re.compile(r"\b" + num + r"[- ]skill\b", re.I),
        # one adjective may sit between the number and "skills" ("the eight canonical skills" slipped past this
        # check until 2026-09-21), and "provides N skills" names the catalogue too
        re.compile(r"\b(?:the|all|these|its|those|same|provides)\s+" + num + r"\s+(?:\w+\s+)?skills\b", re.I),
        re.compile(r"\b" + num + r"\s+academic[- ]writing[- ]skills\b", re.I),
        re.compile(r"\b" + num + r"\s+advisory\s+skills\b", re.I)]
skip = {"specs", "research", "product"}
files = [root / "README.md"] + sorted(p for p in (root / "docs").rglob("*.md")
                                      if not skip & set(p.relative_to(root / "docs").parts))
bad = []
for f in files:
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for pat in pats:
            for m in pat.finditer(line):
                tok = m.group(1).lower()
                val = int(tok) if tok.isdigit() else words[tok]
                if val != n:
                    bad.append("%s:%d says %s, but %d skills ship" % (f.relative_to(root), i, tok, n))
print("\n".join(bad))
sys.exit(1 if bad else 0)
PY
)
    rc=$?
    [ "$rc" = "0" ] || { echo "$out"; return 1; }
}

# --- T190: the README's project-structure block names only paths that exist -

_readme_structure_paths() {
    # Prints every path the README's structure block names, one per line,
    # nested entries joined to their parent. Arguments: README path.
    python3 - "$1" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
block = re.search(r"## Project structure\n+```text\n(.*?)```", text, re.S)
if not block:
    sys.exit("no project-structure block found")
parent = ""
for line in block.group(1).splitlines()[1:]:
    m = re.match(r"^(?P<indent>[│ ]*)(?:├──|└──) (?P<path>\S+)", line)
    if not m:
        continue
    path = m.group("path")
    if m.group("indent"):
        path = parent + path
    else:
        parent = path if path.endswith("/") else ""
    print(path)
PY
}

test_T190() {
    # After the dsh distribution was retired, the block that draws the
    # repository still named seven directories that were gone. Nothing read
    # that block against the disk; this does, and it is derived, so it holds
    # for the next removal too.
    local missing
    missing=$(_readme_structure_paths "$REPO_ROOT/README.md" | while read -r p; do [ -e "$REPO_ROOT/$p" ] || echo "$p"; done)
    [ -z "$missing" ] || { echo "the README names paths that do not exist:"; echo "$missing" | sed 's/^/  /'; return 1; }
    [ "$(_readme_structure_paths "$REPO_ROOT/README.md" | wc -l | tr -d ' ')" -ge 8 ] || { echo "fewer than 8 paths parsed; the parser lost the block"; return 1; }
}

# ── T191–T193: the writing loop (experimental/writing-loop/) ──────────────────
# The engine is stdlib-only Python. Its tests build throwaway git repositories
# and fake transcripts; tests that read a real manuscript are kept outside this
# public repository and are not part of this suite.

test_T191() {
    # The engine's own tests pass, and at least one ran: "OK" over zero tests
    # would be a vacuous pass.
    local out
    out=$(cd experimental/writing-loop/engine/tests && PYTHONPATH="..:." python3 -m unittest -q 2>&1)
    echo "$out" | grep -qE '^Ran [1-9][0-9]* tests?' || return 1
    echo "$out" | grep -q '^OK' || return 1
    ! echo "$out" | grep -q 'skipped'
}

test_T192() {
    # Red check: each mutation breaks the engine in one known way and names the
    # test that must then fail. A mutation whose test stays green means that
    # test cannot see the fault it claims to guard.
    local out rc
    out=$(python3 experimental/writing-loop/engine/tests/redcheck.py 2>&1); rc=$?
    [ "$rc" -eq 0 ] || { echo "$out" | tail -5; return 1; }
    echo "$out" | grep -qE '^\[[0-9.]+\] ' || return 1
}

_home_paths_under() {
    grep -rIlE '(/Users/[^/[:space:]"]+/|/home/[^/[:space:]"]+/)' "$1" 2>/dev/null
}

test_T193() {
    # experimental/ is a public surface. The public-content audit must cover it
    # and no file there may carry an absolute home-directory path. Both checks
    # are first shown able to fail on a planted residue.
    local tmp rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/experimental/x"
    printf 'owner = "%s%s"\n' "Hao" "rui" > "$tmp/experimental/x/a.py"
    printf 'root = "/Users/%s/work/"\n' "someone" > "$tmp/experimental/x/b.py"
    python3 scripts/audit-public-content.py --base-dir "$tmp" >/dev/null 2>&1; rc=$?
    local planted_path
    planted_path=$(_home_paths_under "$tmp/experimental")
    rm -rf "$tmp"
    [ "$rc" -eq 1 ] || return 1
    [ -n "$planted_path" ] || return 1
    [ -z "$(_home_paths_under experimental)" ]
}

run_test "T2  symlink corruption + repair"        test_T2
run_test "T3  sync drift detection + restore"     test_T3
run_test "T4  CLAUDE.md edit propagates to both"  test_T4
run_test "T5  missing marker aborts sync"         test_T5
run_test "T8  sync is idempotent"                 test_T8
run_test "T9  make init aborts without tty"       test_T9
run_test "T10 core.fileMode auto-fix"             test_T10
run_test "T11 no CLAUDE_SKILL_DIR in skill files" test_T11
run_test "T12 no export_output in skill files"   test_T12
run_test "T13 no revisiting status enum"         test_T13
run_test "T14 no deprecated vocab in /map+/note" test_T14
run_test "T15 no compile_pdf.py references"      test_T15
run_test "T16 no PDF export claim in setup docs" test_T16
run_test "T17 Python 3.8 import safety"           test_T17
run_test "T18 allowed-tools sanity (/map+/verify)" test_T18
run_test "T19 phantom citation (Harvard)"          test_T19
run_test "T20 unused citation (Harvard)"           test_T20
run_test "T21 style-outlier (mixed)"               test_T21
run_test "T22 format-comma (APA in Harvard)"       test_T22
run_test "T23 format-comma (Harvard in APA)"       test_T23
run_test "T24 notes-source-malformed (Tier 0)"     test_T24
run_test "T25 etal threshold (APA 3 authors)"      test_T25
run_test "T26 clean Chicago Author-Date"           test_T26
run_test "T27 MLA unused (lastname pair)"          test_T27
run_test "T28 numeric-gap (IEEE [3] missing)"      test_T28
run_test "T29 clean Vancouver"                     test_T29
run_test "T30 clean GB/T 7714-2015 (CJK punct)"    test_T30
run_test "T31 etal threshold (Harvard 4 authors)"  test_T31
run_test "T32 repair clear error on unwritable .agents" test_T32
run_test "T33 public content scan is clean"        test_T33
run_test "T34 internal Superpowers plans removed"  test_T34
run_test "T35 British English audit detects US forms" test_T35
run_test "T36 British English fixer applies safe replacements" test_T36
run_test "T37 citation safe-fix proposes Harvard comma fix" test_T37
run_test "T38 citation safe-fix applies to temp project" test_T38
run_test "T39 logic audit detects paragraph issues" test_T39
run_test "T40 verify-refs accepts valid BibTeX offline" test_T40
run_test "T41 verify-refs flags duplicate/arXiv issues" test_T41
run_test "T42 new skills have Claude dirs and Agent symlinks" test_T42
run_test "T43 README documents new local agent skills" test_T43
run_test "T44 no private/project-specific content in public surfaces" test_T44
run_test "T45 verify-refs Crossref fixture verifies metadata" test_T45
run_test "T46 verify-refs flags Crossref title mismatch" test_T46
run_test "T47 verify-refs flags Crossref year mismatch" test_T47
run_test "T48 verify-refs arXiv fixture verifies metadata" test_T48
run_test "T49 verify-refs documents online flags" test_T49
run_test "T125 verify-refs parses unbraced numeric fields" test_T125
run_test "T126 verify-refs preserves nested-brace values" test_T126
run_test "T50 canonical skills tree is exposed 1:1 via .agents/skills" test_T50
run_test "T54 release packet validator accepts a clean packet" test_T54
run_test "T55 release packet validator rejects invalid evidence state" test_T55
run_test "T56 release packet validator rejects missing columns" test_T56
run_test "T57 release packet validator rejects local paths and placeholders" test_T57
run_test "T58 release packet validator stays local-only" test_T58
run_test "T59 local-agent docs avoid skill drift" test_T59
run_test "T60 verify-refs accepts Markdown BibTeX fences" test_T60
run_test "T61 productization docs and demo structure exist" test_T61
run_test "T62 demo project validates with existing checkers" test_T62
run_test "T63 productization docs keep local links valid" test_T63
run_test "T64 thesis-control packet accepts bounded edit case" test_T64
run_test "T65 thesis-control catches distorted edit case" test_T65
run_test "T66 thesis-control scaffold creates draft packet" test_T66
run_test "T67 thesis-control strict mode requires audits for applied edits" test_T67
run_test "T68 thesis-control scaffold rejects empty excerpts" test_T68
run_test "T69 thesis-control rejects unsafe identifiers" test_T69
run_test "T70 thesis-control rejects uninspectable source paths" test_T70
run_test "T71 thesis-control accepts relative output directories" test_T71
run_test "T72 thesis-control rejects orphan edit contracts" test_T72
run_test "T73 lost-in-conversation bench validates" test_T73
run_test "T74 thesis-control escalates repeated revisions" test_T74
run_test "T75 thesis-control blocks fourth revision without escalation" test_T75
run_test "T76 thesis-control allows fourth revision after approved escalation" test_T76
run_test "T77 thesis-control rejects invalid revision escalation links" test_T77
run_test "T78 thesis-control scaffold emits revision tracking" test_T78
run_test "T79 thesis-control upgrades legacy revision tracking" test_T79
run_test "T80 revision escalation fixture blocks then releases fourth edit" test_T80
run_test "T81 revision escalation requires a new gate after another three failures" test_T81
run_test "T82 non-strict checker accepts legacy packets while strict requires upgrade" test_T82
run_test "T83 strict checker blocks applied edits pending human review" test_T83
run_test "T84 revision escalation counts only resolved failed audits" test_T84
run_test "T85 thesis-control rejects contradictory resolved audit outcomes" test_T85
run_test "T86 one escalation cannot unlock multiple failure cycles" test_T86
run_test "T87 non-applied contracts do not count as failed attempts" test_T87
run_test "T88 scaffold preserves unique sequential revision attempts" test_T88
run_test "T89 revision escalation rejects duplicate trigger contracts" test_T89
run_test "T90 revision escalation requires one row per trigger set" test_T90
run_test "T91 thesis-control rejects duplicate CSV headers" test_T91
run_test "T92 thesis-control reports malformed CSV rows without traceback" test_T92
run_test "T93 strict thesis-control requires schema v3 escalation fields" test_T93
run_test "T94 cycle gate approval requires a completed failure group" test_T94
run_test "T95 early diagnostics never close a failure cycle" test_T95
run_test "T96 cycle gates require exact trigger count and attempt boundary" test_T96
run_test "T97 scaffold rejects malformed headers without mutation" test_T97
run_test "T98 scaffold collisions leave the packet unchanged" test_T98
run_test "T99 scaffold default contract IDs follow attempt numbers" test_T99
run_test "T100 scaffold rejects extension columns without mutation" test_T100
run_test "T101 migration rejects malformed escalation without mutation" test_T101
run_test "T102 migration rejects partial revision metadata without mutation" test_T102
run_test "T103 migration converts v2 escalation rows deterministically" test_T103
run_test "T104 migration rejects ambiguous v2 escalation rows without mutation" test_T104
run_test "T105 migration preserves extensions and is idempotent" test_T105
run_test "T106 checker rejects conflicting resolved audits and de-duplicates failures" test_T106
run_test "T107 cycle gates require trigger contracts in attempt order" test_T107
run_test "T108 scaffold validates the complete candidate packet before mutation" test_T108
run_test "T109 scaffold and migration reject internal symlink paths" test_T109
run_test "T110 batch rollback and invalid UTF-8 fail cleanly" test_T110
run_test "T111 empty and invalid audit outcomes return located issues" test_T111
test_T127() {
    # The point of the fingerprint audit is dispersion, not frequency. Two
    # documents use the same construction at the same rate; one spreads it
    # evenly, the other clusters it. The audit must separate them.
    local tmp out
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
filler = ("The encoder ranks each candidate image against the query text and "
          "records the position of the correct one for every technique in turn. ")
marked = "The score reflects the source of the page rather than its content. "
# same count (12) and same length; spread evenly vs gathered into two
# clusters separated by a drought. A single run of consecutive occurrences
# is NOT bursty -- its internal gaps are as regular as an even spread.
even = "".join(filler * 6 + marked for _ in range(12))
bursty = (filler * 24 + (marked + filler) * 6
          + filler * 24 + (marked + filler) * 6 + filler * 24)
(d / "even.txt").write_text(even, encoding="utf-8")
(d / "bursty.txt").write_text(bursty, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/even.txt" --json 2>&1) || true
    local even_cv
    even_cv=$(echo "$out" | python3 -c "import json,sys; print(json.load(sys.stdin)['metrics']['contrast_gap_cv']['value'])")
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/bursty.txt" --json 2>&1) || true
    local bursty_cv
    bursty_cv=$(echo "$out" | python3 -c "import json,sys; print(json.load(sys.stdin)['metrics']['contrast_gap_cv']['value'])")
    rm -rf "$tmp"
    python3 - "$even_cv" "$bursty_cv" <<'PYEOF'
import sys
even, bursty = float(sys.argv[1]), float(sys.argv[2])
# even use is near-regular; bunched use is far from it
assert even < 0.35, "even text should have low gap CV, got %r" % even
assert bursty > even * 2, "bunched text should have higher gap CV (%r vs %r)" % (bursty, even)
PYEOF
}

test_T128() {
    # Percentiles are withheld when the baseline is too small to support them,
    # and a missing target is a usage error rather than an empty report.
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
body = ("The retrieval pool holds one relevant image for every query. "
        "Each candidate is scored and ranked by cosine similarity. ") * 60
(d / "target.txt").write_text(body, encoding="utf-8")
(d / "base" / "one.txt").write_text(body, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/target.txt" \
            --baseline "$tmp/base" --json 2>&1) || true
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['baseline_sufficient'] is False; assert 'percentile' not in d['metrics']['semicolon_per_1k']" || { rm -rf "$tmp"; return 1; }
    python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/nope.txt" >/dev/null 2>&1
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 2 ]]
}

test_T129() {
    # A manuscript that advertises a concept in its keywords while citing no
    # source for it anywhere is using a field's vocabulary without its
    # literature. That is the finding this audit exists for.
    local tmp out
    tmp=$(mktemp -d) || return 1
    cat > "$tmp/refs.bib" <<'EOF'
@article{smith2020thing, title={A Thing}, author={Smith, Jane}, year={2020}, journal={J. Things}}
EOF
    cat > "$tmp/main.tex" <<'EOF'
\keywords{Shortcut Learning, Construct Validity}
\begin{document}
We evaluate retrieval over a pool where $K \in \{1,5,10\}$ and report a shortcut
that carries the score. Construct validity is what is at stake here.

The pool holds many images and the queries are short. The pool holds many images
and the queries are short. The pool holds many images and the queries are short.
The pool holds many images and the queries are short. The pool holds many images
and the queries are short. The pool holds many images and the queries are short.
The pool holds many images and the queries are short. The pool holds many images
and the queries are short. The pool holds many images and the queries are short.

Prior work on unrelated things is relevant here~\cite{smith2020thing}.
\end{document}
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py --base-dir "$tmp" --json 2>&1)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[i['kind'] for i in d['issues']]
details=' '.join(i['detail'] for i in d['issues'])
assert kinds.count('unsourced-keyword')>=2, kinds
assert 'Shortcut Learning' in details and 'Construct Validity' in details, details
"
}

test_T130() {
    # Two ways the audit could lie. Set notation must not read as a numeric
    # citation -- it did, and a manuscript full of \$K \in \{1,5,10\}\$ looked
    # fully cited while citing nothing. And one source for a named procedure is
    # enough; flagging every later mention buries the finding.
    local tmp out
    tmp=$(mktemp -d) || return 1
    cat > "$tmp/refs.bib" <<'EOF'
@article{bh1995, title={Controlling the FDR}, author={Benjamini, Y.}, year={1995}, journal={JRSSB}}
EOF
    cat > "$tmp/main.tex" <<'EOF'
\keywords{Retrieval}
\begin{document}
We correct with the Benjamini--Hochberg procedure~\cite{bh1995} over $K \in \{1,5,10\}$.

Retrieval is measured at each $K \in \{1,5,10\}$ and the Benjamini correction
applies throughout.

We also run a permutation test at $K \in \{1,5,10\}$.
\end{document}
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py --base-dir "$tmp" --json 2>&1)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=[i['detail'] for i in d['issues'] if i['kind']=='uncited-method']
assert not any('Benjamini' in x for x in m), 'cited once is enough: %r' % m
assert any('permutation' in x for x in m), 'uncited method missed: %r' % m
"
}

run_test "T112 argument governance validator accepts a clean packet" test_T112
run_test "T113 argument governance validator flags weak main support" test_T113
run_test "T114 self-review packet validator accepts clean-room manifest" test_T114
run_test "T115 self-review packet validator rejects contamination" test_T115
run_test "T116 project-intent fixture blocks domain drift and accepts alignment" test_T116
run_test "T117 global audit cannot pass recorded project-level drift" test_T117
run_test "T118 strict thesis-control requires project-intent files" test_T118
run_test "T119 project-intent amendments require explicit lineage" test_T119
run_test "T120 scaffold creates an unapproved project-intent gate" test_T120
run_test "T121 scaffold populates header-only project-intent files" test_T121
run_test "T122 project-intent migration creates a blocked draft atomically" test_T122
run_test "T123 project-intent migration rejects partial schema without mutation" test_T123
run_test "T124 project-intent migration normalises direct-call roots" test_T124
test_T131() {
    # lag-1 must not join the spans on either side of a dropped one.
    # Both documents have the SAME length series -- three long, three short --
    # so a naive filter-then-correlate returns exactly the same value for each.
    # The spliced one puts an over-length span between two long sentences,
    # which destroys twenty genuine long-long adjacencies; honouring the gaps
    # therefore has to report a lower value than the unspliced document.
    local tmp a b
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
long_s = ("The encoder ranks every candidate image against the query text and "
          "records the position of the correct plate for each of the eighteen "
          "techniques in turn under this pool. ")
short_s = "The null is one in ninety. "
splice = "Filler " * 150 + ". "
# three long then three short: four same-class adjacencies against two
# crossings per period, so the series clusters and lag-1 is clearly positive
plain = (long_s * 3 + short_s * 3) * 20
spliced = (long_s + splice + long_s * 2 + short_s * 3) * 20
(d / "plain.txt").write_text(plain, encoding="utf-8")
(d / "spliced.txt").write_text(spliced, encoding="utf-8")
PYEOF
    a=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/plain.txt" --json 2>&1 \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['metrics']['sentence_length_lag1']['value'])")
    b=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/spliced.txt" --json 2>&1 \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['metrics']['sentence_length_lag1']['value'])")
    rm -rf "$tmp"
    python3 - "$a" "$b" <<'PYEOF'
import sys
a, b = float(sys.argv[1]), float(sys.argv[2])
assert a > 0.2, "long-long short-short should cluster, got %r" % a
assert b < a - 0.1, "the dropped spans were joined to their neighbours (%r vs %r)" % (b, a)
PYEOF
}

test_T132() {
    # A baseline that contains the authors' own work is partly the thing being
    # measured, and it is often their paper that sets the extreme. --exclude
    # must remove it from the corpus and say so.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
# the baseline loop wants at least 1500 words per document
calm = "The pool holds one relevant image for every query in this evaluation. " * 150
loud = "The pool holds one image; the query is text; the model is frozen. " * 150
(d / "target.txt").write_text(calm, encoding="utf-8")
# Each baseline paper is semicolon-free like the target but worded differently.
# They used to be verbatim copies of the target, which was convenient until the
# baseline scan started reading a verbatim copy as exactly what it is: a draft
# of the target sitting in its own baseline. The distribution this test needs
# survives the rewording; the contamination does not.
papers = [
    "Sediment cores from the northern shelf preserve annual laminations of winter runoff. ",
    "The compiler rewrites every loop whose bounds are known before the build begins. ",
    "Participants rated fourteen photographs and then described what they had noticed. ",
    "Orbital decay is dominated by atmospheric drag below six hundred kilometres. ",
    "Enzyme activity fell above forty degrees and did not recover on later cooling. ",
    "Rainfall totals were logged hourly at nine stations across the upper catchment. ",
]
for i, body in enumerate(papers):
    filled = body * 200
    assert len(filled.split()) >= 1500, "fixture %d is too short" % i
    (d / "base" / ("paper%d.txt" % i)).write_text(filled, encoding="utf-8")
(d / "base" / "ours2025.txt").write_text(loud, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/target.txt" \
            --baseline "$tmp/base" --json 2>&1) || true
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['baseline_documents']==7, d['baseline_documents']; assert d['metrics']['semicolon_per_1k']['baseline_max'] > 5" || { rm -rf "$tmp"; return 1; }
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/target.txt" \
            --baseline "$tmp/base" --exclude 'ours*' --json 2>&1) || true
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['baseline_documents']==6, d['baseline_documents']; assert d['baseline_excluded']==['ours2025.txt'], d['baseline_excluded']; assert d['metrics']['semicolon_per_1k']['baseline_max'] < 1"
}

test_T133() {
    # An inline author-year citation after a full stop is not a sentence.
    # Allowing "(" to open one fragments a PDF-derived baseline in proportion
    # to its citation style, which is not a property of its prose.
    local tmp cv
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
body = ("The encoder scores each candidate image against the query text and "
        "records where the correct plate lands in the ranking for this pool. ")
frag = "(2019); Smith et al. "
(d / "cited.txt").write_text((body + frag) * 40, encoding="utf-8")
PYEOF
    cv=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/cited.txt" --json 2>&1 \
         | python3 -c "import json,sys; print(json.load(sys.stdin)['metrics']['sentence_length_cv']['value'])")
    rm -rf "$tmp"
    python3 - "$cv" <<'PYEOF'
import sys
cv = float(sys.argv[1])
assert cv < 0.2, "citation fragments were counted as sentences (CV %r)" % cv
PYEOF
}

test_T134() {
    # Package loading and macro definitions are not prose. Counting them
    # inflates the word total that every per-1k rate is divided by.
    local tmp plain pre
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
body = "The pool holds one relevant image for every query in this evaluation. " * 40
(d / "plain.tex").write_text("\\begin{document}\n" + body + "\n\\end{document}\n",
                             encoding="utf-8")
(d / "pre.tex").write_text(
    "\\documentclass{acmart}\n" + "\\usepackage{amsmath} % maths support here\n" * 200
    + "\\begin{document}\n" + body + "\n\\end{document}\n", encoding="utf-8")
PYEOF
    plain=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/plain.tex" --json 2>&1 \
            | python3 -c "import json,sys; print(json.load(sys.stdin)['target_words'])")
    pre=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target "$tmp/pre.tex" --json 2>&1 \
          | python3 -c "import json,sys; print(json.load(sys.stdin)['target_words'])")
    rm -rf "$tmp"
    [[ "$plain" -eq "$pre" ]]
}

test_T139() {
    # The precondition the method states in prose -- the baseline holds none of
    # the author's own work -- used to be enforced by the caller remembering to
    # pass --exclude, and `baseline_excluded: []` read the same whether it had
    # been checked or never considered. A baseline carrying a draft of the
    # target must now withhold percentiles and name the file.
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
# The target needs a few hundred DISTINCT 4-grams, because the scan requires an
# absolute count as well as a share -- a share alone flags any text opening
# with the same stock phrase. One sentence repeated yields barely a dozen.
# Numbering the sentences does not help either: the n-gram tokeniser is
# [a-z']+, so digits are dropped and every numbered sentence collapses onto
# the same 4-grams. A varying WORD is what makes them distinct.
import itertools
_tokens = ["".join(c) for c in itertools.product("abcdefgh", repeat=3)]
target = "".join(
    "The %s stage scored the candidate pool and recorded the rank of the item. " % tok
    for tok in _tokens[:220])
(d / "target.txt").write_text(target, encoding="utf-8")
(d / "base" / "self_draft.txt").write_text(
    target + "One further remark closes the draft. ", encoding="utf-8")
others = [
    "Sediment cores from the northern shelf preserve annual laminations that record winter runoff. Each layer is counted twice and its thickness measured against a reference scale. ",
    "The compiler rewrites every loop whose bounds are known at build time and emits a specialised body. Register pressure is measured after each pass and reported per function. ",
    "Participants rated fourteen photographs on a seven point scale and then described what they noticed. Ratings were collected before any discussion took place. ",
    "Orbital decay is dominated by atmospheric drag below six hundred kilometres. The residual acceleration is fitted over successive arcs and subtracted. ",
    "Enzyme activity fell sharply above forty degrees and did not recover on cooling. Duplicate assays were run on separate days with fresh substrate. ",
]
for i, body in enumerate(others):
    # 1500 words is the audit's own floor for admitting a baseline document.
    # At 70 repeats the shortest of these fell under it, the baseline dropped
    # to four, and the test failed for a reason that had nothing to do with
    # what it asserts. The fixture now checks its own precondition.
    filled = body * 90
    assert len(filled.split()) >= 1500, "fixture %d is too short" % i
    (d / "base" / ("other%d.txt" % i)).write_text(filled, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/target.txt" --baseline "$tmp/base" --json 2>/dev/null)
    rc=$?
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['preconditions_checked'] is False, 'precondition should not read as met'
assert d['overlap_waived'] is False, 'nothing was waived here'
names = [s['file'] for s in d['baseline_suspect']]
assert names == ['self_draft.txt'], 'expected only the draft flagged, got %r' % names
assert 'percentile' not in d['metrics']['semicolon_per_1k'], 'percentiles must be withheld'
assert d['outliers'] == [], 'no outliers without percentiles -- which is why rc must not be 0'
" || { rm -rf "$tmp"; return 1; }
    # 2, not 1: withheld percentiles produce no outliers, so a contaminated run
    # would otherwise exit 0 and read as a pass.
    [[ "$rc" -eq 2 ]] || { rm -rf "$tmp"; return 1; }

    # Excluding it restores the measurement.
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/target.txt" --baseline "$tmp/base" \
            --exclude 'self_draft.txt' --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['preconditions_checked'] is True
assert d['baseline_suspect'] == []
assert d['exclude_patterns'] == ['self_draft.txt']
assert 'percentile' in d['metrics']['semicolon_per_1k']
"
}

test_T140() {
    # --allow-overlap decides whether percentiles are withheld. It does not
    # decide whether the precondition holds. Reporting preconditions_checked
    # true because a waiver was passed would rebuild the ambiguous green light
    # the scan exists to remove -- which the first draft of this feature did.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
# The target needs a few hundred DISTINCT 4-grams, because the scan requires an
# absolute count as well as a share -- a share alone flags any text opening
# with the same stock phrase. One sentence repeated yields barely a dozen.
# Numbering the sentences does not help either: the n-gram tokeniser is
# [a-z']+, so digits are dropped and every numbered sentence collapses onto
# the same 4-grams. A varying WORD is what makes them distinct.
import itertools
_tokens = ["".join(c) for c in itertools.product("abcdefgh", repeat=3)]
target = "".join(
    "The %s stage scored the candidate pool and recorded the rank of the item. " % tok
    for tok in _tokens[:220])
(d / "target.txt").write_text(target, encoding="utf-8")
(d / "base" / "self_draft.txt").write_text(target, encoding="utf-8")
others = [
    "Sediment cores from the northern shelf preserve annual laminations that record winter runoff. Each layer is counted twice and its thickness measured against a reference scale. ",
    "The compiler rewrites every loop whose bounds are known at build time and emits a specialised body. Register pressure is measured after each pass and reported per function. ",
    "Participants rated fourteen photographs on a seven point scale and then described what they noticed. Ratings were collected before any discussion took place. ",
    "Orbital decay is dominated by atmospheric drag below six hundred kilometres. The residual acceleration is fitted over successive arcs and subtracted. ",
    "Enzyme activity fell sharply above forty degrees and did not recover on cooling. Duplicate assays were run on separate days with fresh substrate. ",
]
for i, body in enumerate(others):
    # 1500 words is the audit's own floor for admitting a baseline document.
    # At 70 repeats the shortest of these fell under it, the baseline dropped
    # to four, and the test failed for a reason that had nothing to do with
    # what it asserts. The fixture now checks its own precondition.
    filled = body * 90
    assert len(filled.split()) >= 1500, "fixture %d is too short" % i
    (d / "base" / ("other%d.txt" % i)).write_text(filled, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/target.txt" --baseline "$tmp/base" --allow-overlap --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'percentile' in d['metrics']['semicolon_per_1k'], 'the waiver should restore percentiles'
assert d['overlap_waived'] is True, 'the waiver should be recorded'
assert d['preconditions_checked'] is False, 'a waiver is not a met precondition'
assert len(d['baseline_suspect']) == 1, 'the suspect stays visible in the report'
"
}

test_T169() {
    # Checking nothing is not a pass. On a tree without chapters/**/*.md the
    # fidelity audit used to return `findings: []` with exit 0 -- byte-identical
    # to a clean pass over a corpus it had fully read. It now exits 2 with
    # nothing_checked: true and says what it did not read; and when a corpus
    # exists, the denominators that say how much was read are in the payload.
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/empty/sections" "$tmp/real/chapters"
    printf 'Rescored after the second pass \\citep{smith2019}.\n' > "$tmp/empty/sections/s1.tex"
    printf 'The pool was rescored after the second pass (Smith, 2019).\n' \
        > "$tmp/real/chapters/ch1.md"
    out=$(node .claude/skills/audit/scripts/audit-citation-fidelity.mjs \
            --base-dir "$tmp/empty" --json 2>"$tmp/stderr")
    rc=$?
    # Exit 2 alone is not the signal. The audit once also exited 2 when a
    # dependency it imported was not built, and on CI that read as the
    # intended failure until json.load met an empty string. The payload has
    # to say nothing_checked itself; a run that produced no payload is
    # reported with its reason, not as either verdict.
    if ! printf '%s' "$out" | python3 -c "import json, sys; json.load(sys.stdin)" 2>/dev/null; then
        printf '  T169: the audit produced no payload (rc=%s): %s\n' "$rc" "$(head -c 200 "$tmp/stderr")"
        rm -rf "$tmp"; return 1
    fi
    [[ "$rc" -eq 2 ]] || { rm -rf "$tmp"; return 1; }
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['nothing_checked'] is True
assert d['sentences_checked'] == 0 and d['citations_checked'] == 0
nc = d['not_covered']
assert nc['latex_cite_commands'] == 1, nc
assert nc['latex_distinct_cite_keys'] == 1, nc
assert nc['latex_files_top'] and nc['latex_files_top'][0][1] == 1, nc
" || { rm -rf "$tmp"; return 1; }
    out=$(node .claude/skills/audit/scripts/audit-citation-fidelity.mjs \
            --base-dir "$tmp/real" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['nothing_checked'] is False
assert d['corpus_files'] == 1, d.get('corpus_files')
assert d['sentences_checked'] == 1, d.get('sentences_checked')
assert 'notes_sources_indexed' in d, 'the notes denominator must be visible too'
"
}

test_T170() {
    # Every baseline candidate has to leave a trace. `baseline_skipped` held
    # only the unreadable ones, so a document that loaded fine and fell under
    # the 1500-word floor vanished with no record: a corpus of 179 files
    # reported 129 documents and nothing in the report accounted for the rest.
    # The same silence once cost a test run its diagnosis.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib, itertools
d = pathlib.Path(sys.argv[1])
_tokens = ["".join(c) for c in itertools.product("abcdefgh", repeat=3)]
(d / "target.txt").write_text("".join(
    "The %s stage scored the candidate pool and recorded the rank of the item. " % tok
    for tok in _tokens[:220]), encoding="utf-8")
bodies = [
    "Sediment cores from the northern shelf preserve annual laminations that record winter runoff. Each layer is counted twice against a reference scale. ",
    "The compiler rewrites every loop whose bounds are known at build time and emits a specialised body. Register pressure is measured after each pass. ",
    "Participants rated fourteen photographs on a seven point scale and then described what they noticed. Ratings were collected before any discussion. ",
    "Orbital decay is dominated by atmospheric drag below six hundred kilometres. The residual acceleration is fitted over successive arcs and subtracted. ",
    "Enzyme activity fell sharply above forty degrees and did not recover on cooling. Duplicate assays were run on separate days with fresh substrate. ",
]
for i, body in enumerate(bodies):
    filled = body * 90
    assert len(filled.split()) >= 1500, "fixture %d is too short" % i
    (d / "base" / ("other%d.txt" % i)).write_text(filled, encoding="utf-8")
# One admitted document short of the floor, deliberately.
runt = bodies[0] * 4
assert len(runt.split()) < 1500, "the runt must be under the floor"
(d / "base" / "runt.txt").write_text(runt, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/target.txt" --baseline "$tmp/base" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
short = {x['file'] for x in d['baseline_too_short']}
assert short == {'runt.txt'}, 'the under-length document must be named, got %r' % short
assert d['baseline_documents'] == 5, d['baseline_documents']
# The point of the field is that the arithmetic closes inside the report.
seen = (d['baseline_documents'] + len(d['baseline_skipped'])
        + len(d['baseline_too_short']) + len(d['baseline_excluded']))
assert seen == 6, 'candidates must be fully accounted for, got %d' % seen
# Same pipeline on both sides here, so nothing to declare.
assert d['pipeline_mismatch'] is False, d.get('baseline_pipeline_mix')
"
}

test_T171() {
    # Per-section evenness needs no baseline, which makes it the measurement
    # that is never blocked -- and its key was simply absent when the target was
    # a directory. A run that never computed it and a run with nothing to say
    # produced the same report, so a whole-corpus reading silently lost the one
    # metric that shows whether a device runs evenly across sections.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/dir"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
body = ("The reviewers agreed on the coding frame rather than on the labels. "
        "Each pass was timed and the disagreements were logged for later reading. ") * 60
(d / "dir" / "a.txt").write_text(body, encoding="utf-8")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/dir" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert 'per_section_cv' in d, 'the key must be present even when not computed'
assert d['per_section_cv'] is None, d['per_section_cv']
note = d.get('per_section_note', '')
assert 'NOT COMPUTED' in note, note
assert 'directory' in note, 'the note must say WHY, not just that it is missing'
"
}

test_T172() {
    # A real \keywords{} block wraps across source lines. The term then carried
    # a newline, matched nothing but its own declaration -- which sits in the
    # preamble, where no citation ever is -- and a term used dozens of times, often
    # beside a citation, was reported as unsourced. A keyword genuinely absent
    # from the body is a different finding and has to say so.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/doc"
    cat > "$tmp/doc/main.tex" <<'TEXEOF'
\documentclass{article}
\title{A Study of Label Variation}
\keywords{label
variation, ghost concept}
\begin{document}
Label variation is the central problem here \citep{alpha2020}.
We return to label variation in the discussion \citep{beta2021}.
\end{document}
TEXEOF
    cat > "$tmp/doc/references.bib" <<'BIBEOF'
@article{alpha2020, author = {Alpha, A.}, title = {One}, year = {2020}}
@article{beta2021, author = {Beta, B.}, title = {Two}, year = {2021}}
BIBEOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py \
            --base-dir "$tmp/doc" --bib "$tmp/doc/references.bib" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
kw = [i['detail'] for i in d['issues'] if i['kind'] == 'unsourced-keyword']
joined = ' | '.join(kw)
assert not any('label' in k and 'absent' not in k for k in kw), \
    'a wrapped keyword used beside citations must not be flagged: %s' % joined
ghost = [k for k in kw if 'ghost concept' in k]
assert ghost, 'a keyword never used in the body must still be reported: %s' % joined
assert 'absent from body' in ghost[0], \
    'and it must say it was never used, not that it lacks a source: %s' % ghost[0]
"
}

test_T173() {
    # natbib puts the locator in an optional argument. Requiring "{" straight
    # after the command made \citep[pp.~12--14]{key} invisible, so the
    # paragraph counted as uncited and a method reported WITH its source was
    # filed as uncited-method. The more precisely a manuscript cites, the less
    # the checker saw.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/doc"
    cat > "$tmp/doc/main.tex" <<'TEXEOF'
\documentclass{article}
\begin{document}
The reported Krippendorff's alpha rose after the second pass, and the
intervals are not given \citep[pp.~12--14]{smith2019}.
\end{document}
TEXEOF
    printf '@article{smith2019, author = {Smith, A.}, title = {One}, year = {2019}}\n' \
        > "$tmp/doc/references.bib"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py \
            --base-dir "$tmp/doc" --bib "$tmp/doc/references.bib" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
kinds = [i['kind'] for i in d['issues']]
assert 'uncited-method' not in kinds, \
    'a bracketed locator is still a citation: %r' % d['issues']
assert 'dangling-entry' not in kinds, 'and the key still counts as cited'
"
}

test_T174() {
    # The bare word "novelty" is not a novelty claim. It names procedures, and
    # on one manuscript it appeared inside sentences that REFUSE the claim --
    # a sentence that explicitly refused the claim was reported as High. The
    # explicit frames carry their own negation and must keep firing.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/doc"
    cat > "$tmp/doc/main.tex" <<'TEXEOF'
\documentclass{article}
\begin{document}
The novelty-detection stage returned ten records and is described below.

A null result is not a sign of novelty, and is not read as one.

To our knowledge no earlier study has reported this effect at scale.
\end{document}
TEXEOF
    printf '@article{x2020, author = {Ex, E.}, title = {X}, year = {2020}}\n' \
        > "$tmp/doc/references.bib"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-positioning.py \
            --base-dir "$tmp/doc" --bib "$tmp/doc/references.bib" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
nov = [i['detail'] for i in d['issues'] if i['kind'] == 'bare-novelty']
assert len(nov) == 1, 'exactly the unhedged claim should fire, got %r' % nov
assert 'knowledge' in nov[0], nov[0]
"
}

test_T175() {
    # Every candidate has to leave a trace, and membership is the registrar's
    # word rather than the author's. arXiv's journal_ref is free text -- one
    # real record reads "Just accpeted by ACM Computing Surveys 2026" -- so a
    # record whose DOI resolves to a different journal must be rejected BY NAME,
    # not quietly dropped into a corpus that looks complete.
    local tmp out
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" 2>/dev/null <<'PYEOF'
import importlib.util, json, sys, pathlib
d = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "vb", ".claude/skills/audit/scripts/build-venue-baseline.py")
vb = importlib.util.module_from_spec(spec); spec.loader.exec_module(vb)

# Twenty-two in-window records: twenty good, one in another ACM journal, one
# with nothing but the author's own journal_ref.
recs = [{"arxiv_id": "24%02d.00001v1" % i, "title": "T%d" % i, "year": 2023,
         "primary_category": "cs.LG", "journal_ref": "ACM Computing Surveys",
         "doi": "10.1145/%d" % (3000000 + i)} for i in range(20)]
recs.append({"arxiv_id": "2401.99998v1", "title": "Wrong journal", "year": 2023,
             "primary_category": "cs.LG", "journal_ref": "ACM Computing Surveys",
             "doi": "10.1145/9999999"})
recs.append({"arxiv_id": "2401.99997v1", "title": "No doi", "year": 2023,
             "primary_category": "cs.LG",
             "journal_ref": "Just accpeted by ACM Computing Surveys 2026", "doi": None})
recs.append({"arxiv_id": "1901.00001v1", "title": "Too old", "year": 2019,
             "primary_category": "cs.LG", "journal_ref": "ACM Computing Surveys",
             "doi": "10.1145/1"})

vb.query_arxiv = lambda venue, delay: list(recs)
vb.container_title = lambda doi, delay: (
    "ACM Transactions on Graphics" if doi == "10.1145/9999999" else "ACM Computing Surveys")
sys.argv = ["vb", "--venue", "ACM Computing Surveys", "--from-year", "2021",
            "--dry-run", "--manifest", str(d / "m.json")]
rc = 0
try:
    vb.main()
except SystemExit as e:
    rc = e.code or 0
m = json.loads((d / "m.json").read_text())
assert rc == 0, "a corpus of twenty should succeed, rc=%s" % rc
assert m["admitted"] == 20, m["admitted"]
# Count the records, do not read the tool's own verdict on whether it counted
# them. A first version of this test asserted accounting_closes, and hardcoding
# that field to True left the test green -- the test was vouching for the
# claim instead of checking the arithmetic.
seen = [r["arxiv_id"] for r in m["records"]]
for group in m["rejected_records"].values():
    seen += [r["arxiv_id"] for r in group]
assert len(set(seen)) == len(seen), "a record appears in two dispositions"
assert len(seen) == 23, "every candidate must appear exactly once, got %d" % len(seen)
assert m["candidates"] == 23, m["candidates"]
assert m["accounting_closes"] is True, "dispositions must sum to the candidates"
assert m["rejected"]["container_title_mismatch"] == 1, m["rejected"]
assert m["rejected"]["no_doi"] == 1, m["rejected"]
assert m["rejected"]["out_of_window"] == 1, m["rejected"]
named = [r["arxiv_id"] for r in m["rejected_records"]["container_title_mismatch"]]
assert named == ["2401.99998v1"], "the mismatch must be named, got %r" % named
assert {r["container_title"] for r in m["records"]} == {"ACM Computing Surveys"}
assert all(r["venue_verified"] for r in m["records"])
# The frame itself has to be in the record, not in someone's memory.
for k in ("query", "from_year", "api", "retrieved", "verification", "stage"):
    assert m.get(k), "manifest must record %s" % k
PYEOF
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 0 ]]
}

test_T176() {
    # A corpus under the method's own twenty-document floor is not a small
    # corpus; it is not a corpus. Returning it with exit 0 is how a short
    # baseline gets quoted as a published range.
    local tmp rc
    tmp=$(mktemp -d) || return 1
    out=$(python3 - "$tmp" 2>&1 <<'PYEOF'
import importlib.util, sys, pathlib
d = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "vb", ".claude/skills/audit/scripts/build-venue-baseline.py")
vb = importlib.util.module_from_spec(spec); spec.loader.exec_module(vb)
recs = [{"arxiv_id": "24%02d.1v1" % i, "title": "T", "year": 2023,
         "primary_category": "cs.LG", "journal_ref": "V", "doi": "10.1145/%d" % i}
        for i in range(19)]
vb.query_arxiv = lambda venue, delay: list(recs)
vb.container_title = lambda doi, delay: "ACM Computing Surveys"
sys.argv = ["vb", "--venue", "ACM Computing Surveys", "--dry-run",
            "--manifest", str(d / "m.json")]
try:
    vb.main(); print("RC=0")
except SystemExit as e:
    print("RC=%s" % (e.code or 0))
PYEOF
)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 0 ]] || return 1
    grep -q "RC=2" <<<"$out" || return 1
    grep -q "VENUE_CORPUS_TOO_SMALL" <<<"$out" || return 1
    # The remedy has to offer the honest alternative, not only a wider window.
    grep -q "say so rather than measuring anyway" <<<"$out" || return 1
}

test_T177() {
    # --dry-run answers what the frame would be. It must not touch the network
    # for PDFs or leave a corpus directory behind that a later run would treat
    # as already downloaded.
    local tmp rc
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" 2>/dev/null <<'PYEOF'
import importlib.util, json, sys, pathlib
d = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "vb", ".claude/skills/audit/scripts/build-venue-baseline.py")
vb = importlib.util.module_from_spec(spec); spec.loader.exec_module(vb)
recs = [{"arxiv_id": "24%02d.1v1" % i, "title": "T", "year": 2023,
         "primary_category": "cs.LG", "journal_ref": "V", "doi": "10.1145/%d" % i}
        for i in range(21)]
vb.query_arxiv = lambda venue, delay: list(recs)
vb.container_title = lambda doi, delay: "ACM Computing Surveys"
def no_network(*a, **k):
    raise AssertionError("--dry-run must not fetch a PDF")
vb.fetch = no_network
sys.argv = ["vb", "--venue", "ACM Computing Surveys", "--dry-run",
            "--out", str(d / "corpus"), "--manifest", str(d / "m.json")]
try:
    vb.main()
except SystemExit as e:
    assert (e.code or 0) == 0, e.code
m = json.loads((d / "m.json").read_text())
assert m["dry_run"] is True
assert m["downloaded_now"] == 0, m["downloaded_now"]
assert not (d / "corpus").exists(), "--dry-run must not create the corpus directory"
assert not any("file" in r for r in m["records"]), "no record may claim a file"
PYEOF
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 0 ]]
}

run_test "T127 prose fingerprint separates even from bunched use" test_T127
run_test "T128 prose fingerprint withholds percentiles on a thin baseline" test_T128
run_test "T129 claim positioning flags advertised terms with no source" test_T129
run_test "T130 set notation is not a citation, and one source suffices" test_T130
run_test "T131 lag-1 does not join sentences across a dropped span" test_T131
run_test "T132 --exclude removes a document from the baseline corpus" test_T132
run_test "T133 an inline citation fragment is not a sentence" test_T133
run_test "T134 a LaTeX preamble is not prose" test_T134
run_test "T137 cross-skill author-control gates remain present" test_T137
# --- T142-T146: claim ledger for LaTeX manuscripts ---------------------------
# The gap: the citation fidelity audit reads chapters/**/*.md; a LaTeX
# manuscript's claims about its sources were checked by nothing. Each row of a
# claim ledger binds a manuscript sentence to a verbatim snippet in an archived
# source, and the audit checks the binding in both directions.
ledger_fixture() {
    # $1 = dir. Two content-asserting citing sentences (one ledgered, one not)
    # and one credit-only citation.
    mkdir -p "$1/sections" "$1/evidence"
    cat > "$1/sections/02_related.tex" <<'EOF'
\section{Related work}
Buckley et al. show that small pools bias the judgments toward documents with topic words~\cite{buckley2007}.
Voorhees notes that an absolute score is not meaningful in isolation~\cite{voorhees2002}.
We control the false discovery rate with the Benjamini--Hochberg procedure~\cite{bh1995}.
EOF
    cat > "$1/evidence/buckley2007.txt" <<'EOF'
This paper shows that the judgment sets produced by traditional pooling when the pools are
too small can be biased in that they favor relevant documents that contain some of the topic
title words.
EOF
    printf 'claim\tcite_key\tsnippet\tsource_file\tlevel\n' > "$1/ledger.tsv"
    printf 'Buckley et al. show that small pools bias the judgments toward documents with topic words\tbuckley2007\tcan be biased in that they favor relevant documents that contain some of the topic title words\tevidence/buckley2007.txt\tfulltext\n' >> "$1/ledger.tsv"
}

test_T147() {
    # Citing sentences but an empty ledger: nothing was verified, so this is
    # not a pass either — the coverage list alone must not read as clean.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    printf 'claim\tcite_key\tsnippet\tsource_file\tlevel\n' > "$tmp/ledger.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['citing_sentences'] == 3 and d['ledger_rows'] == 0, d
assert d['nothing_checked'] is True, d
" || return 1
    [ "$status" = "2" ] || { echo "expected exit 2, got $status"; return 1; }
}

test_T142() {
    # A snippet that is not verbatim in the archived source is a hard finding.
    local tmp out
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    sed -i.bak 's/can be biased in that they favor/are always biased because they favour/' "$tmp/ledger.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    local status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'snippet-not-in-source' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T143() {
    # A ledger row whose claim is no longer in the manuscript is a hard finding:
    # the sentence was edited and the binding went stale.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    sed -i.bak 's/Buckley et al. show that small pools bias the judgments toward documents with topic words~/Buckley et al. show that pooling is unreliable~/' "$tmp/sections/02_related.tex"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'claim-not-in-manuscript' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T144() {
    # Coverage: a citing sentence that asserts something about its source and
    # has no ledger row is reported; a credit-only citation is not a finding.
    # The ledgered row prompts about a qualifier the claim drops.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert d['citing_sentences'] == 3, d['citing_sentences']
assert d['ledger_rows'] == 1, d['ledger_rows']
assert 'unledgered-assertion' in kinds, kinds
assert 'voorhees2002' in [f['detail'] for f in d['findings'] if f['kind']=='unledgered-assertion'][0]
assert 'unledgered-credit' not in [f['kind'] for f in d['findings'] if not f.get('prompt')], kinds
assert any(f['kind']=='qualifier-dropped' and f.get('prompt') for f in d['findings']), kinds
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T145() {
    # Checking nothing is not a pass.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/sections"
    printf '\\section{Empty}\nNo citations here.\n' > "$tmp/sections/01.tex"
    printf 'claim\tcite_key\tsnippet\tsource_file\tlevel\n' > "$tmp/ledger.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['nothing_checked'] is True, d
" || return 1
    [ "$status" = "2" ] || { echo "expected exit 2, got $status"; return 1; }
}

test_T146() {
    # A negative claim about a source needs the full text, never an abstract.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    cat >> "$tmp/sections/02_related.tex" <<'EOF'
Buckley et al. did not test pooled judgments on image retrieval~\cite{buckley2007}.
EOF
    printf 'Buckley et al. did not test pooled judgments on image retrieval\tbuckley2007\tcan be biased in that they favor relevant documents\tevidence/buckley2007.txt\tabstract-only\n' >> "$tmp/ledger.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" --ledger "$tmp/ledger.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'negative-claim-without-fulltext' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

# --- Commit gate ------------------------------------------------------------
# Every one of the six wrong citations found in a real manuscript was introduced by
# a commit whose stated purpose was something else (a rewrite, a positioning
# pass, a page-count compression, a change of venue), and the structural check
# that ran at the time was green. The gate narrows the audit to what THIS change
# added, so it can sit on the commit rather than on the submission.
gate_fixture() {
    # $1 = dir. A git repo whose HEAD holds one ledgered assertion and one
    # credit. The caller then edits the working tree and gates against HEAD.
    ledger_fixture "$1"
    git -C "$1" init -q 2>/dev/null
    git -C "$1" config user.email t@example.com
    git -C "$1" config user.name Test
    git -C "$1" add -A 2>/dev/null
    git -C "$1" commit -qm base 2>/dev/null
}

test_T148() {
    # A newly added sentence that asserts something about its source, with no
    # ledger row, is a hard finding in gate mode.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    gate_fixture "$tmp"
    cat >> "$tmp/sections/02_related.tex" <<'EOF'
Chun et al. report that the standard test set under-counts correct matches~\cite{chun2022}.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'new-assertion-unledgered' in kinds, kinds
assert d['gate']['new_citing_sentences'] == 1, d.get('gate')
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T149() {
    # Sentences that did not change are not the gate's business, however many
    # unledgered assertions the manuscript already carries.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    gate_fixture "$tmp"
    printf '\n%% a comment, no new citation\n' >> "$tmp/sections/02_related.tex"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['gate']['new_citing_sentences'] == 0, d.get('gate')
assert d['hard_finding_count'] == 0, d['findings']
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T150() {
    # A method credit passes the gate only when the author has listed that key.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    gate_fixture "$tmp"
    printf 'bh1995\nclopper1934\n' > "$tmp/credits.txt"
    cat >> "$tmp/sections/02_related.tex" <<'EOF'
We report Clopper--Pearson intervals throughout~\cite{clopper1934}.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --credits "$tmp/credits.txt" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count'] == 0, d['findings']
assert d['gate']['new_citing_sentences'] == 1, d.get('gate')
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T151() {
    # The Lakens shape: a key already cited elsewhere in the manuscript, dropped
    # into a new sentence about a different procedure. Being present already is
    # not an account of the new use.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    gate_fixture "$tmp"
    cat >> "$tmp/sections/02_related.tex" <<'EOF'
A family-level permutation test rejects the null here~\cite{bh1995}.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'new-citation-unaccounted' in kinds or 'new-assertion-unledgered' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T152() {
    # Gating against a ref where the file did not exist makes every citing
    # sentence new; an empty ledger then cannot be a pass.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp"
    git -C "$tmp" init -q 2>/dev/null
    git -C "$tmp" config user.email t@example.com
    git -C "$tmp" config user.name Test
    printf 'placeholder\n' > "$tmp/README"
    git -C "$tmp" add -A 2>/dev/null
    git -C "$tmp" commit -qm empty 2>/dev/null
    ledger_fixture "$tmp"
    printf 'claim\tcite_key\tsnippet\tsource_file\tlevel\n' > "$tmp/ledger.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['gate']['new_citing_sentences'] == 3, d.get('gate')
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T153() {
    # The Lakens shape, with the key allowlisted. A credit is accepted for a
    # named procedure; the same key attached to a different procedure is not
    # accounted for by that entry.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    gate_fixture "$tmp"
    printf 'bh1995equivalence = equivalence bounds\n' > "$tmp/credits.txt"
    cat >> "$tmp/sections/02_related.tex" <<'EOF'
A family-level permutation test rejects the null here~\cite{bh1995equivalence}.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --gate-since HEAD --credits "$tmp/credits.txt" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'credit-outside-its-procedure' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

# --- T194-T195: method credits in the full scan -------------------------------
# The credits file was read only in gate mode, so over a whole manuscript a
# sentence the author had already accepted as a method credit ("we report
# bootstrap intervals") stayed in the unledgered-assertion count forever,
# and the count the author sees kept saying more was missing than was.
test_T194() {
    # An asserting sentence whose key is accepted for a procedure the sentence
    # names is a credit, not a missing ledger row; the finding carries the
    # whole sentence so a reader can act on it.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    printf 'voorhees2002 = absolute score\n' > "$tmp/credits.txt"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --credits "$tmp/credits.txt" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
by={f['kind']:f for f in d['findings']}
assert 'unledgered-assertion' not in by, [f['kind'] for f in d['findings']]
assert by['credited']['cite_key'] == 'voorhees2002', by.get('credited')
assert 'absolute score is not meaningful' in by['credited']['sentence'], by['credited']
assert 'Benjamini' in by['unledgered-credit']['sentence'], by['unledgered-credit']
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T195() {
    # A key may be accepted for more than one procedure; any one the sentence
    # names covers it. A procedure the sentence does not name covers nothing.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    ledger_fixture "$tmp"
    printf 'voorhees2002 = absolute score\nvoorhees2002 = pooling depth\n' > "$tmp/credits.txt"
    out=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/ledger.tsv" --credits "$tmp/credits.txt" --json 2>&1)
    status=$?
    printf 'voorhees2002 = pooling depth\n' > "$tmp/credits.txt"
    out2=$(python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir "$tmp" \
           --ledger "$tmp/ledger.tsv" --credits "$tmp/credits.txt" --json 2>&1)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'credited' in kinds and 'unledgered-assertion' not in kinds, kinds
" || return 1
    echo "$out2" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'unledgered-assertion' in kinds and 'credited' not in kinds, kinds
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

# --- Fails closed ----------------------------------------------------------
# A check that examines nothing and exits 0 is worse than no check: the green
# result is read as "looked and found nothing wrong". Three of these shipped.
test_T154() {
    # An empty bibliography verifies no reference. That is not a pass.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    : > "$tmp/empty.bib"
    out=$(python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/empty.bib" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['entries'] == 0, d
assert d['nothing_checked'] is True, d
" || return 1
    [ "$status" = "2" ] || { echo "expected exit 2, got $status"; return 1; }
}

test_T155() {
    # --allow-empty is the way to say an empty bibliography is expected here.
    local tmp status
    tmp=$(mktemp -d) || return 1
    : > "$tmp/empty.bib"
    python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib "$tmp/empty.bib" --allow-empty >/dev/null 2>&1
    status=$?
    rm -rf "$tmp"
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T156() {
    # An argument the script does not recognise must stop it. count-words took
    # an unknown positional, counted a different directory and exited 0.
    local status
    node .claude/skills/map/scripts/count-words.mjs --zzz-not-a-real-flag >/dev/null 2>&1
    status=$?
    [ "$status" != "0" ] || { echo "expected non-zero for an unknown flag, got 0"; return 1; }
    node .claude/skills/map/scripts/count-words.mjs /tmp >/dev/null 2>&1
    status=$?
    [ "$status" != "0" ] || { echo "expected non-zero for an unknown positional, got 0"; return 1; }
}

test_T157() {
    # The property itself, kept green: every check fails closed on an empty
    # target, and every script under a skill is registered as a check or not.
    local out status
    out=$(python3 scripts/check-fails-closed.py --json 2>&1)
    status=$?
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['problem_count'] == 0, d['problems']
assert d['checks_run'] >= 6, d
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

# --- Review findings --------------------------------------------------------
# /review produced "anchored findings" that nothing verified: the anchor was a
# section name or a quoted span, and an author acting on the report had no way
# to tell a real location from a plausible one. The anchor is now file:line, the
# source path is named, and a script resolves both.
review_fixture() {
    # $1 = dir. Two reviewed chapters and a source the findings can name.
    mkdir -p "$1/chapters" "$1/evidence"
    printf 'line one\nline two\nline three\n' > "$1/chapters/ch2.md"
    printf 'alpha\nbeta\n' > "$1/chapters/ch3.md"
    printf 'the archived passage\n' > "$1/evidence/source.txt"
    {
        printf '# reviewed: chapters/ch2.md, chapters/ch3.md\n'
        printf 'location\tsource\tproblem\n'
        printf 'chapters/ch2.md:2\tevidence/source.txt\tThe sentence says more than the passage it rests on.\n'
    } > "$1/findings.tsv"
}

test_T158() {
    # An anchor past the end of the file is the failure this replaces: a
    # location that reads as precise and resolves to nothing.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    review_fixture "$tmp"
    printf 'chapters/ch3.md:99\t-\tThe paragraph repeats the previous one.\n' >> "$tmp/findings.tsv"
    out=$(python3 .claude/skills/review/scripts/audit-review-findings.py --base-dir "$tmp" \
          --findings "$tmp/findings.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'anchor-line-out-of-range' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T159() {
    # No declaration of what was reviewed: zero findings then means nothing,
    # and must not read as a clean review.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    review_fixture "$tmp"
    printf 'location\tsource\tproblem\n' > "$tmp/findings.tsv"
    out=$(python3 .claude/skills/review/scripts/audit-review-findings.py --base-dir "$tmp" \
          --findings "$tmp/findings.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['nothing_checked'] is True, d
assert d['reviewed_files'] == 0, d
" || return 1
    [ "$status" = "2" ] || { echo "expected exit 2, got $status"; return 1; }
}

test_T160() {
    # A review that examined files and found nothing IS a pass. That is the
    # distinction the declaration buys.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    review_fixture "$tmp"
    {
        printf '# reviewed: chapters/ch2.md, chapters/ch3.md\n'
        printf 'location\tsource\tproblem\n'
    } > "$tmp/findings.tsv"
    out=$(python3 .claude/skills/review/scripts/audit-review-findings.py --base-dir "$tmp" \
          --findings "$tmp/findings.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['reviewed_files'] == 2 and d['finding_rows'] == 0, d
assert d['nothing_checked'] is False, d
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T161() {
    # A finding about a file the review never declared it read.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    review_fixture "$tmp"
    printf 'line\n' > "$tmp/chapters/ch9.md"
    printf 'chapters/ch9.md:1\t-\tThis chapter was never opened.\n' >> "$tmp/findings.tsv"
    out=$(python3 .claude/skills/review/scripts/audit-review-findings.py --base-dir "$tmp" \
          --findings "$tmp/findings.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'finding-outside-reviewed-set' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T162() {
    # The source a finding rests on must be on disk, or the finding rests on
    # the reviewer's memory.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    review_fixture "$tmp"
    printf 'chapters/ch3.md:1\tevidence/not-there.txt\tThe claim is not in the source.\n' >> "$tmp/findings.tsv"
    out=$(python3 .claude/skills/review/scripts/audit-review-findings.py --base-dir "$tmp" \
          --findings "$tmp/findings.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'source-missing' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

# --- Number ledger ----------------------------------------------------------
# The manuscript already guards numbers one way: a frequency table of numeric
# tokens taken before and after a prose pass, which answers "did this pass move
# a number". It cannot answer "is this number the artifact's", nor "does the
# sentence carry the scope the number is only true within". Both have failed on
# real work: a ratio true of 15 cells written as if it were true of all of them,
# and a pooled figure quoted alone against the manuscript's own warning.
number_fixture() {
    # $1 = dir. One reported number, its artifact, and a scope word.
    mkdir -p "$1/sections" "$1/results"
    cat > "$1/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
The top-1 rate falls from $30.2$ to $2.5$ times chance.
EOF
    printf 'condition,share\npooled,0.635\nk1,0.210\n' > "$1/results/variance.csv"
    printf 'printed\tin_artifact\tscope\tartifact\tlocator\n' > "$1/numbers.tsv"
    printf '63.5\t0.635\tpooled\tresults/variance.csv\tpooled,0.635\n' >> "$1/numbers.tsv"
}

test_T163() {
    # The locator must be verbatim in the artifact, or the number rests on
    # nothing that can be re-read.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    printf '30.2\t30.2\t-\tresults/variance.csv\tcells,30.2\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'locator-not-in-artifact' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T164() {
    # A sentence that reports the number without the scope it is only true
    # within. This is the failure the frequency table cannot see.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The share is $63.5\%$ across all four conditions.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'scope-missing' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T165() {
    # The ledgered number is no longer in the manuscript: the binding is stale.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled variance share is $91.9\%$ across all five conditions.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'number-not-in-manuscript' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T166() {
    # A locator that does not itself carry the number: the row looks bound and
    # binds nothing.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    printf 'printed\tin_artifact\tscope\tartifact\tlocator\n' > "$tmp/numbers.tsv"
    printf '63.5\t0.635\tpooled\tresults/variance.csv\tcondition,share\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'value-not-in-locator' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T167() {
    # A clean ledger passes, and reports how many reported numbers carry no row.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count'] == 0, d['findings']
assert d['ledger_rows'] == 1 and d['nothing_checked'] is False, d
assert any(f['kind'] == 'unledgered-number' for f in d['findings']), [f['kind'] for f in d['findings']]
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T168() {
    # The two columns exist because the figure writes 0.635 and the prose prints
    # 63.5%. A pair that is neither equal nor that relation is a finding, and
    # the relation is recorded rather than inferred.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    printf 'printed\tin_artifact\tscope\tartifact\tlocator\n' > "$tmp/numbers.tsv"
    printf '63.5\t0.210\tpooled\tresults/variance.csv\tk1,0.210\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=[f['kind'] for f in d['findings']]
assert 'printed-artifact-mismatch' in kinds, kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T198() {
    # A ledger row's artifact is a source, not prose. With the table read as
    # prose, cutting the only sentence that reports a number left the row
    # looking current, because the table itself still carried the number.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    mkdir -p "$tmp/tables"
    cat > "$tmp/tables/rates.tex" <<'EOF'
\begin{tabular}{lr} top-1 & 30.2 \\ \end{tabular}
EOF
    printf '30.2\t30.2\t-\ttables/rates.tex\ttop-1 & 30.2\n' >> "$tmp/numbers.tsv"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
EOF
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
stale=[f for f in d['findings'] if f['kind']=='number-not-in-manuscript']
assert [f['number'] for f in stale] == ['30.2'], d['findings']
assert not any(f['location'].startswith('tables/') for f in d['findings']), d['findings']
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T199() {
    # 2{,}048 is one number. Read digit by digit it was "614", which no
    # sentence reports, so a row for 2,048 could never bind and the coverage
    # list named a number the manuscript does not contain.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
The pool holds $2{,}048$ distractors and 3,071 images in all.
EOF
    printf 'pool,2048\n' >> "$tmp/results/variance.csv"
    printf '2,048\t2048\t-\tresults/variance.csv\tpool,2048\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count'] == 0, d['findings']
nums=[f['number'] for f in d['findings'] if f['kind']=='unledgered-number']
assert '3,071' in nums and '048' not in nums and '071' not in nums, nums
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
}

test_T200() {
    # The text prints an artifact's 17.36 as 17.4: exact rounding to the
    # printed precision is a recorded relation, and a digit that rounding
    # cannot produce (17.3) is still a mismatch.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
Siblings take $17.4\%$ of slots, and the ratio is 12.3 times.
EOF
    printf 'siblings,17.36\nratio,12.3456\n' >> "$tmp/results/variance.csv"
    printf '17.4\t17.36\t-\tresults/variance.csv\tsiblings,17.36\n' >> "$tmp/numbers.tsv"
    printf '12.3\t12.3456\t-\tresults/variance.csv\tratio,12.3456\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    sed -i.bak 's/^17.4	17.36/17.3	17.36/' "$tmp/numbers.tsv"
    sed -i.bak 's/17\.4\\%/17.3\\%/' "$tmp/sections/06_results.tex"
    bad=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['hard_finding_count'] == 0, d['findings']
" || return 1
    [ "$status" = "0" ] || { echo "expected exit 0, got $status"; return 1; }
    echo "$bad" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert [f['number'] for f in d['findings'] if f['kind']=='printed-artifact-mismatch'] == ['17.3'], d['findings']
" || return 1
}

test_T201() {
    # A number printed in two places drifts in one of them. "Is the value
    # still reported somewhere" passed on the other copy; with the copies
    # column the count of reporting sentences is checked.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
Summed over conditions, the pooled share is $63.9\%$.
EOF
    printf 'printed\tin_artifact\tscope\tartifact\tlocator\tcopies\n' > "$tmp/numbers.tsv"
    printf '63.5\t0.635\tpooled\tresults/variance.csv\tpooled,0.635\t2\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert [f['number'] for f in d['findings'] if f['kind']=='copies-changed'] == ['63.5'], d['findings']
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T202() {
    # A scope or locator ending in a digit must not continue into another
    # digit: K=1 is not in "K=10", and a locator ending 0.635 is not in a
    # file that now writes 0.6357.
    local tmp out status
    tmp=$(mktemp -d) || return 1
    number_fixture "$tmp"
    cat > "$tmp/sections/06_results.tex" <<'EOF'
\section{Results}
The pooled share is $63.5\%$ across all four conditions.
The model explains 71.2\% of the variance at K=10.
EOF
    printf 'condition,share\npooled,0.6357\nk1,0.712\n' > "$tmp/results/variance.csv"
    printf 'printed\tin_artifact\tscope\tartifact\tlocator\n' > "$tmp/numbers.tsv"
    printf '63.5\t0.635\tpooled\tresults/variance.csv\tpooled,0.635\n' >> "$tmp/numbers.tsv"
    printf '71.2\t0.712\tK=1\tresults/variance.csv\tk1,0.712\n' >> "$tmp/numbers.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir "$tmp" \
          --ledger "$tmp/numbers.tsv" --json 2>&1)
    status=$?
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json,sys
d=json.load(sys.stdin)
kinds=sorted((f['kind'], f['number']) for f in d['findings'] if f['kind'] != 'unledgered-number')
assert kinds == [('locator-not-in-artifact', '63.5'), ('scope-missing', '71.2')], kinds
" || return 1
    [ "$status" = "1" ] || { echo "expected exit 1, got $status"; return 1; }
}

test_T203() {
    # A baseline file whose text extracted as symbols is not a document of
    # the baseline: it is named under baseline_garbled and not counted.
    local tmp out
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib, itertools, random
d = pathlib.Path(sys.argv[1])
toks = ["".join(c) for c in itertools.product("abcdefgh", repeat=3)]
(d / "target.txt").write_text("".join("The %s stage scored the pool and kept the rank. " % w for w in toks[:220]))
others = ["Sediment cores record winter runoff in annual layers that are counted twice. ",
          "The compiler rewrites loops whose bounds are known and emits a specialised body. ",
          "Participants rated photographs on a scale and then described what they noticed. ",
          "Orbital decay below six hundred kilometres is dominated by atmospheric drag. ",
          "Enzyme activity fell above forty degrees and did not recover on cooling. "]
for i, body in enumerate(others):
    (d / "base" / ("other%d.txt" % i)).write_text(body * 140)
rnd = random.Random(7)
junk = " ".join("".join(rnd.choice("!#%$&'()*+,-/0123456789:;<=>") for _ in range(4)) for _ in range(2500))
(d / "base" / "garbled.txt").write_text(junk)
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py \
            --target "$tmp/target.txt" --baseline "$tmp/base" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert [g['file'] for g in d['baseline_garbled']] == ['garbled.txt'], d['baseline_garbled']
assert d['baseline_documents'] == 5, d['baseline_documents']
"
}

test_T204() {
    # A proposed rewrite is read against the sentence it replaces: one that grows
    # and gains a colon and a relative clause is flagged; one that got shorter
    # and plainer is not.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    printf 'id\told\tnew\n' > "$tmp/pairs.tsv"
    printf 'a\tThe gauge reads the river level twice a day.\tThe gauge, which the survey installed in spring, reads the river level twice a day: once at dawn and once at dusk.\n' >> "$tmp/pairs.tsv"
    printf 'b\tThe survey counted the bridges that had cracked piers in the northern district.\tThe survey counted bridges with cracked piers.\n' >> "$tmp/pairs.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --json 2>/dev/null)
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 1 ] || return 1
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
by = {r['where']: r for r in d['sentences']}
assert d['changed'] == 2 and d['flagged'] == 1, (d['changed'], d['flagged'])
assert {'longer', 'colon', 'clause'} <= set(by['a']['flags']), by['a']['flags']
assert by['b']['flags'] == [], by['b']['flags']
"
}

test_T205() {
    # Two versions of a draft: only the sentences that changed are read, a
    # revision is paired with the sentence it replaced, a dot directory beside
    # the draft is not part of it, and a draft identical to its base reports no
    # change rather than failing.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base" "$tmp/draft/.awt-base"
    printf '%s\n' 'Sediment cores record winter runoff in annual layers. The layers are counted twice by separate readers. Counting stops at the ash band.' > "$tmp/base/ch.md"
    printf '%s\n' 'Sediment cores record winter runoff in annual layers. The layers are counted twice by separate readers; disagreements go to a third. Counting stops at the ash band. A second core confirms the count.' > "$tmp/draft/ch.md"
    printf '%s\n' 'This sentence sits in a dot directory and is not part of the draft at all.' > "$tmp/draft/.awt-base/ch.md"
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --target "$tmp/draft" --base "$tmp/base" --json 2>/dev/null)
    code=$?
    [ "$code" -eq 1 ] || { rm -rf "$tmp"; return 1; }
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d['compared']
assert (d['changed'], c['revised'], c['added']) == (2, 1, 1), c
rev = next(r for r in d['sentences'] if r['kind'] == 'revised')
assert rev['old'].startswith('The layers are counted twice'), rev['old']
assert 'semicolon' in rev['flags'], rev['flags']
assert not any('dot directory' in r['new'] for r in d['sentences'])
" || { rm -rf "$tmp"; return 1; }
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --target "$tmp/base" --base "$tmp/base" --json 2>/dev/null)
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 0 ] || return 1
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['changed'] == 0 and d['flagged'] == 0, d['compared']
"
}

test_T206() {
    # Against a venue corpus a rewrite is placed among the venue's sentences: one
    # that grows past the venue's 90th percentile is flagged for that too. A
    # corpus too small for percentiles is refused (exit 2), never read as a pass.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/venue" "$tmp/tiny"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib, itertools
d = pathlib.Path(sys.argv[1])
words = ["".join(c) for c in itertools.product("abcdefg", repeat=3)]
for i in range(6):
    sents = []
    for j in range(200):
        w = words[(i * 200 + j) % len(words)]
        sents.append("The %s stage kept the %s rank in the pool today." % (w, w))
    (d / "venue" / ("doc%d.txt" % i)).write_text(" ".join(sents))
(d / "tiny" / "doc0.txt").write_text(" ".join(["The pool kept the rank of the stage today."] * 60))
long_new = "The station logged the level of the river at dawn and at dusk on every day of the season " \
           "for the survey team and the regional office and the two partner universities that funded the gauge."
(d / "pairs.tsv").write_text("id\told\tnew\nx\tThe station logged the river level at dawn.\t%s\n" % long_new)
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --baseline "$tmp/venue" --json 2>/dev/null)
    code=$?
    [ "$code" -eq 1 ] || { rm -rf "$tmp"; return 1; }
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['venue']['documents'] == 6 and d['venue']['sentences'] >= 1000, d['venue']
flags = d['sentences'][0]['flags']
assert 'long_for_venue' in flags and 'longer' in flags, flags
" || { rm -rf "$tmp"; return 1; }
    python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --baseline "$tmp/tiny" --json >/dev/null 2>&1
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 2 ]
}

test_T207() {
    # Every kind of addition a rewrite can make is flagged by name, one row each,
    # and a rewrite that only gets shorter is not. Clauses are counted as gained:
    # trading "because" for "which" is an added clause even though the count is
    # unchanged. Modifiers and adverbs are counted net: swapping one for another
    # adds none.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
rows = [
    ("longer", "The gauge reads the river twice a day.", "The gauge reads the level of the river twice a day in spring."),
    ("comma", "The survey counted bridges in the north.", "The survey counted bridges in the north, the port and the hills."),
    ("colon", "The survey counted three kinds of bridge.", "The survey counted three kinds: stone, iron and timber."),
    ("semicolon", "The survey counted stone bridges in the north.", "The survey counted stone bridges; the timber ones were skipped."),
    ("dash", "The survey counted stone bridges in the north.", "The survey counted stone bridges --- the old ones --- in the north."),
    ("parenthesis", "The survey counted stone bridges in the north.", "The survey counted stone bridges (the old ones) in the north."),
    ("clause", "The gauge failed because the river froze.", "The gauge failed in the frost, which froze the river."),
    ("adverb", "The gauge reads the river twice a day.", "The gauge still reads the river only twice a day."),
    ("modifier", "The survey counted bridges in the north.", "The survey counted the damaged bridges collected from the north."),
    ("prepositions", "The survey counted bridges.", "The survey counted bridges of stone in the north."),
    ("opener", "The gauge failed in the frost.", "When the frost came the gauge failed."),
    ("merged", "The gauge failed. The river froze.", "The gauge failed and the river froze."),
    ("clean", "The survey counted the bridges that had cracked piers in the northern district.", "The survey counted bridges with cracked piers."),
    ("swap", "The survey used a stone-age baseline for the count.", "The survey used an iron-age baseline for the count."),
]
lines = ["id\told\tnew"] + ["\t".join(r) for r in rows]
(pathlib.Path(sys.argv[1]) / "pairs.tsv").write_text("\n".join(lines) + "\n")
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --json 2>/dev/null)
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 1 ] || return 1
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
by = {r['where']: r for r in d['sentences']}
for flag in ('longer', 'comma', 'colon', 'semicolon', 'dash', 'parenthesis', 'clause', 'adverb', 'modifier',
             'prepositions', 'opener', 'merged'):
    assert flag in by[flag]['flags'], (flag, by[flag]['flags'])
assert by['clause']['added']['clauses'] == ['which'], by['clause']['added']
assert set(by['adverb']['added']['adverbs']) == {'still', 'only'}, by['adverb']['added']
assert by['clean']['flags'] == [], by['clean']['flags']
assert by['swap']['flags'] == [], by['swap']['flags']
assert d['limits'].startswith('not measured'), d['limits']
"
}

test_T208() {
    # Between two versions every changed sentence is judged. A sentence split in
    # two is read as the old sentence against both pieces; a short sentence
    # expanded past recognition is still a revision; a new sentence with no
    # predecessor is held to the default ceilings when no venue is given, and
    # the report says so.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base" "$tmp/draft"
    printf '%s\n' 'The team logged the river level at the gauge each morning for the regional office that funds the gauge. Floods are rare. The office keeps the logs.' > "$tmp/base/ch.md"
    printf '%s\n' 'The team logged the river level at the gauge each morning. The regional office, which funds the gauge, reads the logs. Floods, which the county still fears, are rare: one per decade. The office keeps the logs. Staff also checked salinity (roughly) because farmers asked. Pumps rust; crews repaint them.' > "$tmp/draft/ch.md"
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --target "$tmp/draft" --base "$tmp/base" --json 2>/dev/null)
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 1 ] || return 1
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
kinds = {r['kind']: r for r in d['sentences']}
assert {r['kind'] for r in d['sentences']} == {'split', 'revised', 'added'}, [(r['kind'], r['new'][:30]) for r in d['sentences']]
assert kinds['split']['pieces'] == 2 and 'clause' in kinds['split']['flags'], kinds['split']
assert {'colon', 'clause', 'adverb'} <= set(kinds['revised']['flags']), kinds['revised']['flags']
added = {r['new'][:5]: r for r in d['sentences'] if r['kind'] == 'added'}
assert {'parenthesis', 'dense_for_venue'} <= set(added['Staff']['flags']), added['Staff']['flags']
assert 'semicolon' in added['Pumps']['flags'], added['Pumps']['flags']
assert d['added_without_venue'] == 2, d['added_without_venue']
assert all(r['flags'] for r in d['sentences']), 'no changed sentence passes unread'
"
}

test_T209() {
    # LaTeX is read the way a reader sees it: a change inside a list item or a
    # figure caption is a changed sentence; reference commands, inline comments
    # and inline math do not make colons or parentheses; a stray quotation mark
    # in a pairs file stays text and does not swallow the rows after it.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    mkdir -p "$tmp/base" "$tmp/draft"
    python3 - "$tmp" <<'PYEOF'
import sys, pathlib
d = pathlib.Path(sys.argv[1])
base = r"""\section{Method}
The gauge reads the river twice a day, as \cref{sec:setup} explains. % TODO: link
\begin{itemize}
\item The first gauge sits at the bridge
\item The second gauge sits in the reeds upstream
\end{itemize}
\begin{figure}\centering\includegraphics{g.pdf}
\caption{The gauge at the bridge in winter.}\end{figure}
The level $f(x)$ rises in spring.
"""
draft = base.replace("The first gauge sits at the bridge",
                     "The first gauge, which the county bought, sits at the bridge; it rusted in March")
draft = draft.replace("The gauge at the bridge in winter.", "The gauge at the bridge in winter: it froze twice.")
draft = draft.replace("rises in spring.", "rises in spring, see \\autoref{fig:g}.")
(d / "base" / "ch.tex").write_text(base)
(d / "draft" / "ch.tex").write_text(draft)
(d / "pairs.tsv").write_text('id\told\tnew\nq1\tThe gauge reads the river.\t"The gauge reads the river twice.\n'
                             'q2\tThe office keeps logs.\tThe office keeps the logs.\n')
PYEOF
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --target "$tmp/draft" --base "$tmp/base" --json 2>/dev/null)
    code=$?
    [ "$code" -eq 1 ] || { rm -rf "$tmp"; return 1; }
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
item = next(r for r in d['sentences'] if 'county' in r['new'])
cap = next(r for r in d['sentences'] if 'froze' in r['new'])
assert {'semicolon', 'clause'} <= set(item['flags']), item['flags']
assert 'reeds' not in item['new'], 'a list item without a full stop is still its own sentence'
assert 'colon' in cap['flags'], cap['flags']
level = [r for r in d['sentences'] if 'rises' in r['new']]
assert all('colon' not in r['flags'] and 'parenthesis' not in r['flags'] for r in level), level
" || { rm -rf "$tmp"; return 1; }
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --json 2>/dev/null)
    rm -rf "$tmp"
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['compared']['pairs'] == 2, d['compared']
"
}

test_T210() {
    # Rewrites that get plainer are not flagged: a preposition that looks like a
    # conjunction ("since 2019", "after training", "once a year"), an adjective
    # that ends in -ly, a comma that replaces a semicolon, a proper noun ending
    # in -ly.
    local tmp out code
    tmp=$(mktemp -d) || return 1
    printf 'id\told\tnew\n' > "$tmp/pairs.tsv"
    printf 'a\tThe archive has grown steadily for a decade.\tThe archive has grown since 2019.\n' >> "$tmp/pairs.tsv"
    printf 'b\tThe model was tested at the end of the training schedule.\tThe model was tested after training.\n' >> "$tmp/pairs.tsv"
    printf 'c\tThe team checks the gauge each year.\tThe team checks the gauge once a year.\n' >> "$tmp/pairs.tsv"
    printf 'd\tA second failure is possible.\tA second failure is likely.\n' >> "$tmp/pairs.tsv"
    printf 'e\tThe gauge failed; the river froze; the team left.\tThe gauge failed, and the team left.\n' >> "$tmp/pairs.tsv"
    printf 'f\tThe second coder was a student.\tThe second coder was Kelly.\n' >> "$tmp/pairs.tsv"
    out=$(python3 .claude/skills/audit/scripts/audit-sentence-changes.py --pairs "$tmp/pairs.tsv" --json 2>/dev/null)
    code=$?
    rm -rf "$tmp"
    [ "$code" -eq 0 ] || { echo "$out" | head -40; return 1; }
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['changed'] == 6 and d['flagged'] == 0, [(r['where'], r['flags']) for r in d['sentences']]
"
}

run_test "T138 claim positioning recognises Harvard author-year in Markdown" test_T138
run_test "T142 claim ledger: a snippet that is not in the archived source" test_T142
run_test "T143 claim ledger: a claim that is no longer in the manuscript" test_T143
run_test "T144 claim ledger: coverage of citing sentences and the qualifier prompt" test_T144
run_test "T145 claim ledger: checking nothing is not a pass" test_T145
run_test "T146 claim ledger: a negative claim needs the full text" test_T146
run_test "T147 claim ledger: citing sentences with an empty ledger is not a pass" test_T147
run_test "T148 commit gate: a new assertion with no ledger row" test_T148
run_test "T149 commit gate: unchanged sentences are not this change's business" test_T149
run_test "T150 commit gate: a credit passes only when the key is listed" test_T150
run_test "T151 commit gate: an existing key used in a new sentence is unaccounted" test_T151
run_test "T152 commit gate: gating against a ref without the file" test_T152
run_test "T153 commit gate: a credit does not cover a different procedure" test_T153
run_test "T154 verify-refs: an empty bibliography is not a pass" test_T154
run_test "T155 verify-refs: --allow-empty says the emptiness is expected" test_T155
run_test "T156 count-words: an unrecognised argument stops it" test_T156
run_test "T157 every check fails closed and every script is registered" test_T157
run_test "T158 review findings: an anchor past the end of the file" test_T158
run_test "T159 review findings: no declaration of what was reviewed" test_T159
run_test "T160 review findings: files read and nothing found is a pass" test_T160
run_test "T161 review findings: a finding about a file never declared read" test_T161
run_test "T162 review findings: the named source must be on disk" test_T162
run_test "T163 number ledger: the locator must be verbatim in the artifact" test_T163
run_test "T164 number ledger: a number reported without its scope" test_T164
run_test "T165 number ledger: the number is no longer in the manuscript" test_T165
run_test "T166 number ledger: a locator that does not carry the artifact value" test_T166
run_test "T167 number ledger: a clean ledger passes and lists what it misses" test_T167
run_test "T168 number ledger: printed and artifact values that do not relate" test_T168
run_test "T139 a baseline holding a draft of the target withholds percentiles" test_T139
run_test "T140 the overlap waiver restores percentiles without asserting the precondition" test_T140
run_test "T169 the fidelity audit says what it did not read, and how much it did" test_T169
run_test "T170 every baseline candidate is accounted for in the report" test_T170
run_test "T171 per-section metrics report their absence instead of vanishing" test_T171
run_test "T172 a wrapped keyword is one term, and an unused one says so" test_T172
run_test "T173 a bracketed natbib locator is still a citation" test_T173
run_test "T174 a refused novelty claim is not a novelty claim" test_T174
run_test "T175 the venue frame is recorded and the registrar decides membership" test_T175
run_test "T176 a corpus under the floor fails closed" test_T176
run_test "T177 --dry-run builds the frame and fetches nothing" test_T177
run_test "T178 session scan: no remote in sight is not a pass" test_T178
run_test "T179 session scan: a branch another session merged and deleted" test_T179
run_test "T180 session scan: a foreign commit in the push range" test_T180
run_test "T181 session scan: a staged file older than the session" test_T181
run_test "T182 session scan: the transcript's first user record is the start" test_T182
run_test "T183 session scan: an upstream that is a different branch" test_T183
run_test "T184 the suite header counts the tests this file runs" test_T184
run_test "T185 public-content audit: a base-dir with no public surface is not a pass" test_T185
run_test "T186 public-content audit: the count is the files read, none skipped for encoding" test_T186
run_test "T187 public-content audit: the real tree's count clears an independent floor" test_T187
run_test "T188 the scripts/ audits fail closed on an empty base-dir" test_T188
run_test "T189 every numbered mention of the skill catalogue matches the skills on disk" test_T189
run_test "T198 number ledger: an artifact file is a source, never prose" test_T198
run_test "T199 number ledger: a number with thousands separators is one number" test_T199
run_test "T200 number ledger: exact rounding is a relation, other digits are not" test_T200
run_test "T201 number ledger: a copy that drifts while another copy holds" test_T201
run_test "T202 number ledger: scopes and locators end at a digit boundary" test_T202
run_test "T203 prose fingerprint: a baseline file that extracted as symbols is named, not counted" test_T203
run_test "T204 changed sentences: a proposed rewrite is read against the sentence it replaces" test_T204
run_test "T205 changed sentences: only what changed between two versions is read, a dot directory is not the draft" test_T205
run_test "T206 changed sentences: a rewrite is placed among the venue's sentences; a corpus too small is refused" test_T206
run_test "T207 changed sentences: each kind of addition is flagged by name; a plainer rewrite and a term swap are not" test_T207
run_test "T208 changed sentences: splits, expansions and additions between two versions are all judged" test_T208
run_test "T209 changed sentences: list items and captions are read; references, comments and math make no punctuation" test_T209
run_test "T210 changed sentences: prepositions, -ly adjectives, a comma for a semicolon and a name are not flagged" test_T210
run_test "T190 every path the README's structure block names exists on disk" test_T190
run_test "T191 writing-loop engine tests pass (hermetic fixtures only)" test_T191
run_test "T192 every writing-loop mutation turns its named test red" test_T192
run_test "T193 experimental/ is audited and carries no home-directory paths" test_T193
run_test "T194 claim ledger: an accepted method credit is not a missing row in the full scan" test_T194
run_test "T195 claim ledger: a key may be credited for several procedures, only a named one covers" test_T195

header ""
if [[ "$RUN_RETIRED" == "1" ]]; then
    printf "  %s on live surfaces, %s on bundles retired under archive/skills/\n" \
        "$LIVE_PASSES" "$RETIRED_PASSES"
else
    printf "  %s on live surfaces; %s registered for bundles retired under archive/skills/ not run (AWT_TEST_RETIRED=1 or make test-all runs them)\n" \
        "$LIVE_PASSES" "$RETIRED_SKIPPED"
fi
if [[ ${#FAIL_LIST[@]} -eq 0 ]]; then
    pass "all $PASSES tests that ran passed."
    exit 0
else
    printf "\n\033[31m%d test(s) failed:\033[0m\n" "${#FAIL_LIST[@]}"
    for t in "${FAIL_LIST[@]}"; do printf "  - %s\n" "$t"; done
    exit 1
fi
