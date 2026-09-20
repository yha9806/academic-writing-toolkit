// `awt init` manifest gate: the scaffolded workspace contains EXACTLY the
// thesis-workspace files, asserted as a full recursive manifest, so any
// toolkit-dev file leaking into the scaffold is a red test, not a review
// comment. Also pins the never-overwrite refusal and the catalogue rules.
// The init half of the retired guards' scaffold test, moved 2026-09-20.
import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { cpSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const AWT = join(ROOT, 'scaffold', 'awt.mjs')
const TEMPLATE = join(ROOT, 'literature', 'reading_notes', '_template_NOTES.md')

const dirs = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

function scratch() {
  const dir = mkdtempSync(join(tmpdir(), 'awt-scaffold-test-'))
  dirs.push(dir)
  return dir
}

function awt(...args) {
  return spawnSync(process.execPath, [AWT, ...args], { encoding: 'utf8', timeout: 60_000 })
}

/** Recursive manifest as sorted `kind relative/path` lines; never follows symlinks. */
function manifest(root) {
  const out = []
  const walk = (rel) => {
    for (const entry of readdirSync(join(root, rel), { withFileTypes: true })) {
      const entryRel = rel === '' ? entry.name : `${rel}/${entry.name}`
      if (entry.isSymbolicLink()) out.push(`link ${entryRel}`)
      else if (entry.isDirectory()) { out.push(`dir ${entryRel}`); walk(entryRel) }
      else out.push(`file ${entryRel}`)
    }
  }
  walk('')
  return out.sort()
}

// Derived from what ships, not written out: as a literal it named a retired
// skill and turned this red long after that skill was gone. Safe to derive
// because test-catalogue.mjs holds the approved catalogue and asserts the
// tree equals it, so an unapproved skill is caught there, not hidden here.
const SKILLS = readdirSync(join(ROOT, '.claude', 'skills')).sort()
assert.ok(SKILLS.length >= 5, `only ${SKILLS.length} skills ship; below that this manifest proves nothing`)

test('init scaffolds exactly the thesis-workspace manifest — no toolkit-dev files', () => {
  const ws = join(scratch(), 'thesis')
  const res = awt('init', ws)
  assert.equal(res.status, 0, res.stderr)
  assert.deepEqual(manifest(ws), [
    'dir .agents',
    'dir .agents/skills',
    ...SKILLS.map((name) => `link .agents/skills/${name}`),
    'dir .claude',
    'link .claude/skills',
    'dir chapters',
    'dir contracts',
    'dir literature',
    'dir literature/reading_notes',
    'file AGENTS.md',
    'file literature/reading_notes/_template_NOTES.md',
    'link references',
    process.platform === 'win32' ? 'file CLAUDE.md' : 'link CLAUDE.md',
  ].sort())
  if (process.platform !== 'win32') assert.equal(readlinkSync(join(ws, 'CLAUDE.md')), 'AGENTS.md')
  assert.match(readFileSync(join(ws, 'CLAUDE.md'), 'utf8'), /Academic Writing Workspace/)
  writeFileSync(join(ws, 'AGENTS.md'), 'author-updated workspace contract')
  assert.equal(readFileSync(join(ws, 'CLAUDE.md'), 'utf8'), 'author-updated workspace contract')
  assert.ok(readFileSync(join(ws, 'references', 'argument-checklist.md'), 'utf8').length > 0)
  for (const name of SKILLS) {
    const target = realpathSync(join(ws, '.agents', 'skills', name))
    assert.ok(lstatSync(join(target, 'SKILL.md')).isFile(), `${name} link does not resolve to a skill bundle`)
  }
})

test('init refuses a non-empty target and leaves it untouched', () => {
  const dir = scratch()
  writeFileSync(join(dir, 'precious.md'), 'author content')
  const res = awt('init', dir)
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_INIT_TARGET_EXISTS/)
  assert.deepEqual(manifest(dir), ['file precious.md'])
})

/**
 * A throwaway product root holding only what `init` reads: the scaffold entry
 * point, the notes template, and a catalogue built to order. `true` makes a
 * real skill (a directory with a SKILL.md); `false` makes a bare directory.
 */
function productRoot(catalogue) {
  const root = scratch()
  mkdirSync(join(root, 'scaffold'), { recursive: true })
  cpSync(AWT, join(root, 'scaffold', 'awt.mjs'))
  mkdirSync(join(root, 'literature', 'reading_notes'), { recursive: true })
  cpSync(TEMPLATE, join(root, 'literature', 'reading_notes', '_template_NOTES.md'))
  for (const [name, isSkill] of Object.entries(catalogue)) {
    const dir = join(root, '.claude', 'skills', name, 'scripts')
    mkdirSync(dir, { recursive: true })
    if (isSkill) writeFileSync(join(root, '.claude', 'skills', name, 'SKILL.md'), `---\nname: ${name}\n---\n`)
  }
  return join(root, 'scaffold', 'awt.mjs')
}

test('init refuses a catalogue directory with no SKILL.md — build residue never becomes an extra skill', () => {
  const entry = productRoot({ note: true, read: true, 'retired-skill': false })
  const ws = join(scratch(), 'ws')
  const res = spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  assert.notEqual(res.status, 0, 'a directory with no SKILL.md must not be linked as a skill')
  assert.match(res.stderr, /AWT_INIT_NOT_A_SKILL/)
  assert.match(res.stderr, /retired-skill/)
})

test('init links exactly the real skills of a clean catalogue', () => {
  const entry = productRoot({ note: true, read: true })
  const ws = join(scratch(), 'ws')
  const res = spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  assert.equal(res.status, 0, res.stderr)
  assert.deepEqual(readdirSync(join(ws, '.agents', 'skills')).sort(), ['note', 'read'])
})
