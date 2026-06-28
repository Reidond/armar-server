---
name: web-dev-best-practices
description: >
  Framework-agnostic web development best practices current as of mid-2026: semantic HTML
  and WCAG 2.2 accessibility, modern baseline CSS (container queries, :has, nesting,
  cascade layers), Core Web Vitals performance (LCP, INP, CLS, images, fonts, bundle
  discipline), web security essentials (XSS/CSP, CSRF, sessions and cookies, security
  headers, OWASP Top 10 2025), REST API design and HTTP caching, accessible forms,
  progressive enhancement, and native platform features that replace library habits
  (dialog, popover, view transitions, AbortController). Auto-loads as background knowledge
  when building web UIs, APIs, or handling web security, performance, or accessibility
  work. Does NOT cover React patterns (see react-best-practices) or TypeScript language
  practices (see typescript-best-practices). Keywords: HTML, CSS, accessibility, a11y,
  WCAG, ARIA, Core Web Vitals, LCP, INP, CLS, XSS, CSP, CSRF, cookies, security headers,
  REST, caching, forms, progressive enhancement.
user-invocable: false
metadata:
  type: reference
---

# Web Development Best Practices

## Role

Background knowledge for building web applications in this project. Framework-agnostic:
applies to any HTML/CSS/JS frontend and any HTTP backend. Current as of mid-2026 —
verified against web.dev, MDN, OWASP, and W3C (not SEO aggregators).

## When This Skill Activates

- Writing HTML, CSS, or frontend JavaScript
- Designing or implementing HTTP APIs
- Any work touching web security, performance, or accessibility
- Reviewing web code for correctness against platform standards

---

## 1. Semantic HTML First — Native Elements Before ARIA

Native elements ship keyboard handling, focus, and assistive-technology semantics for
free. A `div` with a click handler ships none of them. This is the largest single class
of real-world accessibility failures (WebAIM Million 2026: 95.9% of top-1M home pages
fail WCAG; empty/fake buttons and links are top-6 errors).

```html
<!-- GOOD -->
<button type="button" onclick="save()">Save</button>
<a href="/reports">Reports</a>
<nav>…</nav> <main>…</main> <ul>…</ul>

<!-- BAD — no keyboard access, no focus, no role -->
<div class="btn" onclick="save()">Save</div>
<span class="link" onclick="navigate('/reports')">Reports</span>
```

Rule of thumb: `button` for actions, `a href` for navigation, headings in order
(`h1`→`h2`→`h3`, never skipped for styling), landmarks (`main`, `nav`, `header`,
`footer`) once per page region.

## 2. ARIA Only to Fill Gaps — No ARIA Is Better Than Bad ARIA

W3C's First Rule of ARIA: if a native element provides the semantics, use it. Pages
using ARIA average MORE detected errors than pages without it. ARIA adds semantics,
never behavior — `role="tab"` does not make arrow keys work; that's still your job.

Legitimate ARIA: live regions (`aria-live="polite"` for async updates), state not in
HTML (`aria-expanded`, `aria-current`), labeling relationships (`aria-describedby`,
`aria-labelledby`).

```html
<!-- GOOD -->
<button aria-expanded="false" aria-controls="menu">Filters</button>

<!-- BAD — redundant role, label duplicating visible text -->
<button role="button" aria-label="Save">Save</button>
```

Never put `aria-hidden="true"` on focusable content. Decorative images get `alt=""`
(explicitly empty); informative images get alt that conveys the same information —
not the filename, not "image of".

## 3. Focus Must Be Visible and Managed

- Never `outline: none` without an equal-or-better `:focus-visible` style (WCAG 2.4.7;
  2.2 adds Focus Not Obscured — sticky headers must not cover the focused element).
- On SPA route change: move focus to the new content's heading or set `tabindex="-1"`
  target. On dialog close: return focus to the trigger (`<dialog>` does this free).
- Tab order follows DOM order — avoid positive `tabindex`; fix the DOM instead.

## 4. WCAG 2.2 AA Is the Target

Current standard (EU Accessibility Act enforced since June 2025). Beyond 2.1, build to
the new 2.2 criteria: pointer targets ≥ 24×24 CSS px (or spaced equivalently); every
drag interaction has a single-pointer alternative; don't ask users to re-enter
information already provided in the same flow; help mechanisms (contact, chat)
appear in the same relative place on every page; logins must not require puzzles
or transcription — allow paste, autofill, and passkeys.

Also the perennial top failure: text contrast ≥ 4.5:1 (3:1 for large text) — the #1
WebAIM error every year. Never disable zoom (`user-scalable=no`).

## 5. Modern CSS Is Baseline — Use It; Guard the Edges

