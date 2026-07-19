#!/usr/bin/env bash
# scripts/test.sh — runs 149 regression tests (T2-T5 and T8-T152), including T112-T115 argument and clean-room review governance, T116-T124 project-intent control, and T125-T152 research-relation, focus-review, assistant routing, claim-licence locking, OpenAI submission, and reproducible release gates.
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
TEST_ONLY="${TEST_ONLY:-}"

run_test() {
    local name="$1"
    local fn="$2"
    local test_id="${name%% *}"
    if [[ -n "$TEST_ONLY" && " $TEST_ONLY " != *" $test_id "* ]]; then
        return 0
    fi
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
    grep -q "/academic-writing-assistant" "$REPO_ROOT/README.md" || return 1
    grep -q "/verify-refs" "$REPO_ROOT/README.md" || return 1
    grep -q "/human-eval-handoff-repair" "$REPO_ROOT/README.md" || return 1
    grep -q "/argument-governance" "$REPO_ROOT/README.md" || return 1
    grep -q "/peer-review" "$REPO_ROOT/README.md" || return 1
    grep -q "/self-review" "$REPO_ROOT/README.md" || return 1
    grep -q "/style" "$REPO_ROOT/README.md" || return 1
    grep -q "/logic-review" "$REPO_ROOT/README.md" || return 1
    grep -q "local agent skill" "$REPO_ROOT/README.md" || return 1
    grep -q "scripts/audit-citations.py --base-dir" "$REPO_ROOT/README.md" || return 1
    grep -q "scripts/audit-british-english.py --base-dir" "$REPO_ROOT/README.md" || return 1
    grep -q "scripts/audit-logic.py --base-dir" "$REPO_ROOT/README.md" || return 1
    grep -q "scripts/verify-refs.py --bib" "$REPO_ROOT/README.md" || return 1
    grep -q -- "--metadata-dir" "$REPO_ROOT/README.md" || return 1
    ! grep -q "room for explicit online checks" "$REPO_ROOT/README.md" || return 1
    ! grep -R -q "docs/superpowers" "$REPO_ROOT/README.md" "$REPO_ROOT/docs" "$REPO_ROOT/.claude/skills" || return 1
    ! grep -R -q "8 academic writing skills" "$REPO_ROOT/docs" || return 1
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
    out=$(python3 scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json) || {
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
    out=$(python3 scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json 2>&1)
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
    out=$(python3 scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json 2>&1)
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
    out=$(python3 scripts/verify-refs.py --bib "$tmp/refs/paper.bib" --online --metadata-dir "$tmp/meta" --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(v['source']=='arxiv' for v in d['verified'])"
}

test_T49() {
    python3 scripts/verify-refs.py --help | grep -q -- "--online" || return 1
    python3 scripts/verify-refs.py --help | grep -q -- "--metadata-dir"
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
    out=$(python3 scripts/verify-refs.py "$tmp/refs/papers.md" --json) || {
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
    [[ -f "$use_cases/choose-product-surface.md" ]] || return 1

    grep -q "agent-native" "$REPO_ROOT/README.md" || return 1
    grep -q "local-first" "$REPO_ROOT/README.md" || return 1
    grep -q "10-minute demo" "$REPO_ROOT/README.md" || return 1
    grep -q "docs/use-cases" "$REPO_ROOT/README.md" || return 1
    grep -q "examples/demo-project" "$REPO_ROOT/README.md" || return 1
}

test_T62() {
    local demo="$REPO_ROOT/examples/demo-project"
    local out

    python3 scripts/verify-refs.py --bib "$demo/references.bib" --json >/dev/null || return 1
    python3 .claude/skills/evidence-review/scripts/check_review_package.py "$demo" --strict >/dev/null || return 1
    out=$(python3 .claude/skills/release-governance/scripts/check_release_packet.py "$demo" --json) || return 1
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
    root / "docs/use-cases/choose-product-surface.md",
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

_make_valid_relation_argument_packet() {
    local tmp="$1"
    mkdir -p "$tmp/evidence"
    cat > "$tmp/evidence/intent_register.csv" <<'EOF'
intent_id,paper_title,central_problem,target_venue,target_readers,field_positioning,core_gap,current_dominant_narrative,narrative_to_correct,why_now,main_contribution_ids,boundary_statement,success_criterion,reviewer_risk_level,notes
I1,Example paper,Current reviews lack traceable argument checks,Example venue,reviewers and authors,writing tools,Gap-contribution and claim-evidence links are implicit,Manuscripts can be judged by citation count alone,Argument systems need explicit links,Review workflows increasingly use agents,CON-001,This is a governance aid not a scientific validity guarantee,All main claims are source anchored,medium,fixture
EOF
    cat > "$tmp/evidence/contribution_chain.csv" <<'EOF'
contribution_id,intent_id,gap_id,gap_statement,gap_type,why_gap_matters,insight,contribution_statement,contribution_type,method_or_artifact_id,primary_claim_ids,required_evidence_type,current_evidence_ids,evidence_coverage,limitation,boundary_language,reviewer_defense_note
CON-001,I1,GAP-001,Manuscript claims often lack explicit hierarchy,governance_gap,Flat claims hide weak evidence,Argument structure can be checked separately from scientific validity,We provide an argument-governance schema,governance_framework,ART-001,CLM-001,governance schema evidence,EVD-001,adequate,Does not prove manuscript quality,Validates structure only,Checker reports structural issues
EOF
    cat > "$tmp/evidence/claim_hierarchy.csv" <<'EOF'
claim_id,parent_claim_id,root_intent_id,contribution_id,section_id,claim_level,claim_role,claim_text,depends_on_claim_ids,evidence_requirement,evidence_ids,citation_keys,evidence_status,evidence_strength,support_balance,system_role,overclaim_risk,boundary_language,revision_action
CLM-000,,I1,,intro,paper_thesis,interpretive_claim,Argument systems need explicit governance,,packet evidence,EVD-001,,verified_full_text_supported,adequate,adequately_supported,states_implication,low,Within the packet scope,none
CLM-001,CLM-000,I1,CON-001,intro,contribution_claim,artifact_claim,The schema links gaps contributions claims data results and innovation evidence,,schema evidence,EVD-001,,governance_support_only,adequate,adequately_supported,answers_gap,low,Structure only,none
CLM-002,CLM-001,I1,CON-001,methods,paragraph_claim,method_claim,The checker validates required links,,script evidence,EVD-001,,governance_support_only,adequate,adequately_supported,justifies_method,low,It does not judge science,none
EOF
    cat > "$tmp/evidence/argument_system_map.csv" <<'EOF'
node_id,parent_node_id,node_type,node_label,linked_gap_id,linked_contribution_id,linked_claim_id,linked_evidence_ids,section_id,status,risk_level,notes
N1,,intent,Argument governance,,,,,intro,active,medium,root
N2,N1,gap,Implicit argument links,GAP-001,,,,intro,active,medium,gap
N3,N2,contribution,Schema,,CON-001,CLM-001,EVD-001,methods,active,low,contribution
EOF
    cat > "$tmp/evidence/reviewer_attack_matrix.csv" <<'EOF'
attack_id,target_type,target_id,reviewer_question,attack_category,severity,likely_reviewer_profile,current_defense,evidence_needed,current_evidence_ids,defense_strength,revision_needed,response_strategy,owner,status
A1,contribution,CON-001,Is this governance rather than validity?,scope_boundary,medium,methods reviewer,Boundary language states structure only,script and schema,EVD-001,adequate,no,Keep limitation explicit,author,open
EOF
    cat > "$tmp/evidence/gap_register.csv" <<'EOF'
gap_id,intent_id,gap_statement,gap_type,gap_priority,gap_status,scope,search_or_problem_evidence_ids,boundary_language,notes
GAP-001,I1,Manuscript claims often lack explicit hierarchy,governance_gap,core,evidence_supported,argument structure within one manuscript,SRC-001,Does not establish scientific quality,fixture
EOF
    cat > "$tmp/evidence/evidence_objects.csv" <<'EOF'
object_id,object_type,statement_or_description,artifact_or_source,version,scope,method_or_measure,provenance_status,quality_status,uncertainty,status,notes
SRC-001,source,Prior writing-governance work lacks this explicit relation packet,reading note,1,writing governance,literature comparison,verified,checked,Comparison set is bounded,verified,fixture source
DAT-001,data,Synthetic relation fixture,fixture.csv,1,one synthetic packet,row-level records,verified,validated,Synthetic only,verified,fixture data
RES-001,result,The checker identifies missing typed links,validator output,1,one synthetic packet,deterministic validation,verified,validated,Structural validity only,verified,fixture result
EVD-001,evidence,Schema and checker files are present,local files,1,one toolkit packet,file inspection,verified,validated,Does not prove scholarship,verified,fixture evidence
ART-001,artifact,Argument governance schema,argument_schema.md,1,one toolkit packet,file inspection,verified,validated,Structure only,verified,fixture artifact
EOF
    cat > "$tmp/evidence/innovation_register.csv" <<'EOF'
innovation_id,contribution_id,innovation_type,innovation_dimension,comparison_set,difference_statement,materiality_statement,novelty_scope,comparison_evidence_ids,comparison_status,boundary_language,notes
NOV-001,CON-001,new_workflow,typed argument relations,prior writing-governance packet formats,Adds explicit data-result-claim and innovation relations,Improves inspectability of the packet,toolkit workflow only,SRC-001,supported,Not a scientific novelty guarantee,fixture
EOF
    cat > "$tmp/evidence/argument_relations.csv" <<'EOF'
relation_id,source_type,source_id,relation_type,target_type,target_id,evidence_ids,directness,scope_match,status,rationale,notes
REL-001,source,SRC-001,supports,gap,GAP-001,SRC-001,direct,exact,verified,Source bounds the gap,fixture
REL-002,contribution,CON-001,addresses,gap,GAP-001,EVD-001,direct,exact,verified,Contribution addresses the gap,fixture
REL-003,data,DAT-001,produces,result,RES-001,DAT-001,direct,exact,verified,Fixture data produce the result,fixture
REL-004,result,RES-001,supports,claim,CLM-001,RES-001,direct,exact,verified,Result supports the contribution claim,fixture
REL-005,claim,CLM-001,substantiates,contribution,CON-001,EVD-001,direct,exact,verified,Claim substantiates the contribution,fixture
REL-006,innovation,NOV-001,characterises,contribution,CON-001,SRC-001,direct,exact,verified,Innovation characterises the contribution,fixture
REL-007,source,SRC-001,supports,innovation,NOV-001,SRC-001,direct,exact,verified,Comparison evidence supports bounded difference,fixture
REL-008,evidence,EVD-001,supports,claim,CLM-000,EVD-001,direct,exact,verified,Evidence supports the paper thesis,fixture
REL-009,source,SRC-001,supports,claim,CLM-001,SRC-001,direct,exact,verified,Source support fits governance contribution type,fixture
EOF
    cat > "$tmp/evidence/contribution_focus.csv" <<'EOF'
contribution_id,current_role,core_gap_fit,target_reader_fit,narrative_emphasis,author_locked,section_ids,decision_status,notes
CON-001,primary,direct,high,balanced,false,intro;methods,current,fixture
EOF
}

_add_valid_focus_candidate() {
    local tmp="$1"
    cat >> "$tmp/evidence/contribution_chain.csv" <<'EOF'
CON-002,I1,GAP-001,Manuscript claims often lack explicit hierarchy,governance_gap,Flat claims hide weak evidence,A compact relation view makes the project easier to inspect,We provide a compact project relation view,governance_framework,ART-001,CLM-003,governance schema evidence,EVD-001,adequate,Does not prove manuscript quality,Validates structure only,Checker reports structural issues
EOF
    cat >> "$tmp/evidence/claim_hierarchy.csv" <<'EOF'
CLM-003,CLM-000,I1,CON-002,intro,contribution_claim,artifact_claim,The compact relation view exposes the project spine,,schema evidence,EVD-001,,governance_support_only,adequate,adequately_supported,answers_gap,low,Structure only,none
EOF
    cat >> "$tmp/evidence/contribution_focus.csv" <<'EOF'
CON-002,secondary,direct,high,light,false,intro,current,focus candidate fixture
EOF
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-010,contribution,CON-002,addresses,gap,GAP-001,EVD-001,direct,exact,verified,Candidate addresses the core gap,fixture
REL-011,claim,CLM-003,substantiates,contribution,CON-002,EVD-001,direct,exact,verified,Candidate claim substantiates the contribution,fixture
REL-012,source,SRC-001,supports,claim,CLM-003,SRC-001,direct,exact,verified,Source support fits governance contribution type,fixture
EOF
}

test_T64() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp"
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 3 \
        --end-line 4 \
        --unit-id ch01-control \
        --copy-source \
        --json) || {
        rm -rf "$tmp"
        return 1
    }
    python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json > "$tmp/check.json" || {
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
    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 99 \
        --end-line 99 \
        --unit-id beyond-start >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --start-line 1 \
        --end-line 99 \
        --unit-id beyond-end >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch01.md \
        --unit-id ../escape \
        --copy-source >/dev/null 2>&1
    rc=$?
    [[ "$rc" -ne 0 ]] || {
        rm -rf "$tmp"
        return 1
    }

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp/manual" --strict --json 2>&1)
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

    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp/project" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp/manual" --strict --json 2>&1)
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
        python3 "$repo_root/.claude/skills/thesis-control/scripts/scaffold_thesis_control.py" project \
            --source chapters/ch01.md \
            --output-dir out \
            --unit-id relative-out \
            --copy-source \
            --json >/dev/null &&
        python3 "$repo_root/.claude/skills/thesis-control/scripts/check_thesis_control.py" out --strict --json > check.json
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
        python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$case/treatment" --strict >/dev/null || return 1
    done
}

test_T74() {
    python3 - "$REPO_ROOT/.claude/skills/thesis-control/SKILL.md" <<'PY'
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-revision-escalation','revision-escalation-required'} <= kinds"
}

test_T76() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp" approved
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    second=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
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
    blocked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$fixture/blocked" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || return 1
    echo "$blocked" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'missing-revision-escalation','revision-escalation-required'} <= kinds" || return 1

    approved=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$fixture/approved" --strict --json) || return 1
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    legacy=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    echo "$legacy" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0 and d['summary']['revision_tracking'] is False" || {
        rm -rf "$tmp"
        return 1
    }

    strict=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    pending=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    resolved=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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

    pending=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    failed=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    mismatch=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    mismatch=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1) || {
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

    invalid=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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

    first=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    second=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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

    duplicate=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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

    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); duplicates=[i for i in d['issues'] if i['kind']=='duplicate-column']; assert len(duplicates)==4"
}

