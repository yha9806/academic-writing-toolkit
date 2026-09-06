#!/usr/bin/env node
// Inspect an already installed published package. This command does not
// download, upgrade, patch a dependency, or write to an author's session.
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createHash } from 'node:crypto'

const args = process.argv.slice(2)
const value = (flag) => {
  const index = args.indexOf(flag)
  if (index < 0) return undefined
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw new Error(`${flag} needs a value`)
  return args[index + 1]
}
const packageRoot = resolve(value('--package') ?? join(import.meta.dirname, '..', 'guards', 'node_modules', '@deepseek-ai', 'dsh-session'))
const metadata = JSON.parse(readFileSync(join(packageRoot, 'package.json'), 'utf8'))
if (metadata.name !== '@deepseek-ai/dsh-session') throw new Error('expected an installed @deepseek-ai/dsh-session package')
const source = join(packageRoot, 'lib', 'index.js')
const { Session, SessionId } = await import(pathToFileURL(source).href)
const session = Session.create(SessionId('awt-detached-append-probe'))
const event = session.append('awt-guards/fact', { kind: 'page-read', callId: 'probe', pages: 1 }, { ignorable: true })
if (event?.type !== 'awt-guards/fact') throw new Error('append no longer returns the documented event envelope; this probe needs review')
const markerPreserved = event?.type === 'awt-guards/fact' && event?.ignorable === true
const report = {
  checkedAt: new Date().toISOString(),
  package: `${metadata.name}@${metadata.version}`,
  entrySha256: createHash('sha256').update(readFileSync(source)).digest('hex'),
  markerPreserved,
  status: markerPreserved ? 'candidate_requires_refold_validation' : 'blocked',
  writerMayBeEnabled: false,
  nextAction: markerPreserved ? 'Pin the published harness, implement the writer, then pass flush/dispose/remount/refold and live guards gates.' : 'Keep the structured-fact writer disabled. This published append API still drops the envelope marker.',
}
const json = JSON.stringify(report, null, 2)
if (value('--out')) writeFileSync(resolve(value('--out')), json + '\n')
console.log(json)
