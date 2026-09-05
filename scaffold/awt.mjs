#!/usr/bin/env node
// awt — thesis-workspace scaffold and verification ladder (P2 spec items 3-4,
// eco adoptions #4 and #6).
//
//   node scaffold/awt.mjs init <dir>     create a clean thesis workspace
//   node scaffold/awt.mjs verify <dir>   run the verification ladder
//
// `init` scaffolds ONLY workspace files (chapters/, literature/reading_notes/
// with the notes template, contracts/, AGENTS.md + CLAUDE.md config,
// .agents/skills links to the product's 9 canonical skills) — zero
// toolkit-dev files, closing the split-identity finding. It never overwrites:
// an existing non-empty target is a typed refusal, not a merge (the
// preset-package discipline: validate, then write, never clobber).
//
// `verify` runs the ecosystem-standard ladder (create-dsh-plugin --verify
// shape): guards typecheck+build → offline notes-lint smoke → profile
// composition proof (`--dump-config` on a scratch DSH_HOME contains every
// AWT row) → scripted-adapter denial evidence (the live e2e table). Every
// stage fails loudly with a typed code and a remedy; a stage whose tools are
// missing REFUSES rather than skipping (inert verification would be the same
// lie as an inert guard). All dsh activity runs on throwaway DSH_HOME roots
// and throwaway workspaces — never the author's real thesis profile.

import { spawnSync } from 'node:child_process'
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync,
  rmSync, symlinkSync, linkSync, writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, isAbsolute, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')
const TEMPLATE_SRC = join(PRODUCT_ROOT, 'literature', 'reading_notes', '_template_NOTES.md')
const GUARDS_DIR = join(PRODUCT_ROOT, 'guards')
const E2E_DIR = join(PRODUCT_ROOT, 'e2e')
const PROFILE_SRC = join(PRODUCT_ROOT, 'profiles', 'awt-headless')
const DSH_BIN = join(E2E_DIR, 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js')
const RUN_TIMEOUT_MS = 300_000

// --- typed failure -----------------------------------------------------------------

class AwtError extends Error {
  /** @param {string} code @param {string} message @param {string} [remedy] */
  constructor(code, message, remedy) {
    super(message)
    this.code = code
    this.remedy = remedy
  }
}

function fail(error) {
  console.error(`${error.code ?? 'AWT_UNEXPECTED'}: ${error.message}`)
  if (error.remedy) console.error(`  remedy: ${error.remedy}`)
  process.exit(1)
}

// --- init --------------------------------------------------------------------------

const WORKSPACE_CONFIG = `# Academic Writing Workspace

This workspace was created by \`awt init\`. It holds thesis content only —
toolkit development files never belong here.

## Directories
- Chapters: \`chapters/\`
- Literature PDFs: \`literature/\`
- Reading notes: \`literature/reading_notes/\` (template: \`_template_NOTES.md\`)
- Edit contracts: \`contracts/\`
- On-demand reference documents: \`references/\` (linked to the toolkit)

## Reading constraints (enforced by AWT guards when run under dsh)
- Max pages per read invocation: 15
- Max pages per conversation: 90
- No chapter write may cite a source without a conforming notes file
- Text inside quotation spans of existing chapters is immutable

## Writing principles (advisory)
- Read first, write later — complete reading notes before editing chapters
- One notes file per source, following the template format
- Use British English for thesis text
- Citation style: harvard

## Skills
The AWT skill catalogue is linked at \`.agents/skills/\` (discovered by dsh;
Claude Code and Codex read the same files).
`

function init(target) {
  if (target === undefined) throw new AwtError('AWT_INIT_USAGE', 'usage: awt init <dir>')
  const ws = resolve(target)
  if (existsSync(ws) && readdirSync(ws).length > 0) {
    throw new AwtError(
      'AWT_INIT_TARGET_EXISTS',
      `refusing to scaffold into non-empty directory: ${ws}`,
      'pick a new directory; init never merges into or overwrites an existing workspace',
    )
  }
  if (!existsSync(SKILLS_SRC)) {
    throw new AwtError('AWT_INIT_SKILLS_MISSING', `product skill catalogue not found at ${SKILLS_SRC}`)
  }
  if (!existsSync(TEMPLATE_SRC)) {
    throw new AwtError('AWT_INIT_TEMPLATE_MISSING', `notes template not found at ${TEMPLATE_SRC}`)
  }

  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })
  mkdirSync(join(ws, '.agents', 'skills'), { recursive: true })

  cpSync(TEMPLATE_SRC, join(ws, 'literature', 'reading_notes', '_template_NOTES.md'))
  writeFileSync(join(ws, 'AGENTS.md'), WORKSPACE_CONFIG)
  // Claude Code reads CLAUDE.md; one file is the source, the other a link.
  // Windows hard links and directory junctions do not need Developer Mode.
  if (process.platform === 'win32') linkSync(join(ws, 'AGENTS.md'), join(ws, 'CLAUDE.md'))
  else symlinkSync('AGENTS.md', join(ws, 'CLAUDE.md'))

  const skills = readdirSync(SKILLS_SRC, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()
  if (skills.length === 0) throw new AwtError('AWT_INIT_SKILLS_MISSING', `no skills found under ${SKILLS_SRC}`)
  symlinkSync(join(PRODUCT_ROOT, 'references'), join(ws, 'references'), process.platform === 'win32' ? 'junction' : 'dir')
  for (const name of skills) {
    symlinkSync(join(SKILLS_SRC, name), join(ws, '.agents', 'skills', name), process.platform === 'win32' ? 'junction' : 'dir')
  }

  console.log(`workspace created: ${ws}`)
  console.log(`  chapters/  literature/reading_notes/  contracts/  references/ (link)  .agents/skills (${skills.length} links)  AGENTS.md  CLAUDE.md`)
  console.log(`next: node ${relativeToCwd(join(PRODUCT_ROOT, 'scaffold', 'awt.mjs'))} verify ${target}`)
}

