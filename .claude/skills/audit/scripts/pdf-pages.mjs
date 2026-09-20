// pdftotext separates physical pages with form feeds. Empty interior pages
// still consume a page number; only the final delimiter is discarded.
// Library only. Moved unchanged from the retired profiles/awt-headless on
// 2026-09-20; see docs/specs/2026-09-20-retire-dsh-line-design.md.
export function labelPdfPages(text, firstPage = 1) {
  const pages = text.split('\f')
  if (pages.at(-1)?.trim() === '') pages.pop()
  return pages.map((page, index) => `--- page ${firstPage + index} ---\n${page.trimEnd()}`).join('\n\n')
}
