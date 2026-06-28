# Web Security Reference

Companion to SKILL.md §11–§15. Sources: OWASP Top 10:2025, OWASP Cheat Sheet Series
(CSP, CSRF, Session Management, HTTP Headers), web.dev/articles/strict-csp, MDN.

## OWASP Top 10:2025 (published Nov 2025) — mapped to web work

| # | Category | What it means for everyday web code |
|---|----------|--------------------------------------|
| A01 | Broken Access Control (now includes SSRF) | Authorize every object access server-side; deny by default; validate outbound URLs the server fetches |
| A02 | Security Misconfiguration (up from #5) | Headers, CORS, cloud storage perms, default creds, verbose errors off in prod |
| A03 | Software Supply Chain Failures (new, broader than "Vulnerable Components") | Lockfiles, dependency audit in CI, pin CI actions, verify integrity (SRI for third-party scripts) |
| A04 | Cryptographic Failures | TLS everywhere, modern password hashing (argon2id/bcrypt), no homegrown crypto |
| A05 | Injection (down from #3; includes XSS, SQLi) | Parameterized queries; context-aware output encoding |
| A06 | Insecure Design | Threat-model state-changing flows before building |
| A07 | Authentication Failures | Rate-limit logins, MFA/passkeys, no credential hints |
| A08 | Software or Data Integrity Failures | Signed updates, no untrusted deserialization |
| A09 | Security Logging & Alerting Failures | Log authn/authz failures with alerting, no secrets in logs |
| A10 | Mishandling of Exceptional Conditions (new) | Fail closed; error paths must not skip auth checks or leak internals |

## Strict CSP rollout

Target policy (one fresh cryptographic nonce per response):

```
Content-Security-Policy:
  script-src 'nonce-{RANDOM}' 'strict-dynamic' https: 'unsafe-inline';
  object-src 'none';
  base-uri 'none';
  frame-ancestors 'self';
  form-action 'self';
```

Notes:
- `https:` and `'unsafe-inline'` are backward-compat fallbacks: browsers that support
  nonces + `strict-dynamic` ignore them; older browsers degrade to an allowlist.
- `'strict-dynamic'` lets nonce-trusted scripts load their own dependencies — this is
  what makes strict CSP deployable with bundlers and third-party widgets.
- Roll out with `Content-Security-Policy-Report-Only` + a `report-to` endpoint first;
  fix violations; then enforce.
- Hash-based (`'sha256-…'`) variant suits fully static sites where nonces can't be
  injected per-response.
- DOM XSS hardening: `require-trusted-types-for 'script'; trusted-types app-policy;`
  makes `innerHTML`/`eval` sinks reject raw strings.

Why allowlist CSPs fail: any allowlisted domain hosting a JSONP endpoint or an
expression-evaluating library (gadget) becomes a bypass. Research (Google, "CSP Is
Dead, Long Live CSP") found >94% of allowlist policies bypassable.

## Security header baseline (production HTTPS responses)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

- HSTS: start with a small `max-age` in staging; `preload` only when committed —
  it is hard to undo.
- `Permissions-Policy`: explicitly deny every powerful feature you don't use. The old
  `Feature-Policy` syntax silently does nothing in current browsers.
- COOP `same-origin` severs `window.opener` links and enables process isolation;
  add `Cross-Origin-Embedder-Policy: require-corp` only if you need
  `SharedArrayBuffer`/high-res timers (it breaks un-opted-in cross-origin embeds).
- CORP `same-origin` blocks other origins from embedding your resources; relax to
  `cross-origin` only for genuinely public assets (CDN images/fonts).
- Frame control: CSP `frame-ancestors` supersedes `X-Frame-Options`. Setting both is
  fine; `frame-ancestors` wins where supported.
- Remove `Server`/`X-Powered-By` version banners.

## Cookie attribute matrix

| Attribute | Session cookie value | Why |
|---|---|---|
| Name prefix | `__Host-` | Enforces Secure + Path=/ + no Domain; immune to subdomain cookie injection |
| `HttpOnly` | always | JS (and therefore XSS) cannot read it |
| `Secure` | always | HTTPS only |
| `SameSite` | `Lax` (default) or `Strict` (high-value actions) | Cuts most cross-site sends; NOT a complete CSRF defense |
| `Path` | `/` | Required by `__Host-` |
| `Domain` | omit | Host-only; do not widen to subdomains |
| `Max-Age` | match server session timeout | Idle + absolute timeouts server-side regardless |
| `Partitioned` | only for cross-site iframe use cases (CHIPS) | Keeps `SameSite=None` embedded cookies partitioned per top site |

Session hygiene: regenerate the session ID on login (session fixation), invalidate
server-side on logout, rotate refresh tokens and detect reuse (treat a reused rotated
token as compromise — revoke the family).

## CSRF decision flow

1. Endpoint changes state? It must be POST/PUT/PATCH/DELETE — never GET.
2. `Sec-Fetch-Site` present?
   - `same-origin` → allow. `none` (direct navigation/bookmark) → allow.
   - `same-site` → allow only if you trust all subdomains; otherwise reject.
   - `cross-site` → reject (403), log.
3. Header absent (pre-2023 browsers, non-browser clients) → fall back: validate
   `Origin`/`Referer` against an allowlist, or require a synchronizer/double-submit
   token. Absence of all signals → reject, don't allow.
4. Keep `SameSite=Lax`+ on session cookies as defense-in-depth, not as the defense.

## Input validation server-side

- Validate type, length, range, format with allowlists at the API boundary
  (JSON Schema / framework validators); reject, don't "clean".
- Parameterized queries only — string-built SQL is A05 regardless of escaping effort.
- File uploads: validate type by content (magic bytes) not extension, store outside
  the web root with generated names, serve with `Content-Disposition` +
  `X-Content-Type-Options: nosniff`.
- Outbound fetches of user-supplied URLs (webhooks, importers): allowlist schemes and
  hosts, resolve-and-pin DNS, block private IP ranges (SSRF — now part of A01).
