// pdftotext separates physical pages with form feeds. Empty interior pages
// still consume a page number; only the final delimiter is discarded.
export function labelPdfPages(text, firstPage = 1) {
  const pages = text.split('\f')
  if (pages.at(-1)?.trim() === '') pages.pop()
  return pages.map((page, index) => `--- page ${firstPage + index} ---\n${page.trimEnd()}`).join('\n\n')
}