test_T92() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    _make_valid_thesis_control_packet "$tmp/base"

    python3 - "$tmp" "$REPO_ROOT/.claude/skills/thesis-control/scripts/check_thesis_control.py" <<'PY'
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

    legacy=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    echo "$legacy" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count']==0" || {
        rm -rf "$tmp"
        return 1
    }

    strict=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert {'invalid-early-diagnostic-trigger-count','revision-escalation-required'} <= kinds"
}

test_T96() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    _make_revision_escalation_packet "$tmp/base"

    python3 - "$tmp" "$REPO_ROOT/.claude/skills/thesis-control/scripts/check_thesis_control.py" <<'PY'
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$case_dir" \
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
    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$case_dir" \
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

    first=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --attempt-no 1 --copy-source --json) || {
        rm -rf "$tmp"
        return 1
    }
    second=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
        --source chapters/ch.md --unit-id ch --revision-issue-id ri-ch --attempt-no 2 --copy-source --force --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
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

    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
        out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$case_dir" --json 2>&1)
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
    first=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after_first=$(_tree_digest "$tmp")
    second=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after_second=$(_tree_digest "$tmp")
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$conflict" --strict --json 2>&1)
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
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$duplicate" --strict --json) || {
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$project" \
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py "$project" --json 2>&1)
    rc=$?
    after=$(_tree_digest "$tmp")
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$before" == "$after" && "$out" == *"symlink"* ]]
}

