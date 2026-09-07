#!/usr/bin/env node
// Native setup for every supported platform. The make/Bash entrypoints call
// this same implementation; no shell, symlink privilege or global pip needed.
import { spawnSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, renameSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const WINDOWS = process.platform === 'win32'
const SKILLS = join(ROOT, '.claude', 'skills')
const AGENTS = join(ROOT, '.agents', 'skills')
const CONVERTER = join(SKILLS, 'export', 'scripts', 'convert_to_docx.py')
const VENV = join(ROOT, '.venv')
const VENV_PYTHON = join(VENV, WINDOWS ? 'Scripts' : 'bin', WINDOWS ? 'python.exe' : 'python')
const info = (message) => console.log(`  [✓] ${message}`)
const hint = (message) => console.log(`       fix: ${message}`)

function run(command, args, options = {}) {
  return spawnSync(command, args, { cwd: ROOT, encoding: 'utf8', timeout: 300_000, maxBuffer: 8 * 1024 * 1024, ...options })
}

function checked(command, args) {
  const result = run(command, args)
  if (result.status !== 0) throw new Error(`${command} failed: ${result.error?.message ?? ''}\n${result.stdout ?? ''}${result.stderr ?? ''}`.trim())
  return result.stdout
}

function stat(path) {
  try { return lstatSync(path) } catch (error) { if (error.code === 'ENOENT') return undefined; throw error }
}

function insideRoot(path) {
  const rel = relative(ROOT, resolve(path))
  if (!rel || isAbsolute(rel) || rel === '..' || rel.startsWith('..\\') || rel.startsWith('../')) throw new Error(`path is outside the managed checkout: ${path}`)
}

function directory(path) {
  insideRoot(path)
  const entry = stat(path)
  if (entry && (!entry.isDirectory() || entry.isSymbolicLink())) throw new Error(`refusing to write through a linked/non-directory parent: ${path}`)
  if (!entry) mkdirSync(path)
}

function skillNames() {
  if (!existsSync(SKILLS)) throw new Error('.claude/skills/ directory missing')
  const names = readdirSync(SKILLS, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()
  if (!names.length) throw new Error('.claude/skills/ has no skill subdirectories')
  const strays = names.filter((name) => !existsSync(join(SKILLS, name, 'SKILL.md')))
  if (strays.length) throw new Error(`directories without SKILL.md: ${strays.join(', ')}; inspect and move retired cache-only directories out of .claude/skills before setup`)
  return names
}

function samePath(left, right) {
  return WINDOWS ? left.toLowerCase() === right.toLowerCase() : left === right
}

function validLink(path, target) {
  try {
    return Boolean(stat(path)?.isSymbolicLink() && samePath(realpathSync(path), realpathSync(target)) && stat(join(path, 'SKILL.md'))?.isFile())
  } catch { return false }
}

function placeholder(path, name) {
  const entry = stat(path)
  return !entry || (entry.isFile() && readFileSync(path, 'utf8').trim() === `../../.claude/skills/${name}`)
}

function goodSkill(name) {
  const target = join(SKILLS, name)
  const canonical = join(AGENTS, name)
  const alias = join(AGENTS, `awt-local-${name}`)
  // Do not let a good alias hide a wrong canonical directory, or vice versa.
  if (validLink(canonical, target)) return !WINDOWS || !stat(alias) || validLink(alias, target)
  return WINDOWS && placeholder(canonical, name) && validLink(alias, target)
}

function preserveOrUnlink(path) {
  insideRoot(path)
  const entry = stat(path)
  if (!entry) return
  if (entry.isSymbolicLink()) {
    // unlink removes the junction itself. Never recursively remove its target.
    unlinkSync(path)
    return
  }
  const backups = join(ROOT, '.awt-skill-backups')
  directory(backups)
  const backup = join(backups, `${randomUUID()}-${relative(AGENTS, path)}`)
  insideRoot(backup)
  renameSync(path, backup)
  info(`preserved existing skill entry at ${relative(ROOT, backup)}`)
}

function repairLinks() {
  const names = skillNames()
  if (names.every(goodSkill)) { info('skill links already intact'); return }
  try {
    directory(join(ROOT, '.agents'))
    directory(AGENTS)
    for (const name of names) {
      if (goodSkill(name)) continue
      const canonical = join(AGENTS, name)
      const target = join(SKILLS, name)
      const alias = join(AGENTS, `awt-local-${name}`)
      if (WINDOWS && placeholder(canonical, name)) {
        preserveOrUnlink(alias)
        symlinkSync(target, alias, 'junction')
      } else {
        preserveOrUnlink(canonical)
        symlinkSync(WINDOWS ? target : `../../.claude/skills/${name}`, canonical, WINDOWS ? 'junction' : 'dir')
        if (WINDOWS && stat(alias) && !validLink(alias, target)) {
          preserveOrUnlink(alias)
        }
      }
      if (!goodSkill(name)) throw new Error(`skill link did not resolve after repair: ${name}`)
    }
  } catch (error) { throw new Error(`cannot repair broken skill symlinks: ${error.message}`) }
  info(`skill links repaired (${names.length} canonical skills)`)
}

function generatedConfigs(input = join(ROOT, 'CLAUDE.md')) {
  const lines = readFileSync(input, 'utf8').split(/\r?\n/)
  const starts = lines.flatMap((line, index) => line === '<!-- SHARED:START -->' ? [index] : [])
  const ends = lines.flatMap((line, index) => line === '<!-- SHARED:END -->' ? [index] : [])
  if (starts.length !== 1 || ends.length !== 1 || starts[0] >= ends[0]) {
    throw new Error(`expected exactly one <!-- SHARED:START --> and one <!-- SHARED:END --> as standalone lines in ${input} (found start=${starts.length} end=${ends.length})`)
  }
  const shared = lines.slice(starts[0] + 1, ends[0]).join('\n').replace(/\n+$/, '')
  if (!shared) throw new Error('SHARED block is empty')
  return Object.fromEntries(['AGENTS', 'GEMINI'].map((name) => [
    `${name}.md`, readFileSync(join(ROOT, 'templates', `${name.toLowerCase()}-preamble.md`), 'utf8').replace(/\r\n/g, '\n') + shared + '\n',
  ]))
}

function sync(input, destination = ROOT) {
  const generated = generatedConfigs(input)
  if (!stat(destination)?.isDirectory()) throw new Error(`output dir not found: ${destination}`)
  for (const [name, body] of Object.entries(generated)) {
    const path = join(destination, name)
    writeFileSync(`${path}.new`, body)
    renameSync(`${path}.new`, path)
  }
  info('Synced AGENTS.md and GEMINI.md from CLAUDE.md')
}

function pythonCandidates() {
  const commands = process.env.AWT_PYTHON
    ? [[process.env.AWT_PYTHON]]
    : [[VENV_PYTHON], [WINDOWS ? 'python' : 'python3'], [WINDOWS ? 'python3' : 'python'], ...(WINDOWS ? [['py', '-3']] : [])]
  const found = []
  for (const [command, ...args] of commands) {
    const probe = run(command, [...args, '-X', 'utf8', '-c', 'import json,sys; print(json.dumps({"exe":sys.executable,"base":getattr(sys,"_base_executable",sys.executable),"version":list(sys.version_info[:2])}))'], { timeout: 15_000 })
    if (probe.status !== 0) continue
    try {
      const python = JSON.parse(probe.stdout.trim())
      if (python.version[0] === 3 && python.version[1] >= 8 && !found.some((p) => samePath(p.exe, python.exe))) found.push(python)
    } catch { /* A store alias or a non-Python command is not an interpreter. */ }
  }
  if (!found.length) throw new Error('Python 3.8+ not found; install native Python and put python (Windows) or python3 (macOS/Linux) on PATH, or set AWT_PYTHON to its executable')
  return found
}

function backend(python) { return run(python, ['-X', 'utf8', CONVERTER, '--check'], { timeout: 60_000 }) }

function setupExport() {
  const candidates = pythonCandidates()
  // An explicit runtime remains an explicit runtime; do not install into a
  // user's global environment or silently substitute a different interpreter.
  if (process.env.AWT_PYTHON) {
    if (backend(candidates[0].exe).status !== 0) throw new Error('AWT_PYTHON has no export backend; unset it to let setup prepare the project .venv, or prepare that explicitly selected environment first')
    info(`export backend already available (${candidates[0].exe})`)
    return
  }
  if (existsSync(VENV_PYTHON) && backend(VENV_PYTHON).status === 0) {
    info('export backend already available (.venv)')
    return
  }
  // Always prepare the interpreter the app and skill instructions can find.
  // Existing system packages do not prove this project has a usable runtime.
  const entry = stat(VENV)
  if (entry && (!entry.isDirectory() || entry.isSymbolicLink())) throw new Error('refusing to install through a linked/non-directory .venv')
  console.log('  creating .venv and installing the export backend...')
  checked(candidates[0].base, ['-m', 'venv', VENV])
  checked(VENV_PYTHON, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', join(SKILLS, 'export', 'scripts', 'requirements.txt')])
  if (backend(VENV_PYTHON).status !== 0) throw new Error('installed the requirements but the converter still reports no backend')
  info('export backend installed into .venv')
}

function gitConfig(repair = false) {
  if (run('git', ['rev-parse', '--is-inside-work-tree']).status !== 0) return undefined
  if (repair) checked('git', ['config', 'core.fileMode', 'false'])
  return run('git', ['config', '--get', 'core.fileMode']).stdout.trim()
}

function doctor() {
  console.log('Checking academic-writing-toolkit environment...')
  let failures = 0
  const fail = (message) => { failures++; console.log(`  [✗] ${message}`) }
  try {
    const names = skillNames()
    const broken = names.filter((name) => !goodSkill(name))
    for (const name of broken) fail(`skill symlink broken: .agents/skills/${name}`)
    if (!broken.length) info(`skill links intact (${names.length} skills; symlinks or Windows junctions)`)
    else hint('node scripts/setup.mjs repair')
  } catch (error) { fail(error.message) }
  const fileMode = gitConfig()
  if (fileMode === undefined) console.log('  [!] not in a git repo; skipping core.fileMode check')
  else if (fileMode === 'false') info('git core.fileMode disabled (no mode-bit noise commits)')
  else { fail(`git core.fileMode is '${fileMode}' (expected: false)`); hint('node scripts/setup.mjs repair') }
  try {
    const synced = Object.entries(generatedConfigs()).every(([name, body]) => existsSync(join(ROOT, name)) && readFileSync(join(ROOT, name), 'utf8') === body)
    if (synced) info('config sync (CLAUDE.md, AGENTS.md, GEMINI.md aligned)')
    else { fail('config sync — AGENTS.md or GEMINI.md drifted from CLAUDE.md'); hint('node scripts/setup.mjs sync') }
  } catch (error) { fail(`config sync — ${error.message}`) }
  try {
    const python = pythonCandidates()[0].exe
    const probe = backend(python)
    if (probe.status === 0) info(`/export can convert — ${probe.stdout.trim()}`)
    else { fail(`/export cannot convert: no backend for ${python}`); hint('node scripts/setup.mjs (or prepare the explicit AWT_PYTHON environment)') }
  } catch (error) { fail(`/export cannot convert: ${error.message}`) }
  if (!failures) info('all checks pass.')
  else console.log(`\n${failures} issue(s). Run \`node scripts/setup.mjs repair\` to fix links/config; setup installs the export backend.`)
  return failures ? 1 : 0
}

try {
  const [command = 'setup', ...args] = process.argv.slice(2)
  if (command === 'doctor') process.exitCode = doctor()
  else if (command === 'sync') sync(args[0] ? resolve(args[0]) : undefined, args[1] ? resolve(args[1]) : ROOT)
  else if (command === 'export-backend') setupExport()
  else if (command === 'setup' || command === 'repair') {
    repairLinks()
    gitConfig(true)
    sync()
    if (command === 'setup') setupExport()
    process.exitCode = doctor()
  } else throw new Error('usage: node scripts/setup.mjs [setup|doctor|repair|sync [input [outdir]]|export-backend]')
} catch (error) {
  console.error(`error: ${error.message}`)
  process.exitCode = 2
}
