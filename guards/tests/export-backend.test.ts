// Gate A item 2: the export path must fail where it is checked, not where it
// is used.
//
// `make doctor` reported a healthy environment on a machine where `/export`
// could not run, because it probed proxies — the `pandoc` binary and
// `python-docx` — rather than the capability. The converter needs pypandoc
// (the Python binding, not the binary) OR python-docx *and* markdown, and a
// machine can satisfy every proxy while satisfying neither backend. It did
// here. The converter is the only thing that knows whether it can convert, so
// it is what gets asked.
//
// The remedy also has to be one a reader can run: a bare `pip install` is
// refused by any PEP 668 interpreter, which is the default on Homebrew Python
// and on current Debian and Ubuntu.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, realpathSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')
const CONVERTER = join(PRODUCT_ROOT, '.claude', 'skills', 'export', 'scripts', 'convert_to_docx.py')
const DOCTOR = join(PRODUCT_ROOT, 'scripts', 'doctor.sh')

const dirs: string[] = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

/** An interpreter with no site-packages at all — no backend can be present. */
function bareInterpreter(): string {
  const dir = mkdtempSync(join(tmpdir(), 'awt-bare-py-'))
  dirs.push(dir)
  const made = spawnSync('python3', ['-m', 'venv', '--without-pip', join(dir, 'venv')], { encoding: 'utf8', timeout: 120_000 })
  assert.equal(made.status, 0, made.stderr)
  return join(dir, 'venv', 'bin', 'python')
}

/** An interpreter that definitely has a backend, built rather than assumed. */
function backedInterpreter(): string {
  const dir = mkdtempSync(join(tmpdir(), 'awt-backed-py-'))
  dirs.push(dir)
  const venv = join(dir, 'venv')
  const made = spawnSync('python3', ['-m', 'venv', venv], { encoding: 'utf8', timeout: 120_000 })
  assert.equal(made.status, 0, made.stderr)
  const installed = spawnSync(join(venv, 'bin', 'pip'), ['install', '--quiet', 'python-docx', 'markdown'], { encoding: 'utf8', timeout: 300_000 })
  assert.equal(installed.status, 0, installed.stderr)
  return join(venv, 'bin', 'python')
}

test('the converter can be asked whether it can convert, without converting', () => {
  // Built rather than assumed: an earlier version of this test asked the
  // system interpreter, which passes in CI (the workflow installs the backend)
  // and fails on a contributor's machine that happens to lack it — the shape
  // of green this project has been bitten by twice.
  const res = spawnSync(backedInterpreter(), [CONVERTER, '--check'], { encoding: 'utf8', timeout: 60_000 })
  assert.equal(res.status, 0, `--check should succeed where a backend exists:\n${res.stdout}${res.stderr}`)
  assert.match(res.stdout, /pypandoc|python-docx/, 'it should name the backend it found')
})

test('an interpreter with no backend fails the check, and says so before any conversion', () => {
  const res = spawnSync(bareInterpreter(), [CONVERTER, '--check'], { encoding: 'utf8', timeout: 60_000 })
  assert.notEqual(res.status, 0, 'a missing backend must not report success')
  assert.match(res.stdout + res.stderr, /backend/i)
})

test('the remedy works on a PEP 668 interpreter — no bare pip install', () => {
  // `pip install python-docx markdown` is refused as externally-managed on
  // Homebrew Python and on current Debian/Ubuntu, which is where this reader is.
  const out = spawnSync(bareInterpreter(), [CONVERTER, '--check'], { encoding: 'utf8', timeout: 60_000 })
  const message = out.stdout + out.stderr
  assert.match(message, /venv|--break-system-packages|pipx/, `the remedy must survive PEP 668:\n${message}`)
})

test('doctor reports the export path as broken when the converter cannot run', () => {
  // The regression this pins: doctor said "all checks pass" while /export failed.
  const res = spawnSync('bash', [DOCTOR], {
    encoding: 'utf8', timeout: 300_000, cwd: PRODUCT_ROOT,
    env: { ...process.env, AWT_PYTHON: bareInterpreter() },
  })
  assert.notEqual(res.status, 0, `doctor must not pass when /export cannot run:\n${res.stdout}`)
  assert.match(res.stdout, /export|convert/i)
})

// --- which interpreter the app spawns ---------------------------------------
// `awt verify` being honest about the backend is worth little if the app then
// spawns a different interpreter. The workspace reaches the converter through
// a link into the toolkit, so the interpreter that can run it is the toolkit's.

test('the app runs the converter with the toolkit interpreter, not the workspace one', async () => {
  const { exportInterpreter } = await import(
    pathToFileURL(join(PRODUCT_ROOT, 'profiles', 'awt-headless', 'export-interpreter.mjs')).href
  )
  const dir = mkdtempSync(join(tmpdir(), 'awt-export-interp-'))
  dirs.push(dir)

  // A toolkit whose .venv exists, reached through a workspace-style link.
  const toolkit = join(dir, 'toolkit')
  const scriptDir = join(toolkit, '.claude', 'skills', 'export', 'scripts')
  mkdirSync(scriptDir, { recursive: true })
  writeFileSync(join(scriptDir, 'convert_to_docx.py'), '')
  const venv = join(toolkit, '.venv', 'bin')
  mkdirSync(venv, { recursive: true })
  writeFileSync(join(venv, 'python'), '')

  const ws = join(dir, 'thesis', '.agents', 'skills')
  mkdirSync(ws, { recursive: true })
  symlinkSync(join(toolkit, '.claude', 'skills', 'export'), join(ws, 'export'), 'dir')

  const throughLink = join(ws, 'export', 'scripts', 'convert_to_docx.py')
  // The helper resolves through realpath, and on macOS the temp root is itself
  // a symlink (/var -> /private/var), so the expectation canonicalises too.
  const canonicalToolkit = realpathSync(toolkit)
  assert.equal(exportInterpreter(throughLink, { env: {} }), join(canonicalToolkit, '.venv', 'bin', 'python'))

  // No .venv in the toolkit: fall back rather than invent a path.
  rmSync(join(toolkit, '.venv'), { recursive: true, force: true })
  assert.equal(exportInterpreter(throughLink, { env: {} }), 'python3')

  // An explicit interpreter always wins.
  assert.equal(exportInterpreter(throughLink, { env: { AWT_PYTHON: '/usr/bin/python3.11' } }), '/usr/bin/python3.11')
})