test_T110() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    python3 - "$tmp" "$REPO_ROOT/.claude/skills/thesis-control/scripts" <<'PY'
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 && "$out" != *"Traceback"* ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; locations={i['location'] for i in d['issues']}; assert {'invalid-drift-decision','invalid-audit-status'} <= kinds; assert 'thesis_control/drift_audits.csv:row 2' in locations and 'thesis_control/drift_audits.csv:row 3' in locations"
}

test_T116() {
    local fixture blocked aligned rc
    fixture="$REPO_ROOT/examples/project-intent-drift-gate"
    blocked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$fixture/blocked" --strict --json 2>&1)
    rc=$?
    [[ "$rc" -eq 1 ]] || return 1
    echo "$blocked" | python3 -c "import json,sys; d=json.load(sys.stdin); assert {i['kind'] for i in d['issues']} == {'global-thesis-gate-required'}" || return 1

    aligned=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$fixture/aligned" --strict --json) || return 1
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/ch.md --copy-source --json) || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/first.md --copy-source --json >/dev/null || {
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
    python3 .claude/skills/thesis-control/scripts/scaffold_thesis_control.py "$tmp" --source chapters/second.md --copy-source --json >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json) || {
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
    first=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    before=$(_tree_digest "$tmp") || return 1
    second=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    after=$(_tree_digest "$tmp")
    checked=$(python3 .claude/skills/thesis-control/scripts/check_thesis_control.py "$tmp" --strict --json 2>&1)
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
    out=$(python3 .claude/skills/thesis-control/scripts/upgrade_thesis_control_project_intent.py "$tmp" --json 2>&1)
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
    python3 - "$tmp" "$REPO_ROOT/.claude/skills/thesis-control/scripts" <<'PY'
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
    python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --json >/dev/null
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
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --json 2>&1)
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
    python3 .claude/skills/self-review/scripts/check_self_review_packet.py "$tmp/review_packet" --json >/dev/null
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
    out=$(python3 .claude/skills/self-review/scripts/check_self_review_packet.py "$tmp/review_packet" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'forbidden-source-allowed' in kinds and 'missing-required-forbidden-source' in kinds"
}

