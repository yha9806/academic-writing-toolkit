// E1 machine graders (P3 spec item 3) — pure functions, no I/O, no model.
// The producer (run-e1.mjs) wires them to real artifacts; unit tests pin
// their behavior offline. Lint and citation extraction are INJECTED so the
// graders stay dependency-free and the producer can pass the shipped
// guards/dist implementations — the same code the enforcement uses.

/** Collapse whitespace and normalize typographic quotes/dashes for matching. */
export function normalizeForMatch(text) {
  return text
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .replace(/[–—]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Extract quoted spans (>= 4 words — shorter spans are idiom, not quotation)
 * with an adjacent page reference when one exists: "..." (p.12) / (Smith,
 * 2024, p. 12) / (p.12-13).
 */
export function extractQuotedSpans(text) {
  const spans = []
  const re = /["“]([^"“”]{10,}?)["”]/g
  for (const m of text.matchAll(re)) {
    const quote = m[1]
    if (quote.trim().split(/\s+/).length < 4) continue
    const tail = text.slice(m.index + m[0].length, m.index + m[0].length + 60)
    const page = tail.match(/\(\s*(?:[A-Za-z'’-]+,\s*\d{4},\s*)?pp?\.?\s*(\d+)/)
    spans.push({ quote, page: page ? Number(page[1]) : undefined })
  }
  return spans
}

/**
 * Quote fidelity: every quoted span must appear verbatim (whitespace- and
 * typography-normalized) in the reference text the model was shown.
 */
export function gradeQuoteFidelity(spans, referenceText) {
  const reference = normalizeForMatch(referenceText)
  const misses = spans.filter((s) => !reference.includes(normalizeForMatch(s.quote)))
  return {
    quotes: spans.length,
    matched: spans.length - misses.length,
    misses: misses.map((s) => s.quote.slice(0, 80)),
  }
}

/**
 * Page-number accuracy: for spans that cite a page, the span must appear in
 * THAT page's text. Spans without a page reference are counted separately
 * (uncited), not marked wrong.
 */
export function gradePageAccuracy(spans, pagesText) {
  const cited = spans.filter((s) => s.page !== undefined)
  const wrong = cited.filter((s) => {
    const page = pagesText.get(s.page)
    return page === undefined || !normalizeForMatch(page).includes(normalizeForMatch(s.quote))
  })
  return {
    cited: cited.length,
    correct: cited.length - wrong.length,
    uncited: spans.length - cited.length,
    wrong: wrong.map((s) => ({ page: s.page, quote: s.quote.slice(0, 80) })),
  }
}

/** Notes parseability under the shipped notes lint (injected). */
export function gradeNotesParseability(notesText, lintNotes, hasErrors) {
  if (notesText === undefined) return { present: false, parseable: false, errors: ['notes file absent'] }
  const issues = lintNotes(notesText)
  return {
    present: true,
    parseable: !hasErrors(issues),
    errors: issues.filter((i) => i.severity === 'error').map((i) => `${i.code}: ${i.message}`),
  }
}

/**
 * Citations-to-unopened-sources: citations in the drafted section that name
 * a source the session never opened (the E1 run opens exactly the manifest
 * PDF). extractCitations is the guards' own conservative extractor.
 */
export function gradeUnopenedCitations(draftText, openedSources, extractCitations) {
  if (draftText === undefined) return { citations: 0, unopened: [], draftPresent: false }
  const opened = new Set(openedSources.map((s) => `${s.surname.toLowerCase()}|${s.year}`))
  const citations = extractCitations(draftText)
  const unopened = citations.filter((c) => !opened.has(`${c.surname.toLowerCase()}|${c.year}`))
  return {
    draftPresent: true,
    citations: citations.length,
    unopened: unopened.map((c) => `${c.surname} ${c.year}`),
  }
}

/** Split the read_pdf tool's labeled output back into a per-page map. */
export function pagesFromLabeledText(text) {
  const pages = new Map()
  const re = /--- page (\d+) ---\n([\s\S]*?)(?=\n--- page \d+ ---|$)/g
  for (const m of text.matchAll(re)) pages.set(Number(m[1]), m[2])
  return pages
}
