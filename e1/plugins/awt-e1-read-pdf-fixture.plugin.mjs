// Fixture-backed read_pdf for the E1 OFFLINE lane: same tool surface as the
// canonical pdftotext plugin (file_path, first_page, last_page), but the
// text comes from $AWT_E1_REFERENCE — so the scripted model provably "read"
// exactly the reference text the graders later match quotes against, with
// no PDF on disk. Offline-lane only; the real lane uses the canonical
// pdftotext plugin.
import { readFileSync } from 'node:fs'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'awt-e1-read-pdf-fixture'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'read_pdf',
    description: 'Read a page range of a PDF as plain text (E1 offline fixture).',
    parameters: {
      file_path: { type: 'string', required: true, description: 'PDF path (ignored by the fixture).' },
      first_page: { type: 'integer', required: true, description: '1-based first page.' },
      last_page: { type: 'integer', required: true, description: '1-based last page (inclusive).' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute() {
      const path = process.env.AWT_E1_REFERENCE
      if (path === undefined || path === '') throw new Error('AWT_E1_REFERENCE is not set')
      return readFileSync(path, 'utf8')
    },
  }))
}