test_T125() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['profile']=='research-relations-v2' and d['issue_count']==0; assert d['relation_summary']['data_objects']==1 and d['relation_summary']['result_objects']==1 and not d['focus_review_candidates']"
}

test_T126() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_argument_packet "$tmp"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); missing={i['location'] for i in d['issues'] if i['kind']=='missing-file'}; assert d['profile']=='research-relations-v2'; assert {'gap_register.csv','evidence_objects.csv','innovation_register.csv','argument_relations.csv','contribution_focus.csv'} <= {x.rsplit('/',1)[-1].rsplit(chr(92),1)[-1] for x in missing}"
}

test_T127() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/,produces,result,/,bounds,result,/' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); rules={i.get('rule_id') for i in d['issues']}; assert {'DATA-01','DATA-02'} <= rules"
}

test_T128() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    _add_valid_focus_candidate "$tmp"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i.get('rule_id')=='FIT-02' for i in d['issues']); assert any(i['kind']=='missing-focus-snapshot' for i in d['issues']); c=d['focus_review_candidates'][0]; assert c['current_primary_id']=='CON-001' and c['candidate_id']=='CON-002' and c['requires_author_approval'] is True; assert c['recommended_next_skill']=='pending_author_decision' and 'remove' in c['candidate_actions']; assert {'manuscript-reframe','thesis-control'} <= set(c['post_approval_routes']); assert 'contribution order' not in c['post_approval_routes']['manuscript-reframe']"
}

test_T129() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-010,claim,CLM-001,depends_on,claim,CLM-002,EVD-001,direct,exact,verified,First half of invalid cycle,fixture
REL-011,claim,CLM-002,depends_on,claim,CLM-001,EVD-001,direct,exact,verified,Second half of invalid cycle,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='relation-cycle' for i in d['issues'])"
}

test_T130() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    sed 's/,direct,exact,verified,/,unverified,unknown,candidate,/g' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert not any(i.get('rule_id')=='FIT-02' for i in d['issues']); assert any(i.get('rule_id')=='CON-01' for i in d['issues'])"
}

test_T131() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    cat >> "$tmp/evidence/gap_register.csv" <<'EOF'
GAP-002,I1,A secondary governance gap,governance_gap,supporting,evidence_supported,argument structure within one manuscript,SRC-001,Does not establish scientific quality,wrong-target fixture
EOF
    sed -e 's/REL-002,contribution,CON-001,addresses,gap,GAP-001/REL-002,contribution,CON-001,addresses,gap,GAP-002/' -e 's/REL-005,claim,CLM-001,substantiates,contribution,CON-001/REL-005,claim,CLM-001,substantiates,contribution,CON-002/' -e 's/REL-006,innovation,NOV-001,characterises,contribution,CON-001/REL-006,innovation,NOV-001,characterises,contribution,CON-002/' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); mismatches=[i for i in d['issues'] if i['kind']=='cross-table-relation-mismatch']; assert len(mismatches) >= 3"
}

test_T132() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,direct,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert not any(i.get('rule_id')=='FIT-02' for i in d['issues'])"
}

