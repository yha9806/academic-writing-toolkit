import { readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createHash } from 'node:crypto'
import { E1InputError, measuredRun } from './inputs.mjs'
import { sessionFiles, terminalOutcome } from './evidence.mjs'

const fail = (message) => { throw new E1InputError('E1_RESUME_INVALID', message) }
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex')

export function readResume(directory, entries, route, harness, implementationRoot, retryLocalTransport = false) {
  const root = resolve(directory), bytes = readFileSync(join(root, 'metrics.json'))
  const prior = JSON.parse(bytes.toString('utf8'))
  const inputs = entries.map(({ path, ...entry }) => entry)
  if (prior.lane !== 'real' || prior.status !== 'incomplete' || prior.harness !== harness || JSON.stringify(prior.inputs) !== JSON.stringify(inputs)) fail('the saved run does not match this experiment and its exact inputs')
  if (prior.model?.provider !== route.provider || prior.model?.id !== route.model || JSON.stringify(prior.model?.local) !== JSON.stringify(route.localInfo)) fail('the saved model or server parameters differ')
  for (const file of ['e1/graders.mjs', 'profiles/awt-headless/awt-read-pdf.plugin.mjs', 'profiles/awt-headless/pdf-pages.mjs', 'guards/dist/notes-lint.js', 'guards/dist/decisions.js']) {
    if (prior.implementationSha256?.[file] !== digest(readFileSync(join(implementationRoot, file)))) fail(`the saved grader or source reader differs: ${file}`)
  }
  const order = entries.flatMap((entry) => ['skills', 'plain'].map((arm) => `${entry.id}/${arm}`))
  if (!Array.isArray(prior.results) || !prior.results.length || prior.results.length > order.length) fail('the saved run must be a nonempty ordered prefix')
  const arms = [], reusedTasks = [], reusedLogs = [], retriedTransportTasks = []
  for (const [index, prefix] of prior.results.entries()) {
    const key = `${prefix.id}/${prefix.arm}`
    if (key !== order[index] || prefix.artifacts !== key || ![1, 2].includes(prefix.processes?.length)) fail('the saved results are not the ordered prefix of this experiment')
    const artifactDir = join(root, key)
    const logs = sessionFiles(artifactDir).map((file) => {
      const bytes = readFileSync(file), text = bytes.toString('utf8')
      const events = text.split('\n').filter((line) => line.trim()).map((line) => JSON.parse(line))
      const end = events.find((event) => event.type === 'turn/end')
      return { file, sha256: digest(bytes), outcome: terminalOutcome([text]), endedAt: end?.time ?? 0,
        errorCode: end?.data?.reason?.error?.code,
        readOnly: events.filter((event) => event.type === 'tool/call').every((event) => ['read_pdf', 'read', 'glob', 'grep', 'skill'].includes(event.data?.name)) }
    }).sort((a, b) => a.endedAt - b.endedAt)
    if (logs.length !== prefix.processes.length) fail('each prefix task needs one durable session log')
    const processes = [], savedLogs = []
    for (const [taskIndex, process] of prefix.processes.entries()) {
      const log = logs[taskIndex], observed = { ...process, outcome: log.outcome }
      const task = `${key}/${['notes', 'draft'][taskIndex]}`
      if (measuredRun(observed) && (process.status !== 0 || log.outcome === 'completed')) {
        processes.push(observed); savedLogs.push(log)
        reusedTasks.push(task); reusedLogs.push({ task, sha256: log.sha256 })
      } else if (retryLocalTransport && route.provider === 'ollama' && index === prior.results.length - 1 && taskIndex === prefix.processes.length - 1 && process.status === 1 && !process.signal && !process.error && log.errorCode === 'TRANSPORT' && log.readOnly) {
        retriedTransportTasks.push({ task, failedLogSha256: log.sha256, reason: 'explicit local transport retry after health check; no prior tool write' })
      } else {
        fail('the durable prefix log must record a measured terminal outcome; an explicit local transport retry also requires a read-only failed task')
      }
    }
    if (index < prior.results.length - 1 && processes.length !== 2) fail('only the last arm may be partial')
    arms.push({ id: prefix.id, arm: prefix.arm, artifactDir, result: prefix, processes, savedLogs })
  }
  return { arms, process: arms[0].processes[0], provenance: {
    run: root, metricsSha256: digest(bytes), producerSha256: prior.producerSha256,
    reusedTasks, reusedLogSha256: reusedLogs[0]?.sha256, reusedLogs, retriedTransportTasks,
    ...(prior.continuation ? { earlierContinuation: prior.continuation } : {}),
  } }
}
