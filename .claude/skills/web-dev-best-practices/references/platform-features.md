# Native Platform Features Catalog

Companion to SKILL.md §20. Baseline status as of mid-2026 — when in doubt, re-check
MDN Baseline data; do not trust blog posts for availability claims.

## `<dialog>` — modals and non-modal panels (Baseline, widely available)

```html
<dialog id="confirm">
  <form method="dialog">
    <h2>Delete assessment?</h2>
    <button value="cancel" autofocus>Cancel</button>  <!-- focus the safe action -->
    <button value="confirm">Delete</button>
  </form>
</dialog>
<script>
  const dlg = document.getElementById("confirm");
  dlg.showModal();                       // modal: focus trap, Esc, inert background
  dlg.addEventListener("close", () => { if (dlg.returnValue === "confirm") … });
</script>
```

Free: top-layer rendering, focus trapping, Esc-to-close, `::backdrop` styling,
`returnValue`, focus restoration to the trigger. Use `show()` for non-modal.
Don't rebuild this with `div` + z-index + focus-trap libraries.

## Popover API — tooltips, menus, toasts (Baseline 2024)

```html
<button popovertarget="filters">Filters</button>
<div id="filters" popover>
  …menu content…
</div>
```

Free: top layer (no z-index management), light dismiss (click-outside/Esc for
`popover="auto"`), keyboard accessibility, zero JS for the common case.
`popover="manual"` for toasts that shouldn't light-dismiss. Anchor the position with
CSS anchor positioning ONLY behind `@supports(anchor-name: --a)` — not Baseline yet;
fallback to static positioning.

Popover vs dialog: popover is non-modal (page stays interactive); `showModal()` is
modal. A "popover that blocks the page" should be a dialog.

## View Transitions — animated state/page changes

- Same-document (Baseline 2025): wrap DOM updates in
  `document.startViewTransition(() => updateDOM())`; customize via
  `::view-transition-old/new(name)`. Feature-detect:
  `if (!document.startViewTransition) updateDOM()`.
- Cross-document (MPA): enable with `@view-transition { navigation: auto; }` —
  still rolling out across browsers (Interop 2026 focus); pure progressive
  enhancement, never required for function.
- Respect `prefers-reduced-motion` in transition styling.

## fetch + AbortController — cancellation and timeouts

```js
let controller;
async function search(q) {
  controller?.abort();                           // kill the previous request
  controller = new AbortController();
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, {
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);   // fetch only rejects on network failure
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") return;       // expected — stale or user-cancelled
    if (err.name === "TimeoutError") …           // surface timeout distinctly
    throw err;
  }
}
```

Gotchas: `fetch` does NOT reject on 4xx/5xx — check `res.ok`; abort previous
in-flight requests on rapid re-trigger (search-as-you-type) or responses race and
stale data wins; always set a timeout — fetch has none by default. If you pass a
custom reason (`abort("stale")`), the rejection IS that value — `err.name ===
"AbortError"` no longer matches; call `abort()` bare or check `signal.aborted`.

## Library habits replaced by the platform

| Old habit | Platform replacement | Notes |
|---|---|---|
| moment/dayjs formatting | `Intl.DateTimeFormat`, `Intl.NumberFormat`, `Intl.RelativeTimeFormat` | Locale-aware, zero bytes; Temporal API is arriving for date *arithmetic* — check Baseline before unguarded use |
| lodash `cloneDeep` | `structuredClone()` | Handles Dates, Maps, Sets, cycles |
| lodash `debounce`-only imports | ~10-line local util or `scheduler` APIs | Don't pull a library for one function |
| Accordion plugins | `<details><summary>` | Stylable, accessible, searchable (`hidden="until-found"` where supported) |
| Custom date inputs | `<input type="date">` first | Reach for a picker library only when ranges/constraints demand it |
| Smooth-scroll libraries | `scroll-behavior: smooth`, `scrollIntoView({behavior:"smooth"})` | Respect `prefers-reduced-motion` |
| Scroll-position animation (JS) | CSS scroll-driven animations (`animation-timeline`) | NOT Baseline yet (Firefox behind a flag) — enhancement only |
| jQuery DOM/AJAX | `querySelector`, `classList`, `fetch`, `FormData` | `new FormData(form)` serializes a whole form |
| URL/query-string parsers | `URL`, `URLSearchParams` | Also the right tool for state-in-URL (§19) |
| uuid package | `crypto.randomUUID()` | Secure contexts |
| Clipboard plugins | `navigator.clipboard.writeText()` | Async, permission-aware |
| Copy-pasted color libs | `oklch()`, `color-mix()` in CSS | Perceptually uniform |

## CSS features quick status (mid-2026)

| Feature | Status | Action |
|---|---|---|
| Container size queries, `:has()`, nesting, `@layer`, subgrid, logical properties, `dvh`/`svh`, `oklch` | Baseline, widely available | Use freely |
| `@scope` | All major browsers since late 2025 (newly available) | Use; trivial degradation paths anyway |
| `text-wrap: balance` | Baseline newly available | Use as enhancement |
| Scroll-driven animations | NOT Baseline — Chrome/Edge + Safari 26; Firefox behind a flag | Progressive enhancement only; never gate content on it |
| Container *style* queries | Landing cross-browser (Interop 2026) | Guard with `@supports` |
| Anchor positioning | NOT Baseline | `@supports(anchor-name: --a)` + fallback |
| Cross-document view transitions | Rolling out | Pure enhancement only |
