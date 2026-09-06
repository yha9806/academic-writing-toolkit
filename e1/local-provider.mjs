import { E1InputError } from './inputs.mjs'

const fail = (code, message) => { throw new E1InputError(code, message) }

// Installed-model metadata is a preflight input, never a model generation.
export function localModelMetadata(route, version, tags, shown) {
  const installed = tags.models?.find((item) => item.name === route.model || item.model === route.model)
  if (!installed || !/^[a-f0-9]{64}$/i.test(installed.digest ?? '')) fail('E1_LOCAL_MODEL_MISSING', 'select an already installed, digest-identified Ollama model')
  if (shown.remote_host || shown.remote_model) fail('E1_LOCAL_MODEL_REMOTE', 'the local experiment cannot use a cloud-backed Ollama model')
  if (!shown.capabilities?.includes('tools')) fail('E1_LOCAL_TOOLS_MISSING', 'the selected local model must advertise tool support')
  const parameter = (name) => Number((shown.parameters ?? '').match(new RegExp(`^${name}\\s+(\\d+)\\s*$`, 'm'))?.[1])
  const contextWindow = parameter('num_ctx'), maxTokens = parameter('num_predict')
  if (!Number.isSafeInteger(contextWindow) || contextWindow < 16384 || !Number.isSafeInteger(maxTokens) || maxTokens < 1024 || maxTokens >= contextWindow) {
    fail('E1_LOCAL_CONTEXT_UNSET', 'create a local alias with explicit num_ctx >= 16384 and num_predict >= 1024 below num_ctx; declaring a client capacity alone cannot resize the server context')
  }
  return { server: 'Ollama', serverVersion: version.version, modelDigest: installed.digest, contextWindow, maxTokens,
    parameters: shown.parameters, details: shown.details, baseURL: route.baseURL }
}

export async function inspectLocalModel(route) {
  const origin = new URL(route.baseURL).origin
  async function request(path, body) {
    let response
    try {
      response = await fetch(`${origin}${path}`, { method: body ? 'POST' : 'GET', redirect: 'error',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(10000) })
    } catch { fail('E1_LOCAL_UNAVAILABLE', 'the selected loopback Ollama endpoint did not answer its metadata request') }
    if (!response.ok) fail('E1_LOCAL_UNAVAILABLE', `Ollama metadata request failed with HTTP ${response.status}`)
    return response.json()
  }
  const [version, tags, shown] = await Promise.all([request('/api/version'), request('/api/tags'), request('/api/show', { model: route.model })])
  return localModelMetadata(route, version, tags, shown)
}

export function localProviderPatch(route) {
  if (!route.localInfo) fail('E1_LOCAL_UNCHECKED', 'inspect the selected local model before constructing its provider')
  return `- id: llm-pi-ai
  config:
    providers:
      ollama:
        apiKeyEnv: AWT_E1_LOCAL_KEY
        api: openai-completions
        baseURL: ${JSON.stringify(route.baseURL)}
        timeoutMs: 300000
        streamIdleTimeoutMs: 300000
        retryPolicy:
          mode: normal
          maxRetries: 0
        models:
          - id: ${JSON.stringify(route.model)}
            contextWindow: ${route.localInfo.contextWindow}
            maxTokens: ${route.localInfo.maxTokens}
            reasoningEfforts: false
`
}