test_T133() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    sed '/^REL-010,/d' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert not any(i.get('rule_id')=='FIT-02' for i in d['issues'])"
}

test_T134() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/REL-007,source,SRC-001,supports,innovation/REL-007,source,SRC-001,contradicts,innovation/' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); rules={i.get('rule_id') for i in d['issues']}; assert {'NOV-01','NOV-02'} <= rules; assert not d['focus_review_candidates']"
}

test_T135() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    cat >> "$tmp/evidence/innovation_register.csv" <<'EOF'
NOV-002,CON-002,new_workflow,compact relation view,prior writing-governance packet formats,Claims a difference that comparison evidence contradicts,Would improve inspectability if supported,toolkit workflow only,SRC-001,contradicted,Do not promote as established novelty,fixture
EOF
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-013,source,SRC-001,contradicts,innovation,NOV-002,SRC-001,direct,exact,verified,Comparison contradicts the claimed difference,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert any(i.get('rule_id')=='NOV-02' for i in d['issues'])"
}

test_T136() {
    local tmp out
    tmp=$(mktemp -d) || return 1
    _make_valid_argument_packet "$tmp"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --json) || {
        rm -rf "$tmp"
        return 1
    }
    rm -rf "$tmp"
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['schema_version']==1 and d['profile']=='legacy-v1'"
}

test_T137() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-010,source,SRC-001,contradicts,claim,CLM-001,SRC-001,direct,exact,verified,Source records counter-evidence,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not any(i['kind']=='invalid-relation-triple' for i in d['issues']); assert any(i.get('rule_id')=='FIT-01' for i in d['issues'])"
}

test_T138() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/core,evidence_supported/core,closed/' "$tmp/evidence/gap_register.csv" > "$tmp/evidence/gap_register.tmp"
    mv "$tmp/evidence/gap_register.tmp" "$tmp/evidence/gap_register.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='primary-relies-on-inactive-gap' for i in d['issues'])"
}

test_T139() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-010,claim,CLM-001,depends_on,claim,CLM-002,EVD-001,unverified,unknown,candidate,First provisional cycle edge,fixture
REL-011,claim,CLM-002,depends_on,claim,CLM-001,EVD-001,unverified,unknown,candidate,Second provisional cycle edge,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'provisional-relation-cycle' in kinds and 'relation-cycle' not in kinds; assert all(i.get('confidence')=='possible' for i in d['issues'] if i['kind']=='provisional-relation-cycle')"
}

test_T140() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-013,result,RES-001,supports,claim,CLM-003,RES-001,direct,exact,verified,Same result also supports the duplicate candidate,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i.get('rule_id')=='CON-02' and i['kind']=='redundant-contribution-candidate' for i in d['issues'])"
}

test_T141() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/,verified,Source bounds the gap,fixture/,verified,,fixture/' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='missing-required-value' and i['location'].endswith(':rationale') for i in d['issues'])"
}

test_T142() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    sed 's/SRC-001,source,Prior writing-governance work lacks this explicit relation packet,reading note,1,writing governance,literature comparison,verified,checked/SRC-001,source,Prior writing-governance work lacks this explicit relation packet,reading note,1,writing governance,literature comparison,unverified,contradicted/' "$tmp/evidence/evidence_objects.csv" > "$tmp/evidence/evidence_objects.tmp"
    mv "$tmp/evidence/evidence_objects.tmp" "$tmp/evidence/evidence_objects.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i.get('rule_id')=='CON-01' for i in d['issues']); assert not d['focus_review_candidates']"
}

test_T143() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,high,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    sed '/^REL-002,/d' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert not any(i.get('rule_id')=='FIT-02' and i['kind']=='contribution-focus-review' for i in d['issues'])"
}

test_T144() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    cat >> "$tmp/evidence/innovation_register.csv" <<'EOF'
NOV-002,CON-002,new_workflow,compact relation view,prior writing-governance packet formats,Adds a compact relation view,Improves inspectability within the declared scope,toolkit workflow only,SRC-001,supported,The comparison also records limits,fixture
EOF
    cat >> "$tmp/evidence/argument_relations.csv" <<'EOF'
REL-013,source,SRC-001,supports,innovation,NOV-002,SRC-001,direct,exact,verified,Comparison supports the bounded difference,fixture
REL-014,source,SRC-001,limits,innovation,NOV-002,SRC-001,direct,exact,verified,Comparison limits the novelty scope,fixture
REL-015,innovation,NOV-002,characterises,contribution,CON-002,SRC-001,direct,exact,verified,Innovation characterises the candidate,fixture
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); c=d['focus_review_candidates'][0]; counters=[x for x in c['counter_signals'] if x['dimension']=='innovation_limits']; assert counters and counters[0]['relation_ids']==['REL-014']"
}

test_T145() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    cat > "$tmp/manuscript.md" <<'EOF'
# Author-approved manuscript

Synthetic fixture for the frozen focus snapshot.
EOF
    cat > "$tmp/evidence/contribution_focus_snapshot.json" <<'EOF'
{
  "schema_version": 1,
  "intent_ids": ["I1"],
  "current_primary_ids": ["CON-001"],
  "author_approved_manuscript_path": "manuscript.md",
  "author_approved_manuscript_sha256": "unavailable",
  "relation_packet_sha256": "unavailable",
  "captured_from_files": ["evidence/*.csv", "hash unavailable: synthetic fixture"],
  "status": "pending_author_review"
}
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['focus_review_candidates']; assert not any(i['kind'] in {'missing-focus-snapshot','invalid-focus-snapshot'} for i in d['issues'])"
}

