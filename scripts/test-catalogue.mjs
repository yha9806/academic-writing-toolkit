// Catalogue truth: what the skills say about themselves and each other holds
// on disk. Three groups that ran under the retired dsh guards package until
// 2026-09-20 (descriptions, skill-text, skill-commands) moved here unchanged
// in substance; see docs/specs/2026-09-20-retire-dsh-line-design.md.
import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { lintNotes, EVIDENCE_VALUES } from '../.claude/skills/note/scripts/notes-lint.mjs'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')
const SKILL_DOCS = join(PRODUCT_ROOT, 'docs', 'skills')
const AWT = join(PRODUCT_ROOT, 'scaffold', 'awt.mjs')

const CATALOGUE = readdirSync(SKILLS_SRC, { withFileTypes: true })
  .filter((e) => e.isDirectory()).map((e) => e.name).sort()

const dirs = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

// --- descriptions: disjoint routing signatures ------------------------------

// Each skill owns one exclusive keyword that may appear in no other
// description; "rebuttal" (the old cross-fire magnet) may appear in none;
// every description stays within a 40-word budget.
const EXCLUSIVE = {
  read: 'page by page',
  note: 'record',
  map: 'coverage',
  integrate: 'weave',
  review: 'review',
  audit: 'consistency',
  'verify-refs': 'bibtex',
  export: 'docx',
  readers: 'reader panel',
}

