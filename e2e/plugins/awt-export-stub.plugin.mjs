// e2e-only stub of the awt profile's `export_docx` tool (args: scope,
// lang_filter). It exists so the EXPORT_SOURCES_UNRESOLVED guard has a
// registered tool to deny — an unregistered name would fail as UNKNOWN_TOOL
// before the guard stage. When allowed it leaves a marker file so the
// negative direction is provable too; it never runs pandoc.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'awt-export-stub'
export const inject = ['tools']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'export_docx',
    description: 'Stub thesis exporter (e2e): records that an export ran.',
    parameters: {
      scope: { type: 'string', required: true, description: 'chapters | notes | all' },
      lang_filter: { type: 'string', required: true, description: 'en-only | all' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      mkdirSync(join(process.cwd(), 'final_output'), { recursive: true })
      writeFileSync(join(process.cwd(), 'final_output', 'EXPORTED.txt'), `${args.scope} ${args.lang_filter}`)
      return `stub export_docx ${args.scope} ${args.lang_filter}`
    },
  }))
}
