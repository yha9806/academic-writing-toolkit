// Credential-discipline probe (P3 spec item 1, eco #8) — KEYLESS by design.
//
// Boots the CANONICAL awt-headless profile (profiles/awt-headless, real
// pi-ai routes with apiKeyEnv references — not the e2e's scripted profile)
// against the real published launcher, in an environment that provably
// holds no credential: scratch DSH_HOME, scratch HOME (so no user
// ~/.dsh/.credentials.yaml or ~/.env can leak in), scratch workspace, and
// the referenced env vars explicitly absent. The one turn must fail with
// the typed MISSING_CREDENTIAL — pre-network, naming the route/reference,
// never falling through to ambient discovery. Exit 0 only when it does.

import { spawnSync } from 'node:child_process'
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const E2E_DIR = resolve(import.meta.dirname)
const PRODUCT_ROOT = resolve(E2E_DIR, '..')
const PROFILE_SRC = join(PRODUCT_ROOT, 'profiles', 'awt-headless')
const GUARDS_DIST = join(PRODUCT_ROOT, 'guards', 'dist')
const DSH_BIN = join(E2E_DIR, 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js')

if (!existsSync(DSH_BIN)) {
  console.error(`AWT_PROBE_DSH_MISSING: ${DSH_BIN} — run npm ci in e2e/ first`)
  process.exit(1)
}
if (!existsSync(join(GUARDS_DIST, 'dsh-plugin.js'))) {
  console.error('AWT_PROBE_GUARDS_UNBUILT: run npm run build in guards/ first')
  process.exit(1)
}

const scratch = mkdtempSync(join(tmpdir(), 'awt-cred-probe-'))
const home = join(scratch, 'dsh-home')
const fakeUserHome = join(scratch, 'user-home')
const ws = join(scratch, 'workspace')

try {
  // Canonical profile into a scratch DSH_HOME.
  const profile = join(home, 'profiles', 'awt-headless')
  mkdirSync(profile, { recursive: true })
  cpSync(join(PROFILE_SRC, 'package.json'), join(profile, 'package.json'))
  for (const shared of ['cordis.patch.yml', 'awt-read-pdf.plugin.mjs', 'awt-brand.plugin.mjs', 'awt-export.plugin.mjs']) {
    cpSync(join(PROFILE_SRC, shared), join(profile, shared))
  }
  cpSync(GUARDS_DIST, join(profile, 'awt-guards'), { recursive: true })

  // Minimal valid workspace (the guards refuse inert mounts).
  mkdirSync(join(ws, 'chapters'), { recursive: true })
  mkdirSync(join(ws, 'literature', 'reading_notes'), { recursive: true })
  mkdirSync(join(ws, 'contracts'), { recursive: true })

  // Empty fake user home: no ~/.env, no credential store.
  mkdirSync(fakeUserHome, { recursive: true })

  const env = {
    PATH: process.env.PATH,
    LANG: process.env.LANG ?? 'en_US.UTF-8',
    HOME: fakeUserHome,
    DSH_HOME: home,
    DSH_TELEMETRY_DISABLED: '1',
    // DEEPSEEK_API_KEY / ANTHROPIC_API_KEY deliberately absent: the routes'
    // apiKeyEnv references must resolve to nothing.
  }

  const res = spawnSync(
    process.execPath,
    [DSH_BIN, '--profile', 'awt-headless', 'Reply with a single word.'],
    { cwd: ws, env, encoding: 'utf8', timeout: 120_000 },
  )

  const output = `${res.stdout ?? ''}\n${res.stderr ?? ''}`
  const failures = []

  if (res.status === 0) failures.push('run exited 0 — a credential-less turn must not succeed')
  if (!output.includes('MISSING_CREDENTIAL')) {
    failures.push(`typed MISSING_CREDENTIAL not found; output tail: ${output.trim().split('\n').slice(-6).join(' | ')}`)
  }
  if (!/DEEPSEEK_API_KEY|deepseek/.test(output)) {
    failures.push('the failure does not name the route or its credential reference')
  }

  if (failures.length > 0) {
    console.error('CREDENTIAL PROBE FAILED:')
    for (const f of failures) console.error(`  - ${f}`)
    process.exit(1)
  }
  console.log('CREDENTIAL PROBE GREEN: configured apiKeyEnv reference with no value fails typed (MISSING_CREDENTIAL), keyless and pre-network; no ambient fallthrough')
} finally {
  rmSync(scratch, { recursive: true, force: true })
}
