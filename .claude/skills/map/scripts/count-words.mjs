#!/usr/bin/env node
// The same whitespace-delimited unit as the old wc instruction, without a
// platform-specific executable or shell glob. This is not a CJK character count.
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

try {
  const args = process.argv.slice(2)
  if (args.includes('--help')) {
    console.log('Usage: node count-words.mjs [--base-dir <workspace>] [--json]\nCounts whitespace-delimited words in chapters/*.md.')
  } else {
    const index = args.indexOf('--base-dir')
    if (index !== -1 && (!args[index + 1] || args[index + 1].startsWith('--'))) throw new Error('--base-dir needs a workspace path')
    // Anything not recognised stops the run. Handed an unknown positional this
    // silently resolved the base to '.', counted the toolkit's own template and
    // exited 0 — a confident word count for a directory nobody asked about.
    const known = new Set(['--base-dir', '--json', '--help'])
    const valueAt = index === -1 ? -1 : index + 1
    const stray = args.filter((arg, at) => !known.has(arg) && at !== valueAt)
    if (stray.length) throw new Error(`unrecognised argument(s): ${stray.join(' ')}`)
    const base = resolve(index === -1 ? '.' : args[index + 1])
    const chapters = readdirSync(join(base, 'chapters'), { withFileTypes: true })
      .filter((entry) => entry.isFile() && entry.name.endsWith('.md')).map((entry) => entry.name).sort()
      .map((name) => ({ file: `chapters/${name}`, words: (readFileSync(join(base, 'chapters', name), 'utf8').match(/\S+/gu) ?? []).length }))
    const report = { unit: 'whitespace-delimited words', chapters, total: chapters.reduce((sum, entry) => sum + entry.words, 0) }
    if (args.includes('--json')) console.log(JSON.stringify(report, null, 2))
    else console.log([...chapters.map(({ file, words }) => `${words}\t${file}`), `${report.total}\ttotal`].join('\n'))
  }
} catch (error) {
  console.error(`WORD_COUNT_FAILED: ${error.message}`)
  process.exitCode = 1
}