function relativeToCwd(path) {
  const cwd = process.cwd()
  return path.startsWith(cwd) ? path.slice(cwd.length + 1) : path
}

// --- install-profile ---------------------------------------------------------------

/**
 * Copy the canonical AWT profiles (awt-headless and awt-web) plus the built
 * guards bundle into a real $DSH_HOME (default ~/.dsh). Both profiles share
 * the same patch rows — guards, read_pdf, apiKeyEnv routes — and differ
 * only in bundles (headless runner vs the dsh web UI). Never merges: an
 * existing profile is a typed refusal — remove it first to upgrade.
 */
function installProfile(targetHome) {
  const home = resolve(targetHome ?? process.env.DSH_HOME ?? join(process.env.HOME ?? '', '.dsh'))
  const guardsDist = join(GUARDS_DIR, 'dist')
  if (!existsSync(join(guardsDist, 'dsh-plugin.js'))) {
    throw new AwtError('AWT_PROFILE_GUARDS_UNBUILT', `built guards bundle missing at ${guardsDist}`, `cd ${GUARDS_DIR} && npm install && npm run build`)
  }
  for (const name of ['awt-headless', 'awt-web']) {
    const target = join(home, 'profiles', name)
    if (existsSync(target)) {
      throw new AwtError(
        'AWT_PROFILE_EXISTS',
        `refusing to overwrite the existing profile at ${target}`,
        'remove that directory first (upgrades reinstall, never merge in place)',
      )
    }
    mkdirSync(target, { recursive: true })
    cpSync(join(PRODUCT_ROOT, 'profiles', name, 'package.json'), join(target, 'package.json'))
    for (const shared of ['cordis.patch.yml', 'awt-read-pdf.plugin.mjs', 'pdf-pages.mjs', 'awt-brand.plugin.mjs', 'awt-export.plugin.mjs']) {
      cpSync(join(PROFILE_SRC, shared), join(target, shared))
    }
    cpSync(guardsDist, join(target, 'awt-guards'), { recursive: true })
    console.log(`profile installed: ${target}`)
  }
  console.log('  routes need DEEPSEEK_API_KEY or ANTHROPIC_API_KEY in the environment at run time (never in files)')
  console.log(`verify composition: DSH_HOME=${home} npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-headless --dump-config | grep awt-guards`)
  console.log(`web UI: run from your workspace — DSH_HOME=${home} npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-web --host 127.0.0.1 --port 3180`)
}

// --- verify ------------------------------------------------------------------------

/** Run one ladder stage; on child failure raise typed with the output tail. */
function run(code, command, args, options) {
  const res = spawnSync(command, args, { encoding: 'utf8', timeout: RUN_TIMEOUT_MS, ...options })
  if (res.error) throw new AwtError(code, `${command} failed to spawn: ${res.error.message}`)
  if (res.status !== 0) {
    const tail = `${res.stdout ?? ''}\n${res.stderr ?? ''}`.trim().split('\n').slice(-12).join('\n')
    throw new AwtError(code, `exited ${res.status ?? `signal ${res.signal}`}\n${tail}`)
  }
  return res
}

function buildScratchProfileHome(workspace) {
  const home = mkdtempSync(join(tmpdir(), 'awt-verify-home-'))
  const profile = join(home, 'profiles', 'awt-headless')
  mkdirSync(profile, { recursive: true })
  cpSync(join(E2E_DIR, 'profile', 'package.json'), join(profile, 'package.json'))
  cpSync(join(E2E_DIR, 'profile', 'cordis.patch.yml'), join(profile, 'cordis.patch.yml'))
  cpSync(join(E2E_DIR, 'plugins', 'awt-scripted-llm.plugin.mjs'), join(profile, 'awt-scripted-llm.plugin.mjs'))
  cpSync(join(E2E_DIR, 'plugins', 'awt-read-pdf-stub.plugin.mjs'), join(profile, 'awt-read-pdf-stub.plugin.mjs'))
  cpSync(join(GUARDS_DIR, 'dist'), join(profile, 'awt-guards'), { recursive: true })
  return home
}

