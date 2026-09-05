// AWT presentation-layer branding (P3 amendment: AWT is the product; the
// harness is internal). Registers an index.html transform on the native
// webserver seam (ctx.webServer.tapIndex) — the shipped extension point for
// index rewrites — to carry the AWT identity in the web surface: tab title
// and the sidebar wordmark. No client code is forked and no upstream file
// is patched; removing this row restores stock branding completely.
//
// FRAGILITY, stated plainly (the presentation-seam discipline): the
// wordmark override targets the CSS-module class SUFFIX `logoRow`
// ([class*="logoRow"]), pinned against @deepseek-ai/dsh@0.1.0-rc.6's built
// web client. Semantic suffixes survive hash churn but not an upstream
// rename; the harness-pin tripwire (guards/tests/harness-pin-probe.test.ts)
// already forces a re-review on any pin bump — re-verify this override
// there. The model-facing identity is NOT this file's job: that is the
// system-prompt row (includeHarnessIdentity: false + the AWT persona) in
// cordis.patch.yml.
//
// The webserver dependency is taken through the `ctx.inject` dependency
// gate (the same pattern the guards plugin uses for sessionProjections):
// the callback runs when `webServer` becomes available and never blocks
// activation — in the headless composition it simply never fires and this
// plugin is a mounted no-op. Cordis 4's static `inject` list is
// all-required, which would fail the headless profile at boot.

export const name = 'awt-brand'

const TITLE = 'Academic Writing Toolkit'

const STYLE = `
<style data-awt-brand>
  [class*="logoRow"] { position: relative; }
  [class*="logoRow"] > * { visibility: hidden; }
  [class*="logoRow"]::after {
    content: "AWT · Academic Writing Toolkit";
    visibility: visible;
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.02em;
    color: #15967d;
    white-space: nowrap;
  }
</style>`

const SCRIPT = `
<script data-awt-brand>
  (() => {
    const rebrand = () => {
      if (document.title.includes('DeepSeek Harness')) {
        document.title = document.title.replace('DeepSeek Harness', ${JSON.stringify(TITLE)})
      }
    }
    rebrand()
    const observe = () => {
      const el = document.querySelector('title')
      if (!el) return setTimeout(observe, 500)
      new MutationObserver(rebrand).observe(el, { childList: true })
    }
    observe()
  })()
</script>`

export function apply(ctx) {
  ctx.inject(['webServer'], (scoped) => {
    scoped.webServer.tapIndex((html) => html
      .replace(/<title>[^<]*<\/title>/, `<title>${TITLE}</title>`)
      .replace('</head>', `${STYLE}${SCRIPT}\n</head>`))
  })
}