function descriptions() {
  const out = {}
  for (const dir of CATALOGUE) {
    const text = readFileSync(join(SKILLS_SRC, dir, 'SKILL.md'), 'utf8')
    const match = text.match(/^description:\s*(.+)$/m)
    assert.ok(match, `no description frontmatter in ${dir}`)
    out[dir] = match[1].trim().replace(/^["']|["']$/g, '').toLowerCase()
  }
  return out
}

function hasKeyword(text, keyword) {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`\\b${escaped}\\b`).test(text)
}

// The title once carried the count, which went stale the first time a skill
// was retired; the assertion says it better than a number can.
test('catalogue contains exactly the approved skills, and nothing else', () => {
  assert.deepEqual(CATALOGUE, Object.keys(EXCLUSIVE).sort())
})

test('each exclusive routing keyword appears only in its owner description', () => {
  const desc = descriptions()
  for (const [owner, keyword] of Object.entries(EXCLUSIVE)) {
    assert.ok(hasKeyword(desc[owner], keyword), `${owner} description must contain its keyword "${keyword}"`)
    for (const [other, text] of Object.entries(desc)) {
      if (other === owner) continue
      assert.ok(!hasKeyword(text, keyword), `keyword "${keyword}" owned by ${owner} also appears in ${other}`)
    }
  }
})

test('"rebuttal" appears in no description', () => {
  for (const [name, text] of Object.entries(descriptions())) {
    assert.ok(!text.includes('rebuttal'), `"rebuttal" found in ${name}`)
  }
})

test('every description is at most 40 words', () => {
  for (const [name, text] of Object.entries(descriptions())) {
    const words = text.split(/\s+/).filter(Boolean).length
    assert.ok(words <= 40, `${name} description is ${words} words (budget 40)`)
  }
})

// --- skill text: a skill describes the surface it runs on -------------------

/** Every file that tells a reader or an agent which skills exist. */
function skillProse() {
  const out = CATALOGUE.map((name) => ({
    where: `.claude/skills/${name}/SKILL.md`,
    body: readFileSync(join(SKILLS_SRC, name, 'SKILL.md'), 'utf8'),
  }))
  if (existsSync(SKILL_DOCS)) {
    for (const f of readdirSync(SKILL_DOCS).filter((n) => n.endsWith('.md'))) {
      out.push({ where: `docs/skills/${f}`, body: readFileSync(join(SKILL_DOCS, f), 'utf8') })
    }
  }
  return out
}

test('no skill or skill document sends the reader to a command outside the catalogue', () => {
  // A retired skill keeps working as an instruction long after it stops
  // working as a skill: nothing triggers, and the reader cannot tell whether
  // they mistyped it or the document is stale.
  const known = new Set(CATALOGUE)
  const dangling = []
  for (const { where, body } of skillProse()) {
    for (const [, name] of body.matchAll(/(?:^|[\s(`])\/([a-z][a-z0-9-]{2,})\b/g)) {
      if (!known.has(name)) dangling.push(`${where}: /${name}`)
    }
  }
  assert.deepEqual([...new Set(dangling)].sort(), [],
    `these name a skill the catalogue does not have:\n  ${[...new Set(dangling)].sort().join('\n  ')}`)
})

test('the notes template a workspace ships passes the lint /note declares mandatory', () => {
  const template = readFileSync(join(PRODUCT_ROOT, 'literature', 'reading_notes', '_template_NOTES.md'), 'utf8')
  const findings = lintNotes(template).map((f) => `${f.severity}: ${f.code}`)
  assert.deepEqual(findings, [], `the shipped template does not satisfy its own linter:\n  ${findings.join('\n  ')}`)
})

test('a skill that instructs an interpreter is granted the tool that runs it', () => {
  // `/export` once granted `Bash(python *)` while its body ran `python3`, so
  // in a host that honours the declaration the skill's own command is refused.
  const problems = []
  for (const name of CATALOGUE) {
    const body = readFileSync(join(SKILLS_SRC, name, 'SKILL.md'), 'utf8')
    const grant = /^allowed-tools:(.*)$/m.exec(body)?.[1] ?? ''
    const interpreters = new Set([...body.matchAll(/^\s*(python3|node|npm)\s+\S/gm)].map((m) => m[1]))
    if (interpreters.size === 0) continue
    if (!/\bBash\b/.test(grant)) {
      problems.push(`${name}: instructs ${[...interpreters].join(', ')} but grants no Bash`)
      continue
    }
    for (const scoped of grant.matchAll(/Bash\(([^)]*)\)/g)) {
      const covers = [...interpreters].some((i) => scoped[1].trim().startsWith(i))
      if (!covers && !/^Bash\b(?!\()/.test(grant.trim())) {
        problems.push(`${name}: grants Bash(${scoped[1].trim()}) but instructs ${[...interpreters].join(', ')}`)
      }
    }
  }
  assert.deepEqual(problems, [], `frontmatter does not permit the skill's own commands:\n  ${problems.join('\n  ')}`)
})

test('a workspace config carries the chapter targets /map reports against', () => {
  // Asserted against the file `init` actually writes.
  const parent = mkdtempSync(join(tmpdir(), 'awt-skill-text-'))
  dirs.push(parent)
  const ws = join(parent, 'thesis')
  const res = spawnSync(process.execPath, [AWT, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  assert.equal(res.status, 0, res.stderr)
  const config = readFileSync(join(ws, 'AGENTS.md'), 'utf8')
  assert.match(config, /target/i, 'the scaffolded workspace config names no chapter targets')
  assert.match(config, /\|\s*ch1\s*\|/, 'the targets are not a table /map can read')
})

test('the evidence-status values skills name are the ones the linter accepts', () => {
  // `/note` declares the field, the shipped template carries it, and
  // `/integrate` refuses to weave in a source that reports having been read
  // only in part. Three places naming one vocabulary is three places for it
  // to drift from the one that enforces it.
  const known = new Set(EVIDENCE_VALUES)
  assert.ok(known.size >= 3)
  const wrong = []
  for (const { where, body } of skillProse()) {
    for (const [, value] of body.matchAll(/Evidence status[`:\s]*([a-z_]{4,})/g)) {
      if (!known.has(value)) wrong.push(`${where}: ${value}`)
    }
  }
  assert.deepEqual(wrong, [], `these name a value the linter would reject:\n  ${wrong.join('\n  ')}`)
})

// --- skill commands: every command a skill issues resolves ------------------

function workspace() {
  const parent = mkdtempSync(join(tmpdir(), 'awt-skill-cmd-'))
  dirs.push(parent)
  const ws = join(parent, 'thesis')
  const res = spawnSync(process.execPath, [AWT, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  assert.equal(res.status, 0, res.stderr)
  return ws
}

/** Every `python3 <path>` / `node <path>` a skill instructs, with its source. */
function instructedCommands() {
  const out = []
  for (const skill of CATALOGUE) {
    const body = readFileSync(join(SKILLS_SRC, skill, 'SKILL.md'), 'utf8')
    for (const [, interpreter, path] of body.matchAll(/\b(python3?|node)\s+([A-Za-z0-9_./-]+\.(?:py|mjs))/g)) {
      out.push({ skill, interpreter, path })
    }
  }
  return out
}

test('every command a skill instructs names a path that exists in a workspace', () => {
  const ws = workspace()
  const commands = instructedCommands()
  assert.ok(commands.length >= 6, `expected the catalogue to still issue commands, found ${commands.length}`)
  const unresolved = commands
    .filter(({ path }) => !existsSync(join(ws, path)))
    .map(({ skill, path }) => `${skill}: ${path}`)
  assert.deepEqual(unresolved, [], `these skills name paths a workspace does not have:\n  ${unresolved.join('\n  ')}`)
})

test('the same commands also resolve in a toolkit checkout', () => {
  const unresolved = instructedCommands()
    .filter(({ path }) => !existsSync(join(PRODUCT_ROOT, path)))
    .map(({ skill, path }) => `${skill}: ${path}`)
  assert.deepEqual(unresolved, [], `these skills name paths the checkout does not have:\n  ${unresolved.join('\n  ')}`)
})

test('no skill instructs a bare `python`, which exists on neither macOS nor modern Linux', () => {
  const bare = instructedCommands()
    .filter(({ interpreter }) => interpreter === 'python')
    .map(({ skill, path }) => `${skill}: python ${path}`)
  assert.deepEqual(bare, [], `use python3 in the example and name the platform interpreter in prose:\n  ${bare.join('\n  ')}`)
})

test('all instructed Python helpers run with the native interpreter from a linked workspace', () => {
  const ws = workspace()
  const python = process.env.AWT_TEST_PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const paths = [...new Set(instructedCommands().filter(({ interpreter }) => interpreter.startsWith('python')).map(({ path }) => path))]
  assert.ok(paths.length >= 5)
  for (const path of paths) {
    const res = spawnSync(python, ['-X', 'utf8', path, '--help'], { cwd: ws, encoding: 'utf8', timeout: 60_000 })
    assert.equal(res.status, 0, `${path}: ${res.error ?? ''}\n${res.stdout}${res.stderr}`)
  }
})

test('map counts real chapter files without shell globs or Unix wc', () => {
  const ws = workspace()
  writeFileSync(join(ws, 'chapters', 'ch1_中文.md'), '# Heading\n\nTwo words.\t中文测试\n')
  writeFileSync(join(ws, 'chapters', 'ch2 empty.md'), '')
  writeFileSync(join(ws, 'chapters', 'ignored.txt'), 'not a chapter')
  const res = spawnSync(process.execPath, [join(ws, '.claude', 'skills', 'map', 'scripts', 'count-words.mjs'), '--base-dir', ws, '--json'], { encoding: 'utf8' })
  assert.equal(res.status, 0, res.stderr)
  const report = JSON.parse(res.stdout)
  assert.equal(report.total, 5)
  assert.deepEqual(report.chapters.map(({ words }) => words), [5, 0])
  assert.equal(report.chapters.length, 2)
})
