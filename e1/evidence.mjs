import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'

export function sessionFiles(home) {
  const files = []
  function walk(dir) {
    if (!existsSync(dir)) return
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) walk(path)
      else if (entry.isFile() && entry.name.endsWith('.jsonl')) files.push(path)
    }
  }
  walk(join(home, 'sessions'))
  return files.sort()
}

// Match successful tool results to the actual read call in each durable log.
// A manifest entry alone is not proof that the model opened a source.
export function openedReference(logs, workspace, entry) {
  const texts = []
  const normalize = (path) => process.platform === 'win32' ? path.toLowerCase() : path
  const expected = normalize(resolve(workspace, 'literature', 'source.pdf'))
  for (const log of logs) {
    const calls = new Set()
    for (const line of log.split('\n').filter((line) => line.trim())) {
      const event = JSON.parse(line)
      if (event.type === 'tool/call' && event.data?.name === 'read_pdf') {
        let args
        try { args = JSON.parse(event.data.arguments) } catch { continue }
        if (typeof args.file_path === 'string' && normalize(resolve(workspace, args.file_path)) === expected &&
            Number.isSafeInteger(args.first_page) && Number.isSafeInteger(args.last_page) &&
            args.first_page >= entry.firstPage && args.last_page <= entry.lastPage && args.last_page >= args.first_page) {
          calls.add(event.data.callId)
        }
      }
      if (event.type !== 'tool/result') continue
      for (const block of event.data?.message?.content ?? []) {
        if (block.type !== 'tool-result' || !calls.delete(block.toolCallId) || block.isError) continue
        texts.push((block.content ?? []).filter((part) => part.type === 'text').map((part) => part.text).join('\n'))
      }
    }
  }
  return { sourceOpened: texts.length > 0, referenceText: texts.join('\n\n') }
}

export function readOpeningEvidence(home, workspace, entry) {
  const files = sessionFiles(home)
  return { files, ...openedReference(files.map((file) => readFileSync(file, 'utf8')), workspace, entry) }
}

export function terminalOutcome(logs) {
  if (logs.length !== 1) return undefined
  try {
    const events = logs[0].split('\n').filter((line) => line.trim()).map((line) => JSON.parse(line))
    const ends = events.filter((event) => event.type === 'turn/end')
    if (ends.length !== 1) return undefined
    return ends[0].data?.reason?.kind
  } catch { return undefined }
}