Safe unguarded in all modern browsers: container size queries, `:has()`, native
nesting, `@layer`, subgrid, logical properties, `oklch()`/`color-mix()`, `dvh`/`svh`
units, `text-wrap: balance`.

```css
/* GOOD — component responds to its container, not the viewport */
.card-grid { container-type: inline-size; }
@container (min-width: 40rem) { .card { grid-template-columns: 1fr 2fr; } }

/* GOOD — state styling without JS class toggling */
form:has(:user-invalid) .submit-hint { display: block; }
```

Still NOT safe unguarded (mid-2026): CSS anchor positioning, cross-document view
transitions, container *style* queries, scroll-driven animations (Firefox still
behind a flag) — wrap in `@supports` or degrade gracefully.
When unsure about a feature, check Baseline status on MDN/web.dev — not blog posts.

Prefer logical properties (`margin-inline-start`, `inline-size`) over physical ones
for any product that may localize to RTL.

## 6. CSS Architecture: Layers Over Specificity Wars

Declare cascade-layer order once; later layers win regardless of specificity. This
eliminates `!important` escalation and load-order bugs:

```css
@layer reset, base, components, utilities, overrides;
```

Tailwind vs vanilla is a context decision, not a religion: Tailwind for
component-driven UIs and teams with mixed CSS depth (v4 is CSS-first and uses native
layers); vanilla modern CSS for content/server-rendered sites and zero-build contexts.
Hybrid (utilities + a small scoped-CSS layer for complex work) is the pragmatic norm.

## 7. Core Web Vitals: LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1

Measured at the 75th percentile of real-user (field) data. INP replaced FID in 2024.
WARNING: SEO blogs claiming "LCP tightened to 2.0s in 2026" or "Core Web Vitals 2.0 /
Visual Stability Index" are fabrications — trust only web.dev and CrUX for thresholds.

- **LCP**: optimize the one hero resource — discoverable in initial HTML, not behind
  JS or CSS background-image, `fetchpriority="high"`.
- **INP**: worst interaction latency across the whole visit — break long tasks
  (`scheduler.yield()` or chunking), move heavy compute to Web Workers, render the
  visual response before expensive work.
- **CLS**: reserve space for everything async — `width`/`height` on media,
  `aspect-ratio` or `min-height` for embeds/ads, metric-adjusted font fallbacks (§9).

## 8. Images: the LCP Image Is Special

```html
<!-- GOOD — the hero/LCP image -->
<img src="hero.avif" width="1200" height="600" fetchpriority="high"
     alt="Risk map of Southeast Asia" />

<!-- GOOD — below-the-fold images -->
<img src="chart.avif" width="800" height="400" loading="lazy" alt="…" />

<!-- BAD — lazy-loading the LCP image delays the metric you're optimizing -->
<img src="hero.jpg" loading="lazy" />
```

- Formats: AVIF first, WebP fallback, JPEG last (`<picture>` or content negotiation).
  Both AVIF and WebP are ~95%+ supported — JPEG-only is a stale habit.
- Always explicit `width`/`height` (CLS). `srcset` + `sizes` for responsive variants.
- Exactly one `fetchpriority="high"` per page; never lazy-load above-the-fold images.

## 9. Fonts: Swap Plus Metric-Adjusted Fallback

`font-display: swap` alone trades invisible text for layout shift. Pair it with a
fallback whose metrics are adjusted to match:

```css
@font-face { font-family: "Brand"; src: url(brand.woff2) format(woff2);
             font-display: swap; }
@font-face { font-family: "Brand-fallback"; src: local("Arial");
             size-adjust: 104%; ascent-override: 92%; descent-override: 24%; }
body { font-family: "Brand", "Brand-fallback", sans-serif; }
```

Self-host WOFF2; preload at most 1–2 critical fonts (`<link rel="preload" as="font"
crossorigin>`); subset to needed characters; use a variable font when you need ≥ 3
weights.

## 10. JavaScript Bundle Discipline

The fastest JavaScript is the JavaScript you don't ship. Hold a budget (~200 KB
compressed initial load is a common bar) and enforce it in CI. Ship HTML, hydrate or
attach JS only to genuinely interactive parts. `defer`/`type="module"` everything;
nothing render-blocking in `<head>` except critical CSS. Third-party scripts are the
top INP killer — each one needs justification, lazy/`async` loading, and periodic
audits. Before adding a dependency, check whether the platform does it (§20).

## 11. XSS: Encode Output, Then Add a Strict CSP

Primary defense is context-aware output encoding (framework auto-escaping). Never
build DOM from user data with `innerHTML` — use `textContent`, or sanitize, or adopt
Trusted Types (`require-trusted-types-for 'script'`) to make unsafe sinks fail.

