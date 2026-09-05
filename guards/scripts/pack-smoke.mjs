// Pack-and-install smoke (P3 spec item 2, eco #5): prove the install story,
// not just the build. Builds the guards, packs the real npm tarball, gates
// its payload offline (patch + built plugin present), installs it into a
// fresh scratch DSH_HOME profile, and asserts `--dump-config` composes the
// awt-guards row from the package's own bundle patch. Exit 0 only when the
// whole chain holds.
//
// Install path: the official flow is `dsh plugin --profile <name> add <tgz>`
// (pnpm-forwarding) and is used when pnpm is available; without pnpm the
// smoke installs the tarball into $DSH_HOME/profiles/node_modules with npm
// and declares the bundle in the profile manifest — the same loader
// resolution (`bare names resolve through $DSH_HOME/profiles/node_modules`),
// stated honestly in the output.

import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const GUARDS_DIR = resolve(import.meta.dirname, '..')
const PRODUCT_ROOT = resolve(GUARDS_DIR, '..')
const DSH_BIN = join(PRODUCT_ROOT, 'e2e', 'node_modules', '@deepseek-ai', 'dsh', 'lib', 'bin.js')

function run(name, command, args, options = {}) {
  const res = spawnSync(command, args, { encoding: 'utf8', timeout: 300_000, ...options })
  if (res.error || res.status !== 0) {
    const tail = `${res.stdout ?? ''}\n${res.stderr ?? ''}`.trim().split('\n').slice(-10).join('\n')
    console.error(`PACK SMOKE FAILED at ${name}: ${res.error?.message ?? `exit ${res.status}`}\n${tail}`)
    process.exit(1)
  }
  return res
}

if (!existsSync(DSH_BIN)) {
  console.error(`PACK SMOKE FAILED: pinned dsh launcher missing at ${DSH_BIN} — run npm ci in e2e/ first`)
  process.exit(1)
}

const scratch = mkdtempSync(join(tmpdir(), 'awt-pack-smoke-'))
try {
  // 1. Build, then pack the real tarball.
  run('build', 'npm', ['run', 'build'], { cwd: GUARDS_DIR })
  const packed = JSON.parse(run('pack', 'npm', ['pack', '--json', '--pack-destination', scratch], { cwd: GUARDS_DIR }).stdout)
  const tgz = join(scratch, packed[0].filename)
  const shipped = packed[0].files.map((f) => f.path)

  // 2. Offline payload gate: everything the manifest promises is in the tarball.
  for (const required of ['cordis.patch.yml', 'dist/dsh-plugin.js', 'package.json']) {
    if (!shipped.includes(required)) {
      console.error(`PACK SMOKE FAILED: tarball is missing ${required}; shipped: ${shipped.join(', ')}`)
      process.exit(1)
    }
  }

  // 3. Fresh DSH_HOME with a minimal profile that lists ONLY this bundle —
  // proving out-of-tree composition without booting a product tree.
  const home = join(scratch, 'dsh-home')
  const profile = join(home, 'profiles', 'smoke')
  mkdirSync(profile, { recursive: true })
  writeFileSync(join(profile, 'package.json'), JSON.stringify({
    name: 'dsh-profile-smoke',
    private: true,
    type: 'module',
    dsh: { profile: { bundles: ['@awt/guards'] } },
  }, null, 2))

  // 4. Install the tarball where the loader resolves bare bundle names.
  const havePnpm = spawnSync('pnpm', ['--version'], { encoding: 'utf8' }).status === 0
  let installPath
  if (havePnpm) {
    run('dsh-plugin-add', process.execPath, [DSH_BIN, 'plugin', '--profile', 'smoke', 'add', tgz],
      { env: { ...process.env, DSH_HOME: home } })
    installPath = 'official `dsh plugin add` (pnpm)'
  } else {
    const profilesRoot = join(home, 'profiles')
    writeFileSync(join(profilesRoot, 'package.json'), JSON.stringify({ name: 'dsh-profiles-root', private: true }, null, 2))
    // --legacy-peer-deps: install ONLY this bundle. dsh owns
    // $DSH_HOME/profiles/node_modules and symlinks the harness packages into
    // it itself; npm auto-installing our peers would collide with that
    // managed fallback (observed: "cordis exists and is not a symlink").
    run('npm-install', 'npm', ['install', '--prefix', profilesRoot, '--no-audit', '--no-fund', '--legacy-peer-deps', tgz])
    installPath = 'npm install into $DSH_HOME/profiles/node_modules (pnpm unavailable; same loader resolution)'
  }

  // 5. Composition proof: no boot, no credentials — the row must be there.
  const dump = run('dump-config', process.execPath, [DSH_BIN, '--profile', 'smoke', '--dump-config'],
    { env: { ...process.env, DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1' }, cwd: scratch })
  if (!dump.stdout.includes('awt-guards')) {
    console.error(`PACK SMOKE FAILED: --dump-config does not carry the awt-guards row\n${dump.stdout.slice(0, 800)}`)
    process.exit(1)
  }
  if (/FAILED/i.test(dump.stdout)) {
    console.error('PACK SMOKE FAILED: --dump-config reports a FAILED row')
    process.exit(1)
  }

  console.log(`PACK SMOKE GREEN: ${packed[0].filename} -> ${installPath} -> dump-config carries the awt-guards row`)
} finally {
  rmSync(scratch, { recursive: true, force: true })
}