test_T146() {
    local skill="$REPO_ROOT/.claude/skills/academic-writing-assistant/SKILL.md"
    [[ -f "$skill" ]] || return 1
    grep -q '\$argument-governance' "$skill" || return 1
    grep -q -- '--strict-relations --json' "$skill" || return 1
    grep -q 'pending_author_decision' "$skill" || return 1
    grep -q '\$revision-escalation' "$skill" || return 1
    grep -q 'three unsuccessful attempts' "$skill" || return 1
    grep -q 'academic-writing-log' "$skill" || return 1
    ! grep -q 'TODO' "$skill" || return 1
}

test_T147() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    cat >> "$tmp/evidence/intent_register.csv" <<'EOF'
I2,Other paper,Another project has a different problem,Other venue,other readers,another field,A separate project gap,Separate project narrative,Separate correction,Separate timing,,Keep the projects separate,Preserve intent boundaries,medium,cross-intent fixture
EOF
    cat >> "$tmp/evidence/gap_register.csv" <<'EOF'
GAP-002,I2,A separate project gap,governance_gap,core,evidence_supported,another manuscript,SRC-001,Does not belong to I1,cross-intent fixture
EOF
    sed 's/CON-002,I1,GAP-001/CON-002,I2,GAP-002/' "$tmp/evidence/contribution_chain.csv" > "$tmp/evidence/contribution_chain.tmp"
    mv "$tmp/evidence/contribution_chain.tmp" "$tmp/evidence/contribution_chain.csv"
    sed 's/CLM-003,CLM-000,I1,CON-002/CLM-003,,I2,CON-002/' "$tmp/evidence/claim_hierarchy.csv" > "$tmp/evidence/claim_hierarchy.tmp"
    mv "$tmp/evidence/claim_hierarchy.tmp" "$tmp/evidence/claim_hierarchy.csv"
    sed 's/CON-002,addresses,gap,GAP-001/CON-002,addresses,gap,GAP-002/' "$tmp/evidence/argument_relations.csv" > "$tmp/evidence/argument_relations.tmp"
    mv "$tmp/evidence/argument_relations.tmp" "$tmp/evidence/argument_relations.csv"
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert not d['focus_review_candidates']; assert not any(i['kind']=='contribution-focus-review' for i in d['issues'])"
}

test_T148() {
    local tmp out rc
    tmp=$(mktemp -d) || return 1
    _make_valid_relation_argument_packet "$tmp"
    _add_valid_focus_candidate "$tmp"
    sed 's/CON-001,primary,direct,high,balanced/CON-001,primary,weak,low,balanced/' "$tmp/evidence/contribution_focus.csv" > "$tmp/evidence/contribution_focus.tmp"
    mv "$tmp/evidence/contribution_focus.tmp" "$tmp/evidence/contribution_focus.csv"
    cat > "$tmp/unrelated.csv" <<'EOF'
unrelated
value
EOF
    cat > "$tmp/evidence/contribution_focus_snapshot.json" <<'EOF'
{
  "schema_version": 1,
  "intent_ids": ["I9"],
  "current_primary_ids": ["CON-999"],
  "author_approved_manuscript_path": "does-not-exist.md",
  "author_approved_manuscript_sha256": "unavailable",
  "relation_packet_sha256": "unavailable",
  "captured_from_files": ["unrelated.csv", "hash unavailable: synthetic fixture"],
  "status": "pending_author_review"
}
EOF
    out=$(python3 .claude/skills/argument-governance/scripts/check_argument_governance.py "$tmp" --strict-relations --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); locations={i['location'] for i in d['issues'] if i['kind']=='invalid-focus-snapshot'}; assert any(x.endswith(':intent_ids') for x in locations); assert any(x.endswith(':current_primary_ids') for x in locations); assert any(x.endswith(':author_approved_manuscript_path') for x in locations); assert any(x.endswith(':captured_from_files') for x in locations)"
}

test_T149() {
    local skill="$REPO_ROOT/.claude/skills/academic-writing-assistant/SKILL.md"
    local ref="$REPO_ROOT/.claude/skills/academic-writing-assistant/references/argument_level_lock.md"
    local plugin_skill="$REPO_ROOT/plugins/academic-writing-toolkit/skills/academic-writing-assistant/SKILL.md"
    local plugin_ref="$REPO_ROOT/plugins/academic-writing-toolkit/skills/academic-writing-assistant/references/argument_level_lock.md"
    local guide="$REPO_ROOT/docs/skills/00-academic-writing-assistant.md"
    local files=("$skill" "$ref" "$plugin_skill" "$plugin_ref" "$guide")
    local term private_re

    [[ -f "$ref" && -f "$plugin_ref" ]] || return 1
    grep -q 'references/argument_level_lock.md' "$skill" || return 1
    grep -q 'six-line `Paper Claim Licence`' "$skill" || return 1
    grep -q 'Six-Line Paper Claim Licence' "$ref" || return 1
    for term in \
        'Broad problem' \
        'Exact paper contribution' \
        'Primary empirical claim' \
        'Headline or extrapolative claim' \
        'Licensed scope' \
        'Explicitly unlicensed claims'; do
        grep -q "$term" "$ref" || return 1
    done
    grep -qi 'field-level gap' "$ref" || return 1
    grep -qi 'paper-level contribution' "$ref" || return 1
    grep -qi 'data-level empirical finding' "$ref" || return 1
    grep -qi 'extrapolation-level claim' "$ref" || return 1
    grep -q '`wording`' "$ref" || return 1
    grep -q '`argument_design`' "$ref" || return 1
    grep -q '`research_design`' "$ref" || return 1
    grep -q 'decisive study' "$ref" || return 1
    grep -q 'narrow or reclassify the headline claim' "$ref" || return 1
    grep -q 'scope_propagation_failure' "$ref" || return 1
    grep -q '| Transition | Evidence or relation IDs | evidence_status | support_balance | scope_match | Missing evidence | Decision |' "$ref" || return 1
    grep -q 'contribution_focus.csv.*current_role' "$ref" || return 1
    private_re='Reviewer yh''eE|Reviewer QP''E2|Reviewer Pn''Mw|76''\.34|EM''NLP|H''SG|oo''cyte|CS''UR'
    ! grep -Eqi "$private_re" "${files[@]}" || return 1
    ! grep -q 'TODO' "$skill" "$ref" "$guide" || return 1
}

