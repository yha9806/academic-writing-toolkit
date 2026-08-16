// The awt profile's real `read_pdf` tool (P3): pdftotext-backed, page-ranged
// (args: file_path, first_page, last_page — the exact surface the page
// guards decide on). The tool body only ever runs AFTER the monotonic
// guards allowed the call, so the 15-page invocation cap and the 90-page
// session budget are enforced upstream of this file; the body adds no
// policy of its own. A missing pdftotext or an unreadable PDF is a typed,
// content-free tool error.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { isAbsolute, join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'awt-read-pdf'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'read_pdf',
    description: 'Read a page range of a PDF as plain text (pdftotext -layout). Page numbers are 1-based and inclusive; the per-invocation and per-session page budgets are enforced by the AWT guards.',
    parameters: {
      file_path: { type: 'string', required: true, description: 'PDF path, absolute or relative to the workspace.' },
      first_page: { type: 'integer', required: true, description: '1-based first page.' },
      last_page: { type: 'integer', required: true, description: '1-based last page (inclusive).' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const path = isAbsolute(args.file_path) ? args.file_path : join(process.cwd(), args.file_path)
      if (!existsSync(path)) throw new Error(`READ_PDF_NOT_FOUND: no file at ${args.file_path}`)
      const res = spawnSync('pdftotext', [
        '-layout', '-f', String(args.first_page), '-l', String(args.last_page), path, '-',
      ], { encoding: 'utf8', timeout: 60_000, maxBuffer: 16 * 1024 * 1024 })
      if (res.error?.code === 'ENOENT') {
        throw new Error('READ_PDF_TOOL_MISSING: pdftotext is not installed (poppler); install it and retry')
      }
      if (res.status !== 0) {
        throw new Error(`READ_PDF_FAILED: pdftotext exited ${res.status ?? `signal ${res.signal}`} for ${args.file_path}`)
      }
      const pages = res.stdout.split('\f').filter((page) => page.trim() !== '')
      const labeled = pages.map((page, i) => `--- page ${Number(args.first_page) + i} ---\n${page.trimEnd()}`)
      return labeled.join('\n\n')
    },
  }))
}
