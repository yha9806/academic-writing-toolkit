// `awt init` manifest gate (P2 spec item 4): the scaffolded workspace
// contains EXACTLY the thesis-workspace files — asserted as a full recursive
// manifest, so any toolkit-dev file leaking into the scaffold (the
// split-identity finding) is a red test, not a review comment. Also pins the
// never-overwrite refusal and verify's not-a-workspace refusal.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const AWT = resolve(import.meta.dirname, '..', '..', 'scaffold', 'awt.mjs')

const dirs: string[] = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

function scratch(): string {
  const dir = mkdtempSync(join(tmpdir(), 'awt-scaffold-test-'))
  dirs.push(dir)
  return dir
}

function awt(...args: string[]) {
  return spawnSync(process.execPath, [AWT, ...args], { encoding: 'utf8', timeout: 60_000 })
}

/** Recursive manifest as sorted `kind relative/path` lines; never follows symlinks. */
function manifest(root: string): string[] {
  const out: string[] = []
  const walk = (rel: string) => {
    for (const entry of readdirSync(join(root, rel), { withFileTypes: true })) {
      const entryRel = rel === '' ? entry.name : `${rel}/${entry.name}`
      if (entry.isSymbolicLink()) {
        out.push(`link ${entryRel}`)
      } else if (entry.isDirectory()) {
        out.push(`dir ${entryRel}`)
        walk(entryRel)
      } else {
        out.push(`file ${entryRel}`)
      }
    }
  }
  walk('')
  return out.sort()
}

const SKILLS = ['audit', 'edit-contract', 'export', 'integrate', 'map', 'note', 'read', 'review', 'verify-refs']

test('init scaffolds exactly the thesis-workspace manifest — no toolkit-dev files', () => {
  const ws = join(scratch(), 'thesis')
  const res = awt('init', ws)
  assert.equal(res.status, 0, res.stderr)

  assert.deepEqual(manifest(ws), [
    'dir .agents',
    'dir .agents/skills',
    ...SKILLS.map((name) => `link .agents/skills/${name}`),
    'dir chapters',
    'dir contracts',
    'dir literature',
    'dir literature/reading_notes',
    'file AGENTS.md',
    'file literature/reading_notes/_template_NOTES.md',
    'link CLAUDE.md',
  ].sort())

  // The config link resolves and both names read the same contract.
  assert.equal(readlinkSync(join(ws, 'CLAUDE.md')), 'AGENTS.md')
  assert.match(readFileSync(join(ws, 'CLAUDE.md'), 'utf8'), /Academic Writing Workspace/)

  // Every skill link resolves into the product catalogue at a real SKILL.md.
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

test('verify refuses a directory that is not an AWT workspace', () => {
  const dir = scratch()
  mkdirSync(join(dir, 'chapters'))
  const res = awt('verify', dir)
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_VERIFY_NOT_WORKSPACE/)
})