async function verify(target) {
  if (target === undefined) throw new AwtError('AWT_VERIFY_USAGE', 'usage: awt verify <dir>')
  const ws = resolve(target)
  for (const marker of ['chapters', join('literature', 'reading_notes'), join('.agents', 'skills')]) {
    if (!existsSync(join(ws, marker))) {
      throw new AwtError(
        'AWT_VERIFY_NOT_WORKSPACE',
        `${ws} is not an AWT workspace (missing ${marker})`,
        'run `awt init <dir>` first, or point verify at the workspace init created',
      )
    }
  }

  const stages = []
  const record = (stage, detail) => {
    stages.push([stage, detail])
    console.log(`✔ ${stage}: ${detail}`)
  }

  // 1. typecheck + build (tsc does both; the built dist IS the shipped plugin)
  if (!existsSync(join(GUARDS_DIR, 'node_modules'))) {
    throw new AwtError('AWT_VERIFY_GUARDS_DEPS', 'guards/node_modules missing', `cd ${GUARDS_DIR} && npm install`)
  }
  run('AWT_VERIFY_BUILD', process.execPath, [join(GUARDS_DIR, 'node_modules', 'typescript', 'bin', 'tsc'), '-p', 'tsconfig.json'], { cwd: GUARDS_DIR })
  record('build', 'guards typecheck + build green (tsc)')

  // 2. offline notes-lint smoke: the linter must discriminate (an empty file
  // fails), and every real notes file in the workspace must pass.
  const lint = await import(pathToFileURL(join(GUARDS_DIR, 'dist', 'notes-lint.js')).href)
  if (!lint.hasErrors(lint.lintNotes(''))) {
    throw new AwtError('AWT_VERIFY_LINT_SMOKE', 'notes lint accepted an empty file — the linter is not discriminating')
  }
  const notesDir = join(ws, 'literature', 'reading_notes')
  const notesFiles = readdirSync(notesDir).filter((f) => f.endsWith('_NOTES.md') && f !== '_template_NOTES.md')
  for (const file of notesFiles) {
    const issues = lint.lintNotes(readFileSync(join(notesDir, file), 'utf8'))
    if (lint.hasErrors(issues)) {
      const first = issues.find((i) => i.severity === 'error')
      throw new AwtError('AWT_VERIFY_NOTES_LINT', `${file}:${first.line} ${first.code}: ${first.message}`)
    }
  }
  record('notes-lint', `linter discriminates; ${notesFiles.length} workspace notes file(s) pass`)

  // 3. profile composition proof: --dump-config on a scratch DSH_HOME must
  // carry every AWT row (composes offline; no boot, no credentials).
  if (!existsSync(DSH_BIN)) {
    throw new AwtError('AWT_VERIFY_DSH_MISSING', `pinned dsh launcher missing at ${DSH_BIN}`, `cd ${E2E_DIR} && npm ci`)
  }
  const home = buildScratchProfileHome(ws)
  try {
    const dump = run('AWT_VERIFY_DUMP_CONFIG', process.execPath,
      [DSH_BIN, '--profile', 'awt-headless', '--dump-config'],
      { cwd: ws, env: { ...process.env, DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1', AWT_E2E_WORKSPACE: ws } })
    for (const row of ['awt-guards', 'awt-scripted-llm', 'awt-read-pdf-stub']) {
      if (!dump.stdout.includes(row)) {
        throw new AwtError('AWT_VERIFY_DUMP_CONFIG', `--dump-config is missing the ${row} row`)
      }
    }
    if (/FAILED/i.test(dump.stdout)) {
      throw new AwtError('AWT_VERIFY_DUMP_CONFIG', '--dump-config reports a FAILED row')
    }
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
  record('dump-config', 'awt-guards + scripted adapter + read_pdf stub rows compose')

  // 4. scripted-adapter denial evidence: the live e2e table (five scenarios,
  // throwaway workspaces + DSH_HOME roots; exit 0 only when every typed
  // denial and the negative control hold).
  run('AWT_VERIFY_E2E', process.execPath, ['run-e2e.mjs'], { cwd: E2E_DIR })
  record('scripted-denial', 'live e2e evidence table green (6 scenarios)')

  // 5. credential discipline (P3, keyless): a configured apiKeyEnv reference
  // that resolves to nothing must fail typed (MISSING_CREDENTIAL), never
  // fall through to ambient keys.
  run('AWT_VERIFY_CREDENTIAL', process.execPath, ['run-credential-probe.mjs'], { cwd: E2E_DIR })
  record('credential-probe', 'MISSING_CREDENTIAL fails typed and keyless')

  console.log(`\nVERIFY PASSED (${stages.length}/5): ${ws}`)
}

// --- entry -------------------------------------------------------------------------

const [command, target] = process.argv.slice(2)
try {
  if (command === 'init') init(target)
  else if (command === 'verify') await verify(target)
  else if (command === 'install-profile') installProfile(target)
  else fail(new AwtError('AWT_USAGE', 'usage: awt <init|verify> <dir> | awt install-profile [dsh-home]'))
} catch (error) {
  fail(error instanceof AwtError ? error : new AwtError('AWT_UNEXPECTED', error?.stack ?? String(error)))
}
