// Portable identities for derived evidence. Raw logs and their bytes stay intact.
import { posix, win32 } from 'node:path'

function flavour(path) {
  return /^[A-Za-z]:[\\/]/.test(path) || path.startsWith('\\\\') ? win32 : posix
}

export function absoluteRunPath(target, base) {
  return flavour(base).resolve(base, target)
}

export function relativeRunPath(target, runRoot) {
  const path = flavour(runRoot)
  const result = path.relative(runRoot, absoluteRunPath(target, runRoot))
  if (path.isAbsolute(result)) throw new Error('Run provenance requires a relative path on the same volume')
  return result.split(path.sep).join('/') || '.'
}

// Every run reference is relative to the containing metrics file's run root.
// When resuming, sourceRoot is the previous metrics file's run root for the
// entire inherited chain; nested references do not change that base.
export function publicContinuation(value, runRoot, sourceRoot = runRoot) {
  if (!value) return value
  const priorRoot = absoluteRunPath(value.run, sourceRoot)
  return { ...value, run: relativeRunPath(priorRoot, runRoot),
    ...(value.earlierContinuation ? {
      earlierContinuation: publicContinuation(value.earlierContinuation, runRoot, sourceRoot),
    } : {}) }
}
