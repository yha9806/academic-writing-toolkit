import { readFileSync, statSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'

export class E1InputError extends Error {
  constructor(code, message) { super(message); this.code = code }
}
const refuse = (code, message) => { throw new E1InputError(code, message) }

export function parseOptions(args) {
  const options = { real: false, check: false, help: false, provider: 'deepseek', timeoutMs: 600_000 }
  const flags = { '--real': 'real', '--check': 'check', '--help': 'help' }
  const values = { '--manifest': 'manifest', '--out': 'out', '--provider': 'provider', '--model': 'model', '--base-url': 'baseURL', '--timeout-ms': 'timeoutMs' }
  const seen = new Set()
  for (let index = 0; index < args.length; index++) {
    const flag = args[index]
    if (seen.has(flag)) refuse('E1_USAGE', `duplicate option ${flag}`)
    seen.add(flag)
    if (Object.hasOwn(flags, flag)) { options[flags[flag]] = true; continue }
    if (!Object.hasOwn(values, flag)) refuse('E1_USAGE', `unknown option ${flag}`)
    const value = args[++index]
    if (!value || value.startsWith('--')) refuse('E1_USAGE', `${flag} needs a value`)
    options[values[flag]] = value
  }
  options.timeoutMs = Number(options.timeoutMs)
  if (!Number.isSafeInteger(options.timeoutMs) || options.timeoutMs < 1000 || options.timeoutMs > 600_000) {
    refuse('E1_USAGE', '--timeout-ms must be an integer between 1000 and 600000')
  }
  if (options.check && !options.real) refuse('E1_USAGE', '--check requires --real')
  return options
}

export function modelRoute(provider, model, environment, baseURL) {
  if (!['deepseek', 'anthropic', 'ollama'].includes(provider)) refuse('E1_PROVIDER_INVALID', 'provider must be deepseek, anthropic or ollama')
  if (provider !== 'deepseek' && !model) refuse('E1_MODEL_REQUIRED', `specify --model explicitly for ${provider}; no automatic model selection`)
  model ??= 'deepseek-v4-flash'
  if (!/^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$/.test(model)) refuse('E1_MODEL_INVALID', 'invalid model identifier')
  if (provider === 'ollama') {
    let endpoint
    try { endpoint = new URL(baseURL ?? 'http://127.0.0.1:11434/v1') }
    catch { refuse('E1_ENDPOINT_INVALID', 'Ollama requires a loopback HTTP /v1 endpoint') }
    if (endpoint.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname) || endpoint.username || endpoint.password || endpoint.search || endpoint.hash || !['/v1', '/v1/'].includes(endpoint.pathname)) {
      refuse('E1_ENDPOINT_INVALID', 'Ollama is restricted to loopback HTTP /v1, without credentials or query parameters')
    }
    return { provider, model, baseURL: endpoint.href.replace(/\/$/, ''), keyEnv: 'AWT_E1_LOCAL_KEY', keyPresent: true }
  }
  if (baseURL) refuse('E1_ENDPOINT_INVALID', '--base-url is available only for the explicit local Ollama route')
  const keyEnv = provider === 'deepseek' ? 'DEEPSEEK_API_KEY' : 'ANTHROPIC_API_KEY'
  return { provider, model, keyEnv, keyPresent: Boolean(environment[keyEnv]) }
}

export function readManifest(manifestPath) {
  let manifest
  try { manifest = JSON.parse(readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, '')) }
  catch { refuse('E1_MANIFEST_INVALID', 'manifest is missing or is not UTF-8 JSON') }
  if (!Array.isArray(manifest?.pdfs) || manifest.pdfs.length !== 3) {
    refuse('E1_SOURCE_COUNT', 'the paired experiment requires exactly three distinct real PDFs')
  }
  const ids = new Set(), hashes = new Set()
  return manifest.pdfs.map((entry) => {
    if (!entry || typeof entry !== 'object' || typeof entry.id !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,79}$/.test(entry.id)) {
      refuse('E1_SOURCE_INVALID', 'each source needs a safe lowercase id')
    }
    if (ids.has(entry.id)) refuse('E1_SOURCE_DUPLICATE', `duplicate source id ${entry.id}`)
    ids.add(entry.id)
    if (typeof entry.path !== 'string' || !entry.path.trim()) refuse('E1_PDF_MISSING', `${entry.id}: missing PDF path`)
    if (!/^[a-fA-F0-9]{64}$/.test(entry.sha256 ?? '')) refuse('E1_HASH_INVALID', `${entry.id}: sha256 must contain 64 hex digits`)
    if (!Number.isSafeInteger(entry.firstPage) || !Number.isSafeInteger(entry.lastPage) || entry.firstPage < 1 || entry.lastPage < entry.firstPage || entry.lastPage - entry.firstPage + 1 > 15) {
      refuse('E1_PAGE_RANGE', `${entry.id}: use a positive inclusive page window of at most 15 pages`)
    }
    if (typeof entry.source?.surname !== 'string' || !/^[A-Za-z][A-Za-z'’-]*$/.test(entry.source.surname) || typeof entry.source?.year !== 'string' || !/^\d{4}$/.test(entry.source.year)) {
      refuse('E1_SOURCE_INVALID', `${entry.id}: provide a first-author surname and a four-digit year string`)
    }
    const path = resolve(dirname(manifestPath), entry.path)
    let bytes
    try { if (!statSync(path).isFile()) throw new Error(); bytes = readFileSync(path) }
    catch { refuse('E1_PDF_MISSING', `${entry.id}: PDF is not a readable file`) }
    if (!bytes.subarray(0, 1024).includes(Buffer.from('%PDF-'))) refuse('E1_PDF_INVALID', `${entry.id}: missing PDF header`)
    const sha256 = createHash('sha256').update(bytes).digest('hex')
    if (sha256 !== entry.sha256.toLowerCase()) refuse('E1_PDF_HASH_MISMATCH', `${entry.id}: file bytes do not match the declared sha256`)
    if (hashes.has(sha256)) refuse('E1_SOURCE_DUPLICATE', `${entry.id}: the same PDF appears more than once`)
    hashes.add(sha256)
    return { id: entry.id, path, sha256, firstPage: entry.firstPage, lastPage: entry.lastPage, source: { surname: entry.source.surname.toLowerCase(), year: entry.source.year } }
  })
}

// A failed process is an infrastructure outcome. A successful session that
// produces poor or missing notes is still an observed model outcome.
export function classifyRun(lane, runs, sourceOpened, logsPresent = true) {
  const operational = logsPresent && runs.length === 2 && runs.every((run) => run.status === 0 && !run.error && !run.signal)
  return {
    status: operational ? 'completed' : 'incomplete',
    sourceOpened,
    evidenceClass: operational ? (lane === 'real' ? 'E1' : 'E0') : null,
    efficacyEligible: lane === 'real' && operational,
  }
}
