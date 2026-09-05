import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { E1InputError } from './inputs.mjs'
import { sessionFiles, terminalOutcome } from './evidence.mjs'

const fail = (message) => { throw new E1InputError('E1_RESUME_INVALID', message) }
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex')

// Deliberately narrow: preserve the first skills task/arm that the old
// producer stopped after recorded model failures. Never retry those samples.
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
  if (prior.results?.length !== 1 || prefix.id !== entries[0].id || prefix.arm !== 'skills' || prefix.artifacts !== `${entries[0].id}/skills` || ![1, 2].includes(prefix.processes?.length)) fail('only the interrupted first skills task/arm can be continued')
  const artifactDir = join(root, prefix.artifacts)
  const files = sessionFiles(artifactDir)
  const logs = files.map((file) => {
    const bytes = readFileSync(file), text = bytes.toString('utf8')
    const events = text.split('\n').filter((line) => line.trim()).map((line) => JSON.parse(line))
    return { sha256: digest(bytes), outcome: terminalOutcome([text]), endedAt: events.find((event) => event.type === 'turn/end')?.time ?? 0 }
  }).sort((a, b) => a.endedAt - b.endedAt)
  if (logs.length !== prefix.processes.length) fail('each prefix task needs one durable session log')
  const processes = prefix.processes.map((process, index) => {
    const outcome = logs[index].outcome
    if (process.signal || process.error || !([0, 1].includes(process.status)) ||
        (process.status === 0 ? outcome !== 'completed' : !['max-tokens', 'blocked', 'empty-response'].includes(outcome))) {
      fail('the durable prefix log must record a measured terminal outcome, not an infrastructure failure')
    }
    return { ...process, outcome }
  })
  return { artifactDir, id: prefix.id, processes, process: processes[0], provenance: {
    run: root, metricsSha256: digest(bytes), producerSha256: prior.producerSha256,
    reusedTasks: ['notes', 'draft'].slice(0, processes.length).map((task) => `${prefix.id}/skills/${task}`),
    reusedLogSha256: logs[0].sha256, reusedLogs: logs,
    ...(prior.continuation ? { earlierContinuation: prior.continuation } : {}),
  } }
}
