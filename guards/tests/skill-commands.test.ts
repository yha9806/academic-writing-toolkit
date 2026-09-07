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
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
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
  // Kept alongside the run-it test below, which does not cover this: that one
  // picks the interpreter itself from `process.platform`, so it passes however
  // the skill spells the command. This one reads what the skill tells a reader
  // to type. Both matter — a helper that runs under the interpreter CI chose is
  // not the same claim as an instruction a macOS reader can follow.
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
  assert.deepEqual(report.chapters.map(({ words }: { words: number }) => words), [5, 0])
  assert.equal(report.chapters.length, 2)
})