CSP is the defense-in-depth layer, and only the strict form counts:

```
# GOOD — strict, nonce-based (per-response random nonce)
Content-Security-Policy: script-src 'nonce-{RANDOM}' 'strict-dynamic';
  object-src 'none'; base-uri 'none';

# BAD — allowlist CSPs are bypassable (JSONP/gadget scripts); 'unsafe-inline' is no CSP
Content-Security-Policy: script-src 'self' 'unsafe-inline' *.googleapis.com;
```

Full header recipes and the OWASP Top 10:2025 list: [references/security.md](references/security.md).

## 12. CSRF: Fetch Metadata First, Tokens as Fallback

`SameSite` cookies alone are NOT sufficient (same-site JS contexts, subdomain trust,
older clients). Current OWASP guidance (CSRF Cheat Sheet, updated Dec 2025) accepts
`Sec-Fetch-Site` validation as a complete primary defense for modern-browser apps:

- Reject state-changing requests (POST/PUT/PATCH/DELETE) when
  `Sec-Fetch-Site: cross-site`.
- Header absent (old client/non-browser)? Fall back to Origin/Referer checks or
  synchronizer tokens — don't silently allow.
- Never accept state changes via GET.

## 13. Sessions and Cookies: HttpOnly or It's Gone

Never store session tokens or JWTs in `localStorage`/`sessionStorage` — any XSS in
the origin exfiltrates them; there is no HttpOnly equivalent. Patterns that hold up:
server-side sessions in a hardened cookie, or short-lived in-memory access token +
refresh token in an HttpOnly cookie with rotation and reuse detection.

```
# GOOD — __Host- pins to origin (requires Secure, Path=/, no Domain)
Set-Cookie: __Host-session=…; HttpOnly; Secure; SameSite=Lax; Path=/

# BAD
Set-Cookie: session=…; Domain=.example.com        # subdomain takeover can steal/overwrite
localStorage.setItem("jwt", token)                # XSS = account takeover
```

## 14. Ship the Security Header Baseline

On every production response: `Strict-Transport-Security`, CSP (§11),
`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy` (deny unused sensors), `Cross-Origin-Opener-Policy: same-origin`,
`Cross-Origin-Resource-Policy: same-origin`. Frame control belongs in CSP
`frame-ancestors` (X-Frame-Options is legacy). Exact values and rationale:
[references/security.md](references/security.md).

## 15. Validate and Authorize Server-Side, Always

