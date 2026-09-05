import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { E1InputError } from './inputs.mjs'
import { sessionFiles, terminalOutcome } from './evidence.mjs'

const fail = (message) => { throw new E1InputError('E1_RESUME_INVALID', message) }
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex')

// Deliberately narrow: preserve the first notes task that the old producer
// stopped after a recorded output-budget exhaustion. Never retry that sample.
export function readResume(directory, entries, route, harness, implementationRoot) {
  const root = resolve(directory), bytes = readFileSync(join(root, 'metrics.json'))
  const prior = JSON.parse(bytes.toString('utf8'))
  const inputs = entries.map(({ path, ...entry }) => entry)
  if (prior.lane !== 'real' || prior.status !== 'incomplete' || prior.harness !== harness || JSON.stringify(prior.inputs) !== JSON.stringify(inputs)) fail('the saved run does not match this experiment and its exact inputs')
  if (prior.model?.provider !== route.provider || prior.model?.id !== route.model || JSON.stringify(prior.model?.local) !== JSON.stringify(route.localInfo)) fail('the saved model or server parameters differ')
  for (const file of ['e1/graders.mjs', 'profiles/awt-headless/awt-read-pdf.plugin.mjs', 'profiles/awt-headless/pdf-pages.mjs', 'guards/dist/notes-lint.js', 'guards/dist/decisions.js']) {
    if (prior.implementationSha256?.[file] !== digest(readFileSync(join(implementationRoot, file)))) fail(`the saved grader or source reader differs: ${file}`)
  }
  const prefix = prior.results?.[0]
  if (prior.results?.length !== 1 || prefix.id !== entries[0].id || prefix.arm !== 'skills' || prefix.artifacts !== `${entries[0].id}/skills` || prefix.processes?.length !== 1) fail('only the interrupted first skills notes task can be continued')
  const process = prefix.processes[0]
  if (process.status !== 1 || process.signal || process.error) fail('the prefix is not a cleanly terminated headless task')
  const artifactDir = join(root, prefix.artifacts)
  const files = sessionFiles(artifactDir)
  const outcome = terminalOutcome(files.map((file) => readFileSync(file, 'utf8')))
  if (outcome !== 'max-tokens') fail('the durable prefix log must record max-tokens, not an infrastructure failure')
  return { artifactDir, id: prefix.id, process: { ...process, outcome }, provenance: {
    run: root, metricsSha256: digest(bytes), producerSha256: prior.producerSha256,
    reusedTask: `${prefix.id}/skills/notes`, reusedLogSha256: digest(readFileSync(files[0])),
  } }
}
