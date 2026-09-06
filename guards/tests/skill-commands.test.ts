// Gate A goal 1: every command a skill issues resolves in a workspace created
// by `awt init`, not only in a checkout of this toolkit.
//
// The skills have one text and two execution contexts. On the Advisory surface
// the working directory is this repository and `scripts/…` resolves; in the
// app it is the author's workspace and it does not. Nothing in the catalogue
// distinguished the two, so the same instruction was correct in one context
// and unrunnable in the other — `/verify-refs` could not run its only command,
// and three of `/audit`'s five checks failed.
//
// This gate reads the commands out of the skills themselves rather than from a
// list maintained beside them, so a skill that grows a new command is covered
// the day it is written.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')
const AWT = join(PRODUCT_ROOT, 'scaffold', 'awt.mjs')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')

const dirs: string[] = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

function workspace(): string {
  const parent = mkdtempSync(join(tmpdir(), 'awt-skill-cmd-'))
  dirs.push(parent)
  const ws = join(parent, 'thesis')
  const res = spawnSync(process.execPath, [AWT, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  assert.equal(res.status, 0, res.stderr)
  return ws
}

/** Every `python3 <path>` / `node <path>` a skill instructs, with its source. */
function instructedCommands(): Array<{ skill: string; interpreter: string; path: string }> {
  const out: Array<{ skill: string; interpreter: string; path: string }> = []
  for (const skill of readdirSync(SKILLS_SRC, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name)) {
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
  // The Advisory surface must keep working: a fix that moved the scripts
  // somewhere only the app can see would trade one broken context for the other.
  const unresolved = instructedCommands()
    .filter(({ path }) => !existsSync(join(PRODUCT_ROOT, path)))
    .map(({ skill, path }) => `${skill}: ${path}`)
  assert.deepEqual(unresolved, [], `these skills name paths the checkout does not have:\n  ${unresolved.join('\n  ')}`)
})

test('no skill instructs a bare `python`, which exists on neither macOS nor modern Linux', () => {
  const bare = instructedCommands()
    .filter(({ interpreter }) => interpreter === 'python')
    .map(({ skill, path }) => `${skill}: python ${path}`)
  assert.deepEqual(bare, [], `use python3:\n  ${bare.join('\n  ')}`)
})