Client-side validation is UX only. The server re-validates every input (type, length,
range, allowlist) and — the #1 OWASP risk, Broken Access Control — authorizes every
object access against the session, never trusting client-supplied IDs, roles, or
prices. Deny by default; fail closed (OWASP Top 10:2025 added "Mishandling of
Exceptional Conditions" — error paths that fail open are a category of their own).

## 16. REST APIs: Predictable Resources, Honest Status Codes

Plural-noun resources (`GET /assessments/42`), methods carry semantics, status codes
tell the truth — never 200 with an error envelope. Errors use RFC 9457 Problem Details:

```json
// GOOD — application/problem+json, status 422
{ "type": "https://api.example.com/problems/validation",
  "title": "Validation failed", "status": 422,
  "detail": "destination_country is not a valid ISO 3166-1 code",
  "errors": [{ "field": "destination_country", "code": "invalid_format" }] }

// BAD — 200 OK with { "success": false, "error": "Internal error: at line 84 …" }
```

Never leak stack traces or internals in `detail`. Paginate every collection. Use
idempotency keys for retried unsafe operations. More:
[references/api-design.md](references/api-design.md).

## 17. HTTP Caching Is API Design

Every response gets an explicit `Cache-Control`. Hashed static assets:
`Cache-Control: public, max-age=31536000, immutable`. API reads: `ETag` +
`If-None-Match` → `304 Not Modified` (prefer ETag over `Last-Modified`). Personalized
responses: `Cache-Control: private` (or `no-store` when sensitive — `no-store` alone
forbids all caching, making `private` redundant) — and `Vary` on anything that changes
the representation. An API without caching headers makes every client re-download
everything forever.

## 18. Forms Done Right

```html
<!-- GOOD -->
<label for="email">Work email</label>
<input id="email" name="email" type="email" autocomplete="email" required
       aria-describedby="email-error" />
<p id="email-error" class="error">Enter an email like name@company.com</p>

<!-- BAD — placeholder is not a label; it disappears on input -->
<input type="text" placeholder="Email" />
```

- Visible `<label>` per control; correct `type`/`inputmode` (mobile keyboards);
  standardized `autocomplete` tokens — required by WCAG 1.3.5 on personal-data fields
  and proven to halve mobile input errors.
- Errors: validate on submit, then per-field on blur (not while first typing);
  link via `aria-describedby` + `aria-invalid="true"`; message names the problem AND
  the fix ("Enter a date after today"), never just "Invalid".
- The form submits and works without JavaScript (§19); the server re-validates (§15).

## 19. Progressive Enhancement: Core Flows Work Before JS

HTML-first: links navigate, forms POST, content renders — then JS upgrades the
experience. JS can fail to arrive (flaky networks, extensions, CDN hiccups, bots);
a core flow that white-screens without it is a reliability bug, not a purity debate.
Keep state in the URL (`URLSearchParams`) so back/refresh/share work — an app that
breaks the back button is broken.

## 20. Use the Platform Before Reaching for a Library

The platform replaced a generation of library habits — each native feature brings
focus management, top-layer rendering, and accessibility for free:

- `<dialog>` + `showModal()` — modals (focus trap, Esc, `::backdrop`).
- Popover API (`popover` + `popovertarget`, Baseline 2024) — tooltips, menus,
  overlays; light dismiss, no z-index management, zero JS for common cases.
- Same-document View Transitions (Baseline 2025) — animated UI changes
  (cross-document is still emerging — feature-detect).
- `fetch` + `AbortController` — always cancel stale requests and set timeouts:

```js
// GOOD — cancels the previous in-flight search; 10s timeout
controller?.abort();
controller = new AbortController();
const res = await fetch(url, { signal: AbortSignal.any(
  [controller.signal, AbortSignal.timeout(10_000)]) });
```

- `Intl.*` over moment/dayjs for formatting; `structuredClone` over lodash
  cloneDeep; `<details>` for accordions; `<input type="date">` before date-picker
  libraries. Catalog with examples:
  [references/platform-features.md](references/platform-features.md).

---

## Anti-Patterns Quick Reference

| Anti-pattern | Why it fails | Instead |
|---|---|---|
| Clickable `div`/`span` | No keyboard, focus, or role | `<button>`, `<a href>` (§1) |
| Redundant or behavior-free ARIA | Worse than no ARIA | Native elements; ARIA for gaps (§2) |
| `outline: none`, no replacement | Invisible keyboard focus | `:focus-visible` styles (§3) |
| Placeholder as label | Vanishes on input; fails WCAG | Visible `<label>` (§18) |
| Disabling zoom | Locks out low-vision users | Never `user-scalable=no` (§4) |
| Lazy-loading the LCP image | Directly delays LCP | `fetchpriority="high"`, eager (§8) |
| Media without dimensions | Layout shift (CLS) | `width`/`height`/`aspect-ratio` (§8) |
| `font-display: swap` alone | Swap-induced CLS | Metric-adjusted fallback (§9) |
| Allowlist or `unsafe-inline` CSP | Bypassable; theater | Nonce + `strict-dynamic` (§11) |
| `innerHTML` with user data | DOM XSS | `textContent`/sanitize/Trusted Types (§11) |
| Relying on `SameSite` for CSRF | Incomplete defense | `Sec-Fetch-Site` + token fallback (§12) |
| Tokens in `localStorage` | XSS = account takeover | HttpOnly cookies (§13) |
| Trusting client validation/IDs | Bypassed with curl; IDOR | Server validation + per-object authz (§15) |
| GET with side effects | CSRF, prefetch, cache havoc | POST/PUT/DELETE (§12, §16) |
| 200 + error envelope; stack traces | Breaks clients; leaks internals | Status codes + RFC 9457 (§16) |
| `!important` escalation | Unmaintainable cascade | `@layer` ordering (§6) |
| Hand-rolled modal/tooltip stacks | Re-implements focus/stacking badly | `<dialog>`, popover (§20) |
| `fetch` without AbortController | Stale-response races, no timeout | Abort + timeout signals (§20) |
| App state not in URL | Breaks back/refresh/share | URL as state (§19) |

## Currency Rule

Thresholds, Baseline status, and OWASP editions change. Verify against web.dev/CrUX
(vitals), MDN Baseline data (features), and owasp.org (security) — never against
SEO-optimized "2026 guide" blogs, which routinely fabricate changes.

## Additional Resources

- [references/security.md](references/security.md) — full security header recipes,
  strict-CSP rollout, cookie attribute matrix, OWASP Top 10:2025 mapped to web work
- [references/api-design.md](references/api-design.md) — REST conventions, RFC 9457
  patterns, status-code selection, caching and conditional requests
- [references/platform-features.md](references/platform-features.md) — native platform
  feature catalog with usage examples and Baseline status
