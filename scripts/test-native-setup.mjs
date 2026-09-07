// Real first-run regression: a native Python without a backend, flattened Git
// links, Chinese/space paths, and the same setup/doctor entry users invoke.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { delimiter, join, resolve } from 'node:path'

const SOURCE = resolve(import.meta.dirname, '..')
const WINDOWS = process.platform === 'win32'
const pythonIn = (dir) => join(dir, WINDOWS ? 'Scripts' : 'bin', WINDOWS ? 'python.exe' : 'python')
const run = (command, args, cwd, env = process.env) => spawnSync(command, args, {
  cwd, env, encoding: 'utf8', timeout: 300_000,
})
const passed = (result) => assert.equal(result.status, 0, `${result.error ?? ''}\n${result.stdout}\n${result.stderr}`)

test('native clean setup, doctor and repair preserve source and reject wrong links', { timeout: 600_000 }, () => {
  const temporary = realpathSync(mkdtempSync(join(tmpdir(), 'awt-native-setup-')))
  const root = join(temporary, 'toolkit space 中文')
  try {
    mkdirSync(join(root, '.claude'), { recursive: true })
    for (const name of ['scripts', 'templates', '.claude/skills', 'CLAUDE.md', 'AGENTS.md', 'GEMINI.md', '.gitignore']) {
      cpSync(join(SOURCE, name), join(root, name), { recursive: true, filter: (p) => !p.includes('__pycache__') })
    }
    const skills = readdirSync(join(root, '.claude', 'skills'))
    assert.equal(skills.length, 9)
    mkdirSync(join(root, '.agents', 'skills'), { recursive: true })
    for (const name of skills) writeFileSync(join(root, '.agents', 'skills', name), `../../.claude/skills/${name}`)
    passed(run('git', ['init', '--quiet'], root))
    passed(run('git', ['add', '.'], root))

    // A real unprepared interpreter is first on PATH; no mocked pip or venv.
    const seed = join(temporary, 'bootstrap')
    passed(run(process.env.AWT_TEST_PYTHON || (WINDOWS ? 'python' : 'python3'), ['-m', 'venv', '--without-pip', seed], root))
    const env = { ...process.env, PATH: `${join(seed, WINDOWS ? 'Scripts' : 'bin')}${delimiter}${process.env.PATH}`, PYTHONUTF8: '1' }
    delete env.AWT_PYTHON
    delete env.PYTHONPATH
    const cli = (...args) => run(process.execPath, [join(root, 'scripts', 'setup.mjs'), ...args], root, env)
    assert.equal(existsSync(join(root, '.venv')), false)
    passed(cli())
    const python = pythonIn(join(root, '.venv'))
    assert.ok(existsSync(python), 'setup must create a real native project venv')
    passed(run(python, [join(root, '.claude', 'skills', 'export', 'scripts', 'convert_to_docx.py'), '--check'], root))
    passed(cli('doctor'))
    const before = statSync(python).mtimeMs
    passed(cli())
    assert.equal(statSync(python).mtimeMs, before, 'repeat setup should reuse the prepared environment')
    const aliases = skills.map((name) => join(root, '.agents', 'skills', WINDOWS ? `awt-local-${name}` : name))
    for (let i = 0; i < skills.length; i++) {
      assert.ok(lstatSync(aliases[i]).isSymbolicLink())
      assert.equal(realpathSync(aliases[i]), realpathSync(join(root, '.claude', 'skills', skills[i])))
      if (WINDOWS) assert.equal(readFileSync(join(root, '.agents', 'skills', skills[i]), 'utf8'), `../../.claude/skills/${skills[i]}`)
    }
    if (WINDOWS) {
      passed(run('git', ['diff', '--exit-code'], root))
      assert.equal(run('git', ['ls-files', '--others', '--exclude-standard'], root).stdout.trim(), '')
    }

    // An actual misdirected junction/symlink must be repaired without touching
    // the directory it pointed at, even when it contains a plausible SKILL.md.
    const unrelated = join(temporary, 'unrelated')
    mkdirSync(unrelated)
    writeFileSync(join(unrelated, 'SKILL.md'), 'Keep this unrelated user content.')
    unlinkSync(aliases[0])
    symlinkSync(unrelated, aliases[0], WINDOWS ? 'junction' : 'dir')
    assert.notEqual(cli('doctor').status, 0)
    passed(cli('repair'))
    assert.equal(readFileSync(join(unrelated, 'SKILL.md'), 'utf8'), 'Keep this unrelated user content.')
    assert.equal(realpathSync(aliases[0]), realpathSync(join(root, '.claude', 'skills', skills[0])))

    // A directory copy is not a live link; repair must preserve its contents.
    unlinkSync(aliases[0])
    mkdirSync(aliases[0])
    writeFileSync(join(aliases[0], 'SKILL.md'), 'Personal edits must survive repair.')
    assert.notEqual(cli('doctor').status, 0)
    passed(cli('repair'))
    const backups = readdirSync(join(root, '.awt-skill-backups'), { recursive: true })
    assert.ok(backups.some((p) => String(p).endsWith('SKILL.md') && readFileSync(join(root, '.awt-skill-backups', p), 'utf8') === 'Personal edits must survive repair.'))
    passed(cli('doctor'))

    const missing = run(process.execPath, [join(root, 'scripts', 'setup.mjs'), 'doctor'], root, { ...env, AWT_PYTHON: pythonIn(seed) })
    assert.notEqual(missing.status, 0, 'an explicit interpreter without a backend must fail doctor')
    assert.match(missing.stdout + missing.stderr, /export.*cannot convert/)
    writeFileSync(join(root, 'AGENTS.md'), 'Config drift')
    assert.notEqual(cli('doctor').status, 0)
    passed(cli('repair'))
  } finally {
    // This exact directory was created above; links are removed, never followed.
    assert.ok(temporary.startsWith(realpathSync(tmpdir())))
    rmSync(temporary, { recursive: true, force: true })
  }
})
