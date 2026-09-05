// The awt profile's `export_docx` tool (P4 item 3): a registered tool — not
// a shell command — so the pre-export gate can deny it deterministically on
// the monotonic guard seam (shell-command inspection is not a seam). The
// body only runs after EXPORT_SOURCES_UNRESOLVED did not fire, i.e. every
// chapter citation has conforming notes and, when a bibliography exists, it
// and the chapters agree. It wraps the export skill's own converter, found
// through the workspace's skill links, and adds no policy of its own.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'awt-export'
export const inject = ['tools']

const CONVERTER = ['.agents/skills/export/scripts/convert_to_docx.py', '.claude/skills/export/scripts/convert_to_docx.py']

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'export_docx',
    description: 'Convert thesis chapters and/or reading notes to Word (.docx) under final_output/. Blocked by the pre-export gate until every cited source resolves.',
    parameters: {
      scope: { type: 'string', required: true, description: 'chapters | notes | all' },
      lang_filter: { type: 'string', required: true, description: 'en-only | all' },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args) {
      const root = process.cwd()
      const script = CONVERTER.map((rel) => join(root, rel)).find((p) => existsSync(p))
      if (script === undefined) throw new Error('EXPORT_TOOL_MISSING: no export converter under .agents/skills or .claude/skills — run awt init in this workspace')
      const res = spawnSync('python3', [script, '--base-dir', root, '--output-dir', join(root, 'final_output'),
        '--scope', String(args.scope), '--lang-filter', String(args.lang_filter)],
      { encoding: 'utf8', timeout: 300_000, maxBuffer: 16 * 1024 * 1024 })
      if (res.error?.code === 'ENOENT') throw new Error('EXPORT_TOOL_MISSING: python3 is not installed')
      if (res.status !== 0) throw new Error(`EXPORT_FAILED: converter exited ${res.status ?? `signal ${res.signal}`}`)
      return res.stdout.trim().split('\n').slice(-12).join('\n')
    },
  }))
}