test_T150() {
    local assistant="$REPO_ROOT/.claude/skills/academic-writing-assistant/SKILL.md"
    local governance="$REPO_ROOT/.claude/skills/argument-governance/SKILL.md"
    local plugin_assistant="$REPO_ROOT/plugins/academic-writing-toolkit/skills/academic-writing-assistant/SKILL.md"
    local plugin_governance="$REPO_ROOT/plugins/academic-writing-toolkit/skills/argument-governance/SKILL.md"
    local file

    for file in "$assistant" "$governance" "$plugin_assistant" "$plugin_governance"; do
        grep -q 'thesis_control/project_intent.csv' "$file" || return 1
        grep -q 'author-approved' "$file" || return 1
        grep -q 'intent_id' "$file" || return 1
    done
    grep -q 'Never treat scaffold defaults or draft rows as approval' "$assistant" || return 1
    grep -q 'Do not treat a scaffolded draft as author approval' "$governance" || return 1
    grep -q 'inconsistent with the argument-governance `intent_id`' "$assistant" || return 1
    grep -q "inconsistent with the argument packet's \`intent_id\`" "$governance" || return 1
}

test_T151() {
    local checker="$REPO_ROOT/scripts/check-skills-only-submission.py"
    local tmp submission export_skill rc

    python3 "$checker" --repo-root "$REPO_ROOT" >/dev/null || return 1
    tmp=$(mktemp -d) || return 1
    mkdir -p \
        "$tmp/.claude" \
        "$tmp/plugins" \
        "$tmp/submission/openai"
    cp -R "$REPO_ROOT/.claude/skills" "$tmp/.claude/skills" || return 1
    cp -R \
        "$REPO_ROOT/plugins/academic-writing-toolkit" \
        "$tmp/plugins/academic-writing-toolkit" || return 1
    cp \
        "$REPO_ROOT/submission/openai/skills-only-submission.json" \
        "$tmp/submission/openai/skills-only-submission.json" || return 1
    submission="$tmp/submission/openai/skills-only-submission.json"
    export_skill="$tmp/plugins/academic-writing-toolkit/skills/export/SKILL.md"
    rc=0

    python3 - "$submission" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["test_cases"].pop()
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    if python3 "$checker" --repo-root "$tmp" >/dev/null 2>&1; then
        rc=1
    fi

    cp \
        "$REPO_ROOT/submission/openai/skills-only-submission.json" \
        "$submission" || rc=1
    python3 - "$submission" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["test_cases"][0]["entry_skill"] = "unknown-skill"
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    if python3 "$checker" --repo-root "$tmp" >/dev/null 2>&1; then
        rc=1
    fi

    cp \
        "$REPO_ROOT/submission/openai/skills-only-submission.json" \
        "$submission" || rc=1
    python3 - "$export_skill" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace(
    "description:",
    "disable-model-invocation: true\ndescription:",
    1,
)
path.write_text(text, encoding="utf-8")
PY
    if python3 "$checker" --repo-root "$tmp" >/dev/null 2>&1; then
        rc=1
    fi

    rm -rf "$tmp"
    return "$rc"
}

test_T152() {
    local tmp version first_source second_source first_plugin second_plugin

    tmp=$(mktemp -d) || return 1
    version=$(python3 - "$REPO_ROOT/plugins/academic-writing-toolkit/.codex-plugin/plugin.json" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["version"])
PY
) || {
        rm -rf "$tmp"
        return 1
    }

    python3 "$REPO_ROOT/scripts/build-plugin-release.py" \
        --repo-root "$REPO_ROOT" \
        --ref HEAD \
        --version "$version" \
        --out-dir "$tmp/first" >/dev/null || {
        rm -rf "$tmp"
        return 1
    }
    python3 "$REPO_ROOT/scripts/build-plugin-release.py" \
        --repo-root "$REPO_ROOT" \
        --ref HEAD \
        --version "$version" \
        --out-dir "$tmp/second" >/dev/null || {
        rm -rf "$tmp"
        return 1
    }

    first_source=$(sha256sum "$tmp/first/academic-writing-toolkit-v${version}.zip" | awk '{print $1}')
    second_source=$(sha256sum "$tmp/second/academic-writing-toolkit-v${version}.zip" | awk '{print $1}')
    first_plugin=$(sha256sum "$tmp/first/academic-writing-toolkit-openai-plugin-v${version}.zip" | awk '{print $1}')
    second_plugin=$(sha256sum "$tmp/second/academic-writing-toolkit-openai-plugin-v${version}.zip" | awk '{print $1}')

    rm -rf "$tmp"
    [[ "$first_source" == "$second_source" && "$first_plugin" == "$second_plugin" ]]
}

