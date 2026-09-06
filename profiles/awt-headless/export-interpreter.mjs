// Which interpreter can run the export converter.
//
// A workspace reaches the converter through a link into the toolkit, so the
// interpreter that can run it is the toolkit's — not whatever `python3` the
// workspace happens to resolve, which on a PEP 668 machine commonly has no
// conversion backend at all. Follow the script's real path back to the toolkit
// root and prefer the `.venv` that `.claude/skills/export/scripts/requirements.txt`
// tells the reader to build.
//
// Kept out of the plugin so it can be tested without a dsh installation, the
// same separation `pdf-pages.mjs` uses for the page labeller.

import { existsSync, realpathSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'

/**
 * @param {string} script absolute path to convert_to_docx.py, possibly reached
 *   through a workspace's `.agents/skills` link
 * @param {{ env?: Record<string, string | undefined> }} [options]
 * @returns {string} the interpreter to spawn
 */
export function exportInterpreter(script, options = {}) {
  const env = options.env ?? process.env
  if (env.AWT_PYTHON) return env.AWT_PYTHON
  try {
    // <toolkit>/.claude/skills/export/scripts/convert_to_docx.py
    const toolkit = resolve(dirname(realpathSync(script)), '..', '..', '..', '..')
    const venv = join(toolkit, '.venv', 'bin', 'python')
    if (existsSync(venv)) return venv
  } catch {
    // An unreadable or dangling path is not this function's problem; the caller
    // already reports EXPORT_TOOL_MISSING for a converter it cannot find.
  }
  return 'python3'
}
