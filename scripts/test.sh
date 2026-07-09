#!/usr/bin/env bash
# scripts/test.sh — runs the regression test suite (97 automated tests: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features + T45-T49 reference metadata + T50-T53 plugin packaging + T54-T58 release governance + T59 docs consistency + T60 Markdown BibTeX + T61-T63 productization + T64-T72 thesis control + T73 lost-in-conversation bench + T74-T100 revision escalation and human gates) for academic-writing-toolkit.
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
    grep -q "/human-eval-handoff-repair" "$REPO_ROOT/README.md" || return 1
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

_make_valid_thesis_control_packet() {
    local tmp="$1"
    mkdir -p "$tmp/thesis_control" "$tmp/chapters"
    cat > "$tmp/chapters/ch02.md" <<'EOF'
# Chapter 2

Local-first writing workflows can make source notes inspectable, but this section only claims that file-based records improve traceability within one project. It does not claim that such workflows improve scholarly quality by themselves.
EOF
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch02-s1,chapters/ch02.md,Local workflow control,This unit argues that file-based records improve traceability within one writing project by keeping notes and claims inspectable.,single-project workflow traceability only,file-based records improve traceability;the workflow does not prove scholarly quality,do not claim quality improvement;preserve single-project boundary
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch02-s1,ri-ch02-traceability,1,clarify topic sentence in first paragraph,make the traceability claim clearer without changing its scope,do not add quality improvement claims;do not remove single-project boundary,check following paragraph for repeated boundary language,spine sentence preserved;no new unsupported claim,true,applied
EOF
    cat > "$tmp/thesis_control/drift_audits.csv" <<'EOF'
audit_id,contract_id,changed_claims,changed_boundaries,new_unsupported_claims,missed_adjacent_updates,drift_decision,human_review_required,status
da-001,ec-001,none,none,none,none,accept,false,passed
EOF
    cat > "$tmp/thesis_control/revision_escalations.csv" <<'EOF'
escalation_id,revision_issue_id,escalation_kind,trigger_contracts,approved_after_attempt,primary_category,writing_scope,valid_requirements,missing_or_conflicting_information,latest_author_approved_version,recommended_next_action,human_approved,status
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
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
ch03,chapters/ch03.md,Revision control,This unit argues that repeated revisions need a durable escalation gate.,one section only,revision attempts require a stop gate,do not broaden beyond revision control
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-002,ch03,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-003,ch03,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
ec-004,ch03,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
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
    mkdir -p "$tmp/thesis_control"
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-legacy-001,ch01,clarify prose,improve clarity,do not broaden,check neighbours,spine preserved,true,applied
ec-legacy-002,ch02,clarify prose,improve clarity,do not broaden,check neighbours,spine preserved,false,draft
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
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status
ec-001,ch03,ri-ch03-clarity,1,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,false,draft
ec-002,ch03,ri-ch03-clarity,2,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,approved
ec-003,ch03,ri-ch03-clarity,3,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,false,rejected
ec-004,ch03,ri-ch03-clarity,4,clarify the claim,improve clarity,do not broaden,check next paragraph,spine preserved,true,applied
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
    cat > "$tmp/thesis_control/spine_cards.csv" <<'EOF'
unit_id,path,section_title,spine_sentence,scope_boundary,core_claims,do_not_change
EOF
    cat > "$tmp/thesis_control/edit_contracts.csv" <<'EOF'
contract_id,unit_id,revision_issue_id,attempt_no,change_scope,allowed_changes,forbidden_changes,adjacent_context,acceptance_checks,human_approved,status,owner_note
ec-a-001,a,ri-a,1,scope,allowed,forbidden,adjacent,checks,false,draft,keep-a
ec-b-001,b,ri-b,1,scope,allowed,forbidden,adjacent,checks,false,draft,keep-b
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

header ""
if [[ ${#FAIL_LIST[@]} -eq 0 ]]; then
    pass "all $PASSES tests passed."
    exit 0
else
    printf "\n\033[31m%d test(s) failed:\033[0m\n" "${#FAIL_LIST[@]}"
    for t in "${FAIL_LIST[@]}"; do printf "  - %s\n" "$t"; done
    exit 1
fi
