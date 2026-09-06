// Skill-scope probe (#33) — KEYLESS. A session booted with the canonical AWT
// profile must offer exactly the workspace catalogue: decoy skills planted in
// both user-level roots dsh scans by default ($DSH_HOME/skills and
// ~/.agents/skills) must be invisible to the model, while a canonical skill
// linked in the workspace must be visible. Observed in the persisted session
// log (the skill catalog is model-visible context, so it is logged).

import { spawnSync } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const E2E_DIR = resolve(import.meta.dirname)
const ROOT = resolve(E2E_DIR, '..')
const PROFILE_SRC = join(ROOT, 'profiles', 'awt-headless')
const GUARDS_DIST = join(ROOT, 'guards', 'dist')
const SKILLS_SRC = join(ROOT, '.claude', 'skills')
const DSH_BIN = join(E2E_DIR, 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js')

function fail(msg) { console.error(`SKILL SCOPE PROBE FAILED: ${msg}`); process.exit(1) }
if (!existsSync(DSH_BIN)) fail('pinned dsh launcher missing — npm ci in e2e/')
if (!existsSync(join(GUARDS_DIST, 'dsh-plugin.js'))) fail('guards/dist missing — npm run build in guards/')

const decoySkill = (dir, name) => {
  mkdirSync(join(dir, name), { recursive: true })
  writeFileSync(join(dir, name, 'SKILL.md'), `---\nname: ${name}\ndescription: Decoy skill that must never reach an AWT session (${name}).\n---\n\n# ${name}\n`)
}

const scratch = mkdtempSync(join(tmpdir(), 'awt-skill-scope-'))
try {
  const home = join(scratch, 'dsh-home')
  const userHome = join(scratch, 'user-home')
  const ws = join(scratch, 'workspace')

  // Decoys in both user-level roots the default provider scans.
  decoySkill(join(home, 'skills'), 'decoy-dsh-skill')
  decoySkill(join(userHome, '.agents', 'skills'), 'decoy-user-skill')

  // Canonical profile + the keyless overlay the E1 offline lane uses.
  const profile = join(home, 'profiles', 'awt-headless')
  mkdirSync(profile, { recursive: true })
  cpSync(join(PROFILE_SRC, 'package.json'), join(profile, 'package.json'))
  for (const f of readdirSync(PROFILE_SRC).filter((n) => n.endsWith('.mjs'))) cpSync(join(PROFILE_SRC, f), join(profile, f))
  cpSync(GUARDS_DIST, join(profile, 'awt-guards'), { recursive: true })
  cpSync(join(ROOT, 'e1', 'plugins', 'awt-e1-scripted-llm.plugin.mjs'), join(profile, 'awt-e1-scripted-llm.plugin.mjs'))
  let patch = readFileSync(join(PROFILE_SRC, 'cordis.patch.yml'), 'utf8')
    .replace('provider: deepseek', 'provider: scripted').replace('model: deepseek-v4-flash', 'model: scripted-1')
  patch += `
- id: session-persistence-jsonl
  config:
    root: !!js dshHomePath('sessions')
    compression: none

- insert:
    - id: awt-e1-scripted-llm
      name: './awt-e1-scripted-llm.plugin.mjs'
`
  writeFileSync(join(profile, 'cordis.patch.yml'), patch)

  // A workspace with the canonical catalogue linked, as awt init lays it out.
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })
  mkdirSync(join(ws, '.agents', 'skills'), { recursive: true })
  for (const name of readdirSync(SKILLS_SRC)) symlinkSync(join(SKILLS_SRC, name), join(ws, '.agents', 'skills', name))

  const res = spawnSync(process.execPath, [DSH_BIN, '--profile', 'awt-headless', 'List the skills you can see.'], {
    cwd: ws,
    env: { PATH: process.env.PATH, LANG: 'en_US.UTF-8', HOME: userHome, DSH_HOME: home, DSH_AGENTS_HOME: join(userHome, '.agents'), DSH_TELEMETRY_DISABLED: '1' },
    encoding: 'utf8', timeout: 120_000,
  })
  if (res.status !== 0) fail(`dsh exited ${res.status}: ${(res.stderr ?? '').split('\n').slice(-4).join(' | ')}`)

  const logs = []
  const walk = (d) => { for (const n of readdirSync(d, { withFileTypes: true })) { const p = join(d, n.name); n.isDirectory() ? walk(p) : (n.name.endsWith('.jsonl') && logs.push(readFileSync(p, 'utf8'))) } }
  walk(join(home, 'sessions'))
  const all = logs.join('\n')
  const problems = []
  if (!all.includes('verify-refs')) problems.push('the workspace catalogue is NOT visible (verify-refs absent from the session log)')
  for (const decoy of ['decoy-dsh-skill', 'decoy-user-skill']) if (all.includes(decoy)) problems.push(`${decoy} leaked into the session (user-level skill root is being scanned)`)
  if (problems.length) fail(problems.join('; '))
  console.log('SKILL SCOPE PROBE GREEN: the session sees the workspace catalogue and neither user-level decoy')
} finally {
  rmSync(scratch, { recursive: true, force: true })
}
