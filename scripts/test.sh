#!/usr/bin/env bash
# scripts/test.sh — runs the regression test suite (41 automated tests: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features) for academic-writing-toolkit.
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
source "$SCRIPT_DIR/lib.sh"

cd "$REPO_ROOT"

PASSES=0
FAIL_LIST=()

run_test() {
    local name="$1"
    local fn="$2"
    if "$fn"; then
        pass "$name"
        PASSES=$((PASSES+1))
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
    grep -qE '^allowed-tools:.*\bRead\b' "$REPO_ROOT/.claude/skills/verify/SKILL.md" || return 1
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
    python3 scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --json >/dev/null
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
    out=$(python3 scripts/verify-refs.py --bib "$tmp/refs/bad.bib" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'duplicate-key' in kinds and 'arxiv-invalid' in kinds"
}

test_T42() {
    for skill in style logic-review verify-refs; do
        [[ -f "$REPO_ROOT/.claude/skills/$skill/SKILL.md" ]] || return 1
        [[ -L "$REPO_ROOT/.agents/skills/$skill" ]] || return 1
        [[ "$(readlink "$REPO_ROOT/.agents/skills/$skill")" == "../../.claude/skills/$skill" ]] || return 1
    done
}

test_T43() {
    grep -q "/verify-refs" "$REPO_ROOT/README.md" || return 1
    grep -q "/style" "$REPO_ROOT/README.md" || return 1
    grep -q "/logic-review" "$REPO_ROOT/README.md" || return 1
    grep -q "local agent skill" "$REPO_ROOT/README.md"
}

test_T44() {
    python3 scripts/audit-public-content.py --base-dir "$REPO_ROOT" >/dev/null
}

# ----------------------------------------------------------------------------
header "Running spec §6 acceptance tests..."
header ""

# T1 (fresh-clone simulation) and T6 (PATH manipulation) and T7 (EDITOR=true)
# are skipped here because they require either a separate clone or PATH/env
# mutation that would interfere with parallel test runs.
# Run those manually per spec §6 if desired; they document the contract but
# aren't part of the automated harness.

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

header ""
if [[ ${#FAIL_LIST[@]} -eq 0 ]]; then
    pass "all $PASSES tests passed."
    exit 0
else
    printf "\n\033[31m%d test(s) failed:\033[0m\n" "${#FAIL_LIST[@]}"
    for t in "${FAIL_LIST[@]}"; do printf "  - %s\n" "$t"; done
    exit 1
fi
