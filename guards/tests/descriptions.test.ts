// Catalogue truth test: the 9 shipped skill descriptions must have disjoint
// routing signatures. Each skill owns one exclusive keyword that may appear
// in no other description; "rebuttal" (the old cross-fire magnet) may appear
// in none; every description stays within a 40-word budget.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const SKILLS = join(ROOT, '.claude', 'skills')

const EXCLUSIVE: Record<string, string> = {
  read: 'page by page',
  note: 'record',
  map: 'coverage',
  integrate: 'weave',
  review: 'review',
  'edit-contract': 'contract',
  audit: 'consistency',
  'verify-refs': 'bibtex',
  export: 'docx',
}

function descriptions(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const dir of readdirSync(SKILLS)) {
    const text = readFileSync(join(SKILLS, dir, 'SKILL.md'), 'utf8')
    const match = text.match(/^description:\s*(.+)$/m)
    assert.ok(match, `no description frontmatter in ${dir}`)
    out[dir] = match[1].trim().replace(/^["']|["']$/g, '').toLowerCase()
  }
  return out
}

test('catalogue contains exactly the 9 approved skills', () => {
  assert.deepEqual(readdirSync(SKILLS).sort(), Object.keys(EXCLUSIVE).sort())
})

function hasKeyword(text: string, keyword: string): boolean {
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`\\b${escaped}\\b`).test(text)
}

test('each exclusive routing keyword appears only in its owner description', () => {
  const desc = descriptions()
  for (const [owner, keyword] of Object.entries(EXCLUSIVE)) {
    assert.ok(hasKeyword(desc[owner], keyword), `${owner} description must contain its keyword "${keyword}"`)
    for (const [other, text] of Object.entries(desc)) {
      if (other === owner) continue
      assert.ok(!hasKeyword(text, keyword), `keyword "${keyword}" owned by ${owner} also appears in ${other}`)
    }
  }
})

test('"rebuttal" appears in no description', () => {
  for (const [name, text] of Object.entries(descriptions())) {
    assert.ok(!text.includes('rebuttal'), `"rebuttal" found in ${name}`)
  }
})

test('every description is at most 40 words', () => {
  for (const [name, text] of Object.entries(descriptions())) {
    const words = text.split(/\s+/).filter(Boolean).length
    assert.ok(words <= 40, `${name} description is ${words} words (budget 40)`)
  }
})