test_T50() {
    bash scripts/sync-plugin.sh --check >/dev/null
}

test_T51() {
    bash scripts/check-plugin.sh >/dev/null
}

test_T52() {
    local cache rc
    cache="$REPO_ROOT/.claude/skills/export/scripts/__pycache__"
    mkdir -p "$cache"
    printf 'bytecode cache fixture\n' > "$cache/convert_to_docx.cpython-38.pyc"
    bash scripts/sync-plugin.sh --check >/dev/null 2>&1
    rc=$?
    rm -rf "$cache"
    return "$rc"
}

test_T53() {
    ! grep -Rq 'removeprefix' "$REPO_ROOT/scripts/check-plugin.sh" "$REPO_ROOT/scripts/sync-plugin.sh"
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
    python3 .claude/skills/release-governance/scripts/check_release_packet.py "$tmp" >/dev/null
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
    out=$(python3 .claude/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
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
    out=$(python3 .claude/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
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
    out=$(python3 .claude/skills/release-governance/scripts/check_release_packet.py "$tmp" --json 2>&1)
    rc=$?
    rm -rf "$tmp"
    [[ "$rc" -eq 1 ]] || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); kinds={i['kind'] for i in d['issues']}; assert 'local-absolute-path' in kinds and 'placeholder-text' in kinds"
}

test_T58() {
    ! grep -Eq '\b(subprocess|socket|requests|urllib|http\.client|ftplib)\b' .claude/skills/release-governance/scripts/check_release_packet.py
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

    local doc
    for doc in "${setup_docs[@]}"; do
        grep -q "evidence-review" "$doc" || return 1
        grep -q "release-governance" "$doc" || return 1
    done

    grep -q "Local agent skills" "$REPO_ROOT/README.md" || return 1
    grep -q "ChatGPT App MCP server" "$REPO_ROOT/README.md" || return 1
    grep -q "pasted-text" "$REPO_ROOT/README.md" || return 1
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
run_test "T45 verify-refs Crossref fixture verifies metadata" test_T45
run_test "T46 verify-refs flags Crossref title mismatch" test_T46
run_test "T47 verify-refs flags Crossref year mismatch" test_T47
run_test "T48 verify-refs arXiv fixture verifies metadata" test_T48
run_test "T49 verify-refs documents online flags" test_T49
run_test "T50 plugin skills are synced" test_T50
run_test "T51 plugin package validates" test_T51
run_test "T52 plugin sync ignores bytecode caches" test_T52
run_test "T53 plugin checks are Python 3.8 compatible" test_T53
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
run_test "T125 strict relation profile accepts a clean packet" test_T125
run_test "T126 strict relation profile rejects a legacy-only packet" test_T126
run_test "T127 strict relation profile separates data from results" test_T127
run_test "T128 strict relation profile proposes an approval-gated focus review" test_T128
run_test "T129 strict relation profile rejects relation cycles" test_T129
run_test "T130 provisional evidence cannot complete a contribution chain" test_T130
run_test "T131 strict relations reject cross-table target mismatches" test_T131
run_test "T132 one focus weakness cannot trigger a focus shift" test_T132
run_test "T133 candidates require a reliable active core-gap relation" test_T133
run_test "T134 contradictory innovation evidence is not positive support" test_T134
run_test "T135 contradicted secondary innovation cannot become a focus candidate" test_T135
run_test "T136 legacy output preserves schema version one" test_T136
run_test "T137 verified counter-evidence uses an allowed relation triple" test_T137
run_test "T138 primary contributions cannot rely on inactive gaps" test_T138
run_test "T139 provisional relation cycles stay advisory" test_T139
run_test "T140 semantic support overlap detects duplicate contributions" test_T140
run_test "T141 strict relation rows require key values" test_T141
run_test "T142 unreliable evidence objects cannot complete a chain" test_T142
run_test "T143 one gap-fit defect cannot count as two focus weaknesses" test_T143
run_test "T144 innovation limits remain traceable counter-signals" test_T144
run_test "T145 a valid focus snapshot satisfies the decision gate" test_T145
run_test "T146 academic writing assistant routes without duplicating governance" test_T146
run_test "T147 contribution focus candidates cannot cross intent boundaries" test_T147
run_test "T148 stale or unrelated focus snapshots fail semantic validation" test_T148
run_test "T149 academic writing assistant locks argument levels and claim licence" test_T149
run_test "T150 assistant and argument governance reuse project intent" test_T150
run_test "T151 skills-only submission validator rejects drift" test_T151
run_test "T152 release builder produces reproducible archives" test_T152

header ""
if [[ ${#FAIL_LIST[@]} -eq 0 ]]; then
    pass "all $PASSES tests passed."
    exit 0
else
    printf "\n\033[31m%d test(s) failed:\033[0m\n" "${#FAIL_LIST[@]}"
    for t in "${FAIL_LIST[@]}"; do printf "  - %s\n" "$t"; done
    exit 1
fi
