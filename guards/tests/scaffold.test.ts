// `awt init` manifest gate (P2 spec item 4): the scaffolded workspace
// contains EXACTLY the thesis-workspace files — asserted as a full recursive
// manifest, so any toolkit-dev file leaking into the scaffold (the
// split-identity finding) is a red test, not a review comment. Also pins the
// never-overwrite refusal and verify's not-a-workspace refusal.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { cpSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, readlinkSync, realpathSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const AWT = resolve(import.meta.dirname, '..', '..', 'scaffold', 'awt.mjs')
const TEMPLATE = resolve(import.meta.dirname, '..', '..', 'literature', 'reading_notes', '_template_NOTES.md')

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

test('install-profile lands both canonical profiles in a DSH_HOME and refuses to overwrite', () => {
  const home = scratch()
  const res = awt('install-profile', home)
  assert.equal(res.status, 0, res.stderr)
  for (const name of ['awt-headless', 'awt-web']) {
    const profile = join(home, 'profiles', name)
    for (const file of ['package.json', 'cordis.patch.yml', 'awt-read-pdf.plugin.mjs', join('awt-guards', 'dsh-plugin.js')]) {
      assert.ok(lstatSync(join(profile, file)).isFile(), `${name}: missing ${file}`)
    }
    // No secret material anywhere in the installed profile files.
    const patch = readFileSync(join(profile, 'cordis.patch.yml'), 'utf8')
    assert.match(patch, /apiKeyEnv/)
    assert.doesNotMatch(patch, /sk-|api[-_]?key\s*[:=]\s*['"][A-Za-z0-9]/i)
  }
  // The two profiles differ ONLY in bundles: same guard rows, same routes.
  const headless = JSON.parse(readFileSync(join(home, 'profiles', 'awt-headless', 'package.json'), 'utf8'))
  const web = JSON.parse(readFileSync(join(home, 'profiles', 'awt-web', 'package.json'), 'utf8'))
  assert.deepEqual(headless.dsh.profile.bundles, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-headless'])
  assert.deepEqual(web.dsh.profile.bundles, ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app'])
  assert.equal(
    readFileSync(join(home, 'profiles', 'awt-headless', 'cordis.patch.yml'), 'utf8'),
    readFileSync(join(home, 'profiles', 'awt-web', 'cordis.patch.yml'), 'utf8'),
    'the enforcement patch must be identical across surfaces',
  )

  const again = awt('install-profile', home)
  assert.notEqual(again.status, 0)
  assert.match(again.stderr, /AWT_PROFILE_EXISTS/)
})

/**
 * A throwaway product root holding only what `init` reads: the scaffold entry
 * point, the notes template, and a catalogue built to order. `true` makes a
 * real skill (a directory with a SKILL.md); `false` makes a bare directory.
 */
function productRoot(catalogue: Record<string, boolean>, harnessVersion?: string): string {
  const root = scratch()
  mkdirSync(join(root, 'scaffold'), { recursive: true })
  cpSync(AWT, join(root, 'scaffold', 'awt.mjs'))
  cpSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), join(root, 'COMPAT.json'))
  mkdirSync(join(root, 'literature', 'reading_notes'), { recursive: true })
  cpSync(TEMPLATE, join(root, 'literature', 'reading_notes', '_template_NOTES.md'))
  for (const [name, isSkill] of Object.entries(catalogue)) {
    const dir = join(root, '.claude', 'skills', name, 'scripts')
    mkdirSync(dir, { recursive: true })
    if (isSkill) writeFileSync(join(root, '.claude', 'skills', name, 'SKILL.md'), `---\nname: ${name}\n---\n`)
  }
  if (harnessVersion !== undefined) {
    // A launcher that prints its argv, so forwarding is observable and no
    // real harness (or credential) is needed to test launch's preconditions.
    const pkg = join(root, 'harness', 'node_modules', '@deepseek-ai', 'dsh')
    mkdirSync(join(pkg, 'lib'), { recursive: true })
    writeFileSync(join(pkg, 'lib', 'bin.js'), 'console.log(JSON.stringify(process.argv.slice(2)))\n')
    writeFileSync(join(pkg, 'package.json'), JSON.stringify({ version: harnessVersion }))
  }
  return join(root, 'scaffold', 'awt.mjs')
}

test('init refuses a catalogue directory with no SKILL.md — build residue never becomes an extra skill', () => {
  // A retired skill whose sources are gone but whose __pycache__ survives is
  // invisible to `git status` and to every tracked-tree test, but readdir
  // still sees the directory. Linking it hands the model a catalogue entry
  // that resolves to nothing.
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

// --- awt web / awt run: the supported launch path ----------------------------------
// The launcher lives in the TOOLKIT CHECKOUT, not in $DSH_HOME: dsh owns
// $DSH_HOME/profiles/node_modules and heals it from the installation it was
// launched out of, rejecting a real directory placed there. An earlier version
// of these tests hand-built the launcher under a scratch $DSH_HOME and
// asserted in a comment that install-profile put it there. It never did, and
// the mock made a blocks-use gap untestable: on any machine that had run dsh
// before, launch worked; on every clean one it refused.

function awtAt(entry: string, home: string, ...args: string[]) {
  return spawnSync(process.execPath, [entry, ...args], {
    encoding: 'utf8', timeout: 60_000, env: { ...process.env, DSH_HOME: home },
  })
}

/** A $DSH_HOME holding only installed profile directories — no launcher. */
function dshHome(profile?: string): string {
  const home = scratch()
  if (profile) mkdirSync(join(home, 'profiles', profile), { recursive: true })
  return home
}

test('launch refuses when the harness was never installed into the checkout', () => {
  const entry = productRoot({ note: true })            // no harness/
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const res = awtAt(entry, dshHome('awt-headless'), 'run', ws, 'anything')
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_LAUNCH_HARNESS_MISSING/)
  assert.match(res.stderr, /install-profile/)
})

test('launch refuses a harness that is not the COMPAT-pinned version', () => {
  // Silently launching a different harness would void every attested gate.
  const entry = productRoot({ note: true }, '0.1.2-rc.1')
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const res = awtAt(entry, dshHome('awt-headless'), 'run', ws, 'anything')
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_LAUNCH_HARNESS_UNPINNED/)
  assert.match(res.stderr, /0\.1\.2-rc\.1/)
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  assert.match(res.stderr, new RegExp(pinned.replace(/\./g, '\\.')))
})

test('web refuses when the profile was never installed into DSH_HOME', () => {
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  const entry = productRoot({ note: true }, pinned)
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const res = awtAt(entry, dshHome(), 'web', ws)
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_LAUNCH_PROFILE_MISSING/)
  assert.match(res.stderr, /install-profile/)
})

test('web refuses a directory that is not an AWT workspace', () => {
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  const entry = productRoot({ note: true }, pinned)
  const res = awtAt(entry, dshHome('awt-web'), 'web', scratch())
  assert.notEqual(res.status, 0)
  assert.match(res.stderr, /AWT_LAUNCH_NOT_WORKSPACE/)
})

test('run refuses without a task, and web without a workspace', () => {
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  const entry = productRoot({ note: true }, pinned)
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const home = dshHome('awt-headless')
  assert.match(awtAt(entry, home, 'run', ws).stderr, /AWT_LAUNCH_USAGE/)
  assert.match(awtAt(entry, home, 'web').stderr, /AWT_LAUNCH_USAGE/)
})

test('launch forwards everything after `--` to the harness, so documented overlays work', () => {
  // The runbook tells authors to select a model with the launcher's --patch
  // overlay; silently dropping extra argv would make that impossible.
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  const entry = productRoot({ note: true }, pinned)
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const res = awtAt(entry, dshHome('awt-headless'), 'run', ws, 'a task', '--', '--patch', 'model.yml')
  assert.equal(res.status, 0, res.stderr)
  assert.deepEqual(JSON.parse(res.stdout), ['--profile', 'awt-headless', 'a task', '--patch', 'model.yml'])
})

test('web forwards after `--` too, and keeps its port argument', () => {
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  const entry = productRoot({ note: true }, pinned)
  const ws = join(scratch(), 'ws')
  spawnSync(process.execPath, [entry, 'init', ws], { encoding: 'utf8', timeout: 60_000 })
  const res = awtAt(entry, dshHome('awt-web'), 'web', ws, '3199', '--', '--patch', 'model.yml')
  assert.equal(res.status, 0, res.stderr)
  assert.deepEqual(JSON.parse(res.stdout), ['--profile', 'awt-web', '--host', '127.0.0.1', '--port', '3199', '--patch', 'model.yml'])
})

test('install-profile installs the pinned launcher, so the next command can actually start', () => {
  // The gap this closes: install-profile wrote only the profile directories,
  // and the launcher was assumed to exist under $DSH_HOME. On a clean machine
  // both `awt run` and `awt web` refused. Needs the network on a cold checkout.
  const home = scratch()
  const res = awt('install-profile', home)
  assert.equal(res.status, 0, res.stderr)
  const pkgRoot = resolve(import.meta.dirname, '..', '..', 'harness', 'node_modules', '@deepseek-ai', 'dsh')
  assert.ok(lstatSync(join(pkgRoot, 'lib', 'bin.js')).isFile(), 'no launcher in the toolkit harness')
  const pinned = JSON.parse(readFileSync(resolve(import.meta.dirname, '..', '..', 'COMPAT.json'), 'utf8')).harness.split('@').pop()
  assert.equal(JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8')).version, pinned)
  // And what it tells the user to run next must be the supported commands.
  assert.doesNotMatch(res.stdout, /npx/, 'install-profile still advertises the npx launch path')
  assert.match(res.stdout, /awt\.mjs (web|run)/)
})
