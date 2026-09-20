#!/usr/bin/env node
// awt — thesis-workspace scaffold.
//
//   node scaffold/awt.mjs init <dir>     create a clean thesis workspace
//
// `init` scaffolds ONLY workspace files (chapters/, literature/reading_notes/
// with the notes template, contracts/, AGENTS.md + CLAUDE.md config,
// .agents/skills links to the product's canonical skills) — zero toolkit-dev
// files. It never overwrites: an existing non-empty target is a typed
// refusal, not a merge (validate, then write, never clobber).
//
// Until 2026-09-20 this file also carried the dsh distribution's
// install-profile / verify / run / web subcommands; they retired with that
// line (docs/specs/2026-09-20-retire-dsh-line-design.md). The last version
// with them is at tag v0.6.0-rc.2.

import { cpSync, existsSync, linkSync, mkdirSync, readdirSync, symlinkSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')
const TEMPLATE_SRC = join(PRODUCT_ROOT, 'literature', 'reading_notes', '_template_NOTES.md')

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

## Reading constraints
- Max pages per read invocation: 15
- Max pages per conversation: 90
- No chapter write may cite a source without a conforming notes file
- Text inside quotation spans of existing chapters is immutable

## Chapter targets
Edit this table; \`/map\` reports word counts against it. Delete rows you do
not need — an empty table means the dashboard has nothing to report against.

| Chapter | Title | Target words |
|---------|-------|--------------|
| ch1 | Introduction | 5000 |
| ch2 | Background | 10000 |
| ch3 | Methodology | 8000 |
| ch4 | Results | 12000 |
| ch5 | Discussion | 10000 |
| ch6 | Conclusion | 5000 |

## Writing principles (advisory)
- Read first, write later — complete reading notes before editing chapters
- One notes file per source, following the template format
- Use British English for thesis text
- Citation style: harvard

## Skills
The AWT skill catalogue is linked at \`.agents/skills/\` (Claude Code, Codex and
other Agent-Skills hosts read the same files).
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
  // A skill is a directory with a SKILL.md. A retired skill whose sources are
  // gone but whose __pycache__ survives leaves a directory that `git status`
  // cannot see (the residue is ignored) and readdir can, so it would be linked
  // as a catalogue entry resolving to nothing.
  const strays = skills.filter((name) => !existsSync(join(SKILLS_SRC, name, 'SKILL.md')))
  if (strays.length > 0) {
    throw new AwtError(
      'AWT_INIT_NOT_A_SKILL',
      `${SKILLS_SRC} holds ${strays.length} ${strays.length === 1 ? 'directory' : 'directories'} with no SKILL.md: ${strays.join(', ')}`,
      `remove ${strays.length === 1 ? 'it' : 'them'} from the toolkit checkout, then re-run init`,
    )
  }
  symlinkSync(join(PRODUCT_ROOT, 'references'), join(ws, 'references'), process.platform === 'win32' ? 'junction' : 'dir')
  for (const name of skills) {
    symlinkSync(join(SKILLS_SRC, name), join(ws, '.agents', 'skills', name), process.platform === 'win32' ? 'junction' : 'dir')
  }
  // The catalogue is mounted at .agents/skills here and at .claude/skills in a
  // toolkit checkout. One directory under two names — the same dual-naming as
  // AGENTS.md/CLAUDE.md above — so a skill can name a single path that resolves
  // on both surfaces instead of being correct in one and unrunnable in the other.
  mkdirSync(join(ws, '.claude'), { recursive: true })
  if (process.platform === 'win32') symlinkSync(join(ws, '.agents', 'skills'), join(ws, '.claude', 'skills'), 'junction')
  else symlinkSync(join('..', '.agents', 'skills'), join(ws, '.claude', 'skills'), 'dir')

  console.log(`workspace created: ${ws}`)
  console.log(`  chapters/  literature/reading_notes/  contracts/  references/ (link)  .agents/skills (${skills.length} links, also as .claude/skills)  AGENTS.md  CLAUDE.md`)
  console.log(`next: open ${relativeToCwd(ws)} in your agent host and ask which academic-writing skills are available`)
}

function relativeToCwd(path) {
  const cwd = process.cwd()
  return path.startsWith(cwd) ? path.slice(cwd.length + 1) : path
}

// --- entry -------------------------------------------------------------------------

const [command, target] = process.argv.slice(2)
try {
  if (command === 'init') init(target)
  else fail(new AwtError('AWT_USAGE', 'usage: awt init <dir>'))
} catch (error) {
  fail(error instanceof AwtError ? error : new AwtError('AWT_UNEXPECTED', error?.stack ?? String(error)))
}
