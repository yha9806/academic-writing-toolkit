// Rebuild a public copy of frozen evidence; never edit an original run.
// node e1/sanitise-published.mjs <original-packet> <raw-run> <new-output>
import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { isDeepStrictEqual } from 'node:util'
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { absoluteRunPath, publicContinuation, relativeRunPath } from './public-paths.mjs'

const hash = (file) => createHash('sha256').update(readFileSync(file)).digest('hex')
const read = (file) => JSON.parse(readFileSync(file, 'utf8'))
const write = (file, value, newline = '\n') => writeFileSync(file, (JSON.stringify(value, null, 2) + '\n').replaceAll('\n', newline))
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function withoutPaths(value) {
  if (Array.isArray(value)) return value.map(withoutPaths)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'run' && key !== 'log')
    .map(([key, child]) => [key, withoutPaths(child)]))
}

function assertPublic(value) {
  if (typeof value === 'string') {
    assert(!/(^|[^\w])[A-Za-z]:[\\/]|(^|[\s"'(])\/(Users|home|tmp|private|var\/folders)\/|--(?:[A-Za-z]-Users-|Users-|home-|private-|tmp-|var-folders-)/.test(value),
      'A machine-specific path remains in the public packet')
  } else if (value && typeof value === 'object') {
    for (const child of Object.values(value)) assertPublic(child)
  }
}

export function sanitisePublished(packet, run, output) {
  packet = resolve(packet); run = resolve(run); output = resolve(output)
  assert(!existsSync(output), 'Output must be new; preserve every original packet and run')
  const receiptPath = join(packet, 'verification.json')
  const receipt = read(receiptPath)
  const originalHashes = { ...receipt.publishedFilesSha256 }
  for (const [file, expected] of Object.entries(originalHashes)) {
    assert(!file.includes('/') && !file.includes('\\') && !file.startsWith('.'), 'Receipt filenames must be local basenames')
    assert(hash(join(packet, file)) === expected, `Frozen packet hash mismatch: ${file}`)
  }
  for (const file of ['metrics.json', 'results.md']) {
    assert(hash(join(run, file)) === originalHashes[file], `Raw run differs from the frozen packet: ${file}`)
  }
  const original = read(join(packet, 'metrics.json'))
  const metrics = { ...original }
  const logicalRoot = receipt.runDirectory
  if (metrics.continuation) metrics.continuation = publicContinuation(metrics.continuation, logicalRoot)
  assert(isDeepStrictEqual(withoutPaths(metrics), withoutPaths(original)), 'Measurements or original hash-chain references changed')

  let prior = original.continuation, priorCount = 0
  while (prior) {
    const priorRoot = absoluteRunPath(prior.run, logicalRoot)
    const physicalRoot = resolve(run, relativeRunPath(priorRoot, logicalRoot))
    assert(hash(join(physicalRoot, 'metrics.json')) === prior.metricsSha256, 'An original continuation metric hash no longer matches')
    priorCount += 1; prior = prior.earlierContinuation
  }
  mkdirSync(output, { recursive: true })
  for (const file of ['results.md', 'Modelfile', 'pdfs.json']) cpSync(join(packet, file), join(output, file))
  write(join(output, 'metrics.json'), metrics)
  const summary = spawnSync(process.env.PYTHON ?? 'python', [join(import.meta.dirname, 'summarize-run.py'), run,
    '--metrics', join(output, 'metrics.json'), '--output', output], { encoding: 'utf8', timeout: 120_000 })
  assert(summary.status === 0, 'Summary regeneration failed; original files are intact')
  const oldAnalysis = read(join(packet, 'analysis.json'))
  const analysis = read(join(output, 'analysis.json'))
  assert(analysis.metricsSha256 === hash(join(output, 'metrics.json')), 'Summary does not bind the sanitised metrics')
  assert(isDeepStrictEqual(withoutPaths({ ...analysis, metricsSha256: oldAnalysis.metricsSha256 }), withoutPaths(oldAnalysis)),
    'Regenerated observations, usage, outcomes or session hashes differ from the frozen evidence')
  // Avoid a whole-file diff solely because the original publisher used
  // Windows line endings. The summariser itself emits portable LF output.
  if (readFileSync(join(packet, 'analysis.json'), 'utf8').includes('\r\n')) {
    const portable = readFileSync(join(output, 'analysis.json'), 'utf8').replaceAll('\r\n', '\n')
    writeFileSync(join(output, 'analysis.json'), portable.replaceAll('\n', '\r\n'))
  }
  const expectedProse = readFileSync(join(packet, 'analysis.md'), 'utf8')
    .replace(oldAnalysis.metricsSha256, analysis.metricsSha256)
  assert(readFileSync(join(output, 'analysis.md'), 'utf8').replaceAll('\r\n', '\n') === expectedProse.replaceAll('\r\n', '\n'),
    'Summary prose changed beyond its metrics hash')
  // Preserve the frozen prose's original line endings on every platform.
  writeFileSync(join(output, 'analysis.md'), expectedProse)
  const verification = { ...receipt, runDirectory: '.',
    priorRunsVerified: receipt.priorRunsVerified.map((value) => relativeRunPath(value, logicalRoot)),
    publishedFilesSha256: Object.fromEntries(Object.keys(originalHashes).map((file) => [file, hash(join(output, file))])),
    publicSanitisation: {
      method: 'run-relative paths and content-addressed session references; original bytes retained privately',
      originalVerificationSha256: hash(receiptPath), originalPublishedFilesSha256: originalHashes,
      pathFieldsRewritten: 1 + receipt.priorRunsVerified.length + priorCount + analysis.sessions.length,
      unchangedSessionLogHashes: analysis.uniqueSessionLogs, originalContinuationHashesVerified: priorCount,
      measurementsUsageOutcomesAndOriginalHashChainUnchanged: true,
      rawSessionLogsPublished: false, localMachinePathsIncluded: false,
      producer: 'e1/sanitise-published.mjs', producerSha256: hash(fileURLToPath(import.meta.url)),
    },
  }
  for (const value of [metrics, analysis, verification]) assertPublic(value)
  write(join(output, 'verification.json'), verification, readFileSync(receiptPath, 'utf8').includes('\r\n') ? '\r\n' : '\n')
  // A second receipt check also covers unchanged files copied into the output.
  for (const [file, expected] of Object.entries(verification.publishedFilesSha256)) {
    assert(hash(join(output, file)) === expected, `Published hash mismatch: ${file}`)
  }
  return verification.publicSanitisation
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  assert(args.length === 3, 'Usage: node e1/sanitise-published.mjs <original-packet> <raw-run> <new-output>')
  console.log(JSON.stringify(sanitisePublished(...args), null, 2))
}
