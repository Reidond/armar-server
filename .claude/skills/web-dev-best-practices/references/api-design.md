# API Design Reference

Companion to SKILL.md §16–§17. Sources: RFC 9457, RFC 9110/9111 (HTTP semantics and
caching), OWASP REST Security Cheat Sheet.

## Resource and URL conventions

- Plural nouns, no verbs: `GET /assessments`, `POST /assessments`,
  `GET /assessments/{id}`, `PATCH /assessments/{id}`, `DELETE /assessments/{id}`.
- Nest one level max for ownership (`/trips/{id}/assessments`); deeper relations get
  query filters (`/assessments?trip_id=…`).
- Actions that don't map to CRUD: a sub-resource noun (`POST /assessments/{id}/approval`)
  beats RPC-style verbs; if a verb is unavoidable, make it clearly an action endpoint.
- Filtering, sorting, pagination via query params: `?status=active&sort=-created_at
  &cursor=…`. Prefer cursor pagination for large/changing sets; return `next` links.
- Version in the path (`/v1/`) or media type; never break existing fields — add,
  deprecate, then remove on a published timeline.

## Status code selection

| Situation | Code |
|---|---|
| Read OK / update OK with body | 200 |
| Created (return `Location` header) | 201 |
| Accepted for async processing (return status URL) | 202 |
| Success, no body (DELETE, some PUTs) | 204 |
| Conditional GET, unchanged | 304 |
| Malformed request (unparseable) | 400 |
| Not authenticated | 401 |
| Authenticated but not allowed | 403 |
| Not found (also for hiding existence) | 404 |
| Method not supported on resource | 405 |
| Conflict (version/state, duplicate) | 409 |
| Well-formed but semantically invalid | 422 |
| Rate limited (include `Retry-After`) | 429 |
| Unexpected server failure | 500 |
| Upstream dependency failed | 502/503/504 |

Never: 200 with `{"success": false}`; 500 for validation errors; 403 vs 404
inconsistency that leaks resource existence to unauthorized callers.

## RFC 9457 Problem Details

`Content-Type: application/problem+json`. Standard members: `type` (URI identifying
the problem class — dereferenceable docs ideally), `title` (short, stable per type),
`status`, `detail` (occurrence-specific, human-readable), `instance` (URI of this
occurrence). Extensions are allowed and clients MUST ignore unknown ones.

```json
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Validation failed",
  "status": 422,
  "detail": "2 fields failed validation.",
  "instance": "/v1/assessments",
  "errors": [
    { "field": "destination_country", "code": "invalid_format",
      "message": "Must be an ISO 3166-1 alpha-2 code." },
    { "field": "start_date", "code": "out_of_range",
      "message": "Must be today or later." }
  ]
}
```

Rules:
- One stable `type` URI per problem class; clients branch on `type`, not on `detail`.
- `detail` explains this occurrence; it must never contain stack traces, SQL, file
  paths, or library names. Log the internals server-side with a correlation ID and
  expose the ID as an extension (`"trace_id": "…"`).
- Use the same shape for every error in the API — consistency is the feature.

## Caching and conditional requests

- Every response carries explicit `Cache-Control`. Defaults differ by class:
  - Immutable hashed assets: `public, max-age=31536000, immutable`
  - Public semi-static API data: `public, max-age=60, stale-while-revalidate=300`
  - Per-user data: `private, no-store` (or `private, max-age=0, must-revalidate`
    + ETag if revalidation is wanted)
- ETag flow: server sends `ETag: "v42"`; client revalidates with
  `If-None-Match: "v42"`; server replies 304 (empty body) when unchanged. Prefer ETag
  over `Last-Modified` (sub-second precision, content-derived).
- Optimistic concurrency: require `If-Match: "v42"` on PUT/PATCH; reply
  `412 Precondition Failed` when stale — prevents lost updates.
- `Vary` on every request header that changes the representation
  (`Accept`, `Accept-Language`, `Origin` for CORS responses). Wrong `Vary` poisons
  shared caches — including serving one user's cached response to another.

## Reliability conventions

- Idempotency: PUT/DELETE are idempotent by design; for POSTs that must not double-fire
  (payments, bookings), accept an `Idempotency-Key` header and replay the stored
  response for retries.
- Rate limiting: return 429 + `Retry-After`; document limits via
  `RateLimit-*` headers.
- Timeouts/retries are client contracts: document which operations are safe to retry.
- CORS: allowlist exact origins; never reflect arbitrary `Origin` with
  `Access-Control-Allow-Credentials: true`.
