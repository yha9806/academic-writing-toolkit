// e2e-only stub of the awt profile's planned pdftotext-backed `read_pdf`
// tool (args: file_path, first_page, last_page). It exists so the
// PAGE_RANGE_EXCEEDED guard has a registered tool to deny — an unregistered
// name would fail as UNKNOWN_TOOL before the guard stage. The body never
// runs in the deny scenario; when allowed it returns a fixed marker string.
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'awt-read-pdf-stub'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'read_pdf',
    description: 'Stub PDF page reader (e2e): echoes the requested page range.',
    parameters: {
      file_path: { type: 'string', required: true, description: 'PDF path.' },
      first_page: { type: 'integer', required: true, description: '1-based first page.' },
      last_page: { type: 'integer', required: true, description: '1-based last page (inclusive).' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      return `stub read_pdf ${args.file_path} pages ${args.first_page}-${args.last_page}`
    },
  }))
}
