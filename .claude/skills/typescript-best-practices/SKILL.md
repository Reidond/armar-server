---
name: typescript-best-practices
description: >
  Expert TypeScript conventions current as of mid-2026: strictness configuration
  (strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes, verbatimModuleSyntax),
  type design (discriminated unions, branded types, unknown over any, satisfies, const
  assertions), generics discipline, runtime validation at boundaries (zod/valibot),
  error handling, ESM/module resolution, project references, the TypeScript 6.0/7.0
  (native tsgo) transition, typed linting with typescript-eslint, and anti-patterns
  (any leakage, as-casting, enum pitfalls). Auto-loads as background knowledge when
  writing or reviewing TypeScript code or configuring tsconfig. Does NOT cover React
  patterns (see react-best-practices) or general web platform concerns (see
  web-dev-best-practices).
user-invocable: false
metadata:
  type: reference
---

# TypeScript Best Practices (mid-2026)

## Role

Background knowledge for writing, reviewing, and configuring TypeScript in this project.
Calibrated for an AI coding agent: every rule states the rationale and, where mistakes
are common, a GOOD/BAD pair. Sourced from official TypeScript 6.0/7.0 release notes,
the TSConfig reference, typescript-eslint docs, Node.js docs, and Total TypeScript
(research brief: `.specs/skill-typescript-best-practices/research-brief.md`).

## When This Skill Activates

- Writing or modifying any `.ts`/`.mts`/`.cts` file
- Creating or editing `tsconfig.json` / ESLint config for TypeScript
- Reviewing TypeScript code or type design
- NOT for React component patterns or browser/web-platform APIs (sibling skills own those)

---

## 1. Know the 2026 Compiler Landscape Before Trusting Training Data

State as of June 2026 — re-verify if much time has passed:

- **TypeScript 6.0** (stable, March 2026) is the last JS-based release. It changed
  defaults: `strict: true`, `module: esnext`, `target` = current-year ES, `types: []`
  (no auto `@types` enumeration), `rootDir` = tsconfig directory. It deprecated
  `target: es5`, `moduleResolution: node`/`classic`, `module: amd|umd|system|none`,
  `baseUrl`, `outFile`, `downlevelIteration`, and import assertions (`assert` → `with`).
- **TypeScript 7.0** (beta April 2026, stable expected mid-2026) is the native Go port
  ("Corsa", `microsoft/typescript-go`), ~10x faster. Type checking is structurally
  identical to 6.0; `--build`, `--incremental`, and project references work. Beta ships
  as `@typescript/native-preview` with the `tsgo` CLI; stable reclaims `typescript`/`tsc`.
  Legacy TS Server plugins do not work (LSP architecture); stable programmatic API lands ≥7.1.
- **Practical rule**: code and config that are clean on 6.0 with zero deprecated options
  ARE TypeScript 7 compatible. Never write "tsgo-specific" code; never introduce
  deprecated options (`baseUrl`, node10 resolution, es5 target) into new configs.
- **Node 24 LTS runs `.ts` files directly** via type stripping — but only *erasable*
  syntax: no enums, no namespaces with values, no parameter properties, no legacy
  decorators (see §9, §3).

## 2. Strictness: `strict: true` Is the Floor, Not the Ceiling

`strict` does NOT include several high-value checks. New tsconfigs must add them:

```jsonc
{
  "compilerOptions": {
    "strict": true,                       // implied default since TS 6.0, keep explicit
    "noUncheckedIndexedAccess": true,     // arr[i] is T | undefined — kills OOB bugs
    "exactOptionalPropertyTypes": true,   // {x?: T} no longer accepts explicit undefined
    "noImplicitOverride": true,           // require `override` keyword
    "verbatimModuleSyntax": true,         // forces import type / export type
    "isolatedModules": true,
    "moduleDetection": "force",
    "skipLibCheck": true
  }
}
```

Adoption caveats (judgment, not dogma):
- `exactOptionalPropertyTypes` is painful on codebases/deps that assign `undefined` to
  optional props. Greenfield: enable. Retrofit: enable last, fix incrementally.
  With it on, distinguish "absent" (`delete` / omit) from "present-but-undefined"
  (`prop: T | undefined`).
- `noUncheckedIndexedAccess` handling — narrow, don't assert:

```ts
// GOOD
const first = items[0];
if (first !== undefined) use(first);
for (const item of items) use(item);      // iteration needs no check

// BAD
use(items[0]!);                            // non-null assertion = unchecked OOB again
```

## 3. Pick Module Config by Emit Strategy (Three Valid Setups)

There is no single correct `module` setting — it follows who consumes the output:

| Strategy | Settings | Use when |
|---|---|---|
| **tsc emits** | `module: "nodenext"`, `outDir`, real `.js` extensions in relative imports | Libraries, plain Node services |
| **Bundler emits** | `module: "preserve"`, `noEmit: true` | Apps built by Vite/esbuild/Rollup/etc. |
| **Node runs .ts directly** | `module: "nodenext"`, `noEmit: true`, `erasableSyntaxOnly: true`, `rewriteRelativeImportExtensions: true` | Node ≥24 scripts/services without a build step |

Never: `moduleResolution: "node"` (node10), `baseUrl` for aliases (use `paths` with
prefixes, or `#/` subpath imports from package.json `imports`), `module: "commonjs"` for
new code without a documented reason. Full annotated configs (incl. library/declaration
settings): [references/tsconfig-and-monorepo.md](references/tsconfig-and-monorepo.md).

## 4. `unknown` Over `any`; Contain Unavoidable `any`

Every operation on `any` returns `any` — one `any` in an exported signature infects all
call sites and disables checking transitively. `unknown` is the correct type for
"I don't know yet": it forces narrowing before use.

```ts
// GOOD
function handle(payload: unknown): Order {
  return orderSchema.parse(payload);       // narrow via validation (§11) or type guards
}

// BAD
function handle(payload: any): Order {
  return payload;                          // compiles, lies
}
```

If `any` is genuinely needed (rare: interop guts, complex generic internals), keep it
inside a function body with a well-typed signature and never export it. typescript-eslint's
`no-unsafe-*` rules (§14) catch leakage mechanically.

## 5. `as` Is an Override, `satisfies` Is a Check — Prefer the Check

`as` tells the checker to stop checking; refactors then break silently. The double
assertion `as unknown as T` is a code-review red flag. `satisfies` validates against a
type while *keeping the narrower inferred type*; `as const` narrows to literals.

```ts
// GOOD — checked, and config.endpoints.health stays a known literal key
const config = {
  retries: 3,
  endpoints: { health: "/health" },
} satisfies AppConfig;

// BAD — annotation widens (loses literal keys)…
const config: AppConfig = { retries: 3, endpoints: { health: "/health" } };
// …and `as` doesn't even check:
const config2 = { retris: 3 } as AppConfig;   // typo compiles
```

Legitimate `as`: `as const`, narrowing to a literal-union member immediately after a
runtime check, test fixtures intentionally violating types. Anything else: fix the type,
write a type guard, or parse at the boundary (§11).

## 6. Model State as Discriminated Unions; Make Invalid States Unrepresentable

Tag variants with a literal field and switch exhaustively. Optional-field "bag" types
permit impossible combinations the compiler can't reject.

```ts
// GOOD
type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: RiskReport }
  | { status: "error"; error: AppError };

function render(s: FetchState) {
  switch (s.status) {
    case "idle": case "loading": return spinner();
    case "success": return show(s.data);     // data only exists here
    case "error": return alert(s.error);
    default: { const _exhaustive: never = s; return _exhaustive; } // new variant = compile error
  }
}

// BAD — allows loading && data && error simultaneously
type FetchState = { loading: boolean; data?: RiskReport; error?: AppError };
```

## 7. Brand Domain Primitives That Must Not Cross

Two same-shaped strings (userId vs tripId) are interchangeable to the structural type
system. Brand them when transposition is a real risk (IDs, currency amounts, sanitized
strings, units). Don't brand every string — it's ceremony with a cost.

```ts
declare const brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [brand]: B };

type UserId = Brand<string, "UserId">;
type TripId = Brand<string, "TripId">;
const asUserId = (s: string): UserId => s as UserId;  // one blessed cast at the boundary

assignTrip(tripId, userId);   // GOOD: swapping arguments is now a compile error
```

## 8. type vs interface: Default `type`, Use `interface` Deliberately

The TS team says "personal preference, default interface"; the stronger community
position (Pocock): default `type`, because `interface` declaration merging silently
merges same-name declarations — a footgun unless you want it. Use `interface` for:
object hierarchies via `extends` (better cached by the checker than repeated
intersections) and intentional declaration merging (module augmentation). Whichever
default you pick, be consistent within the codebase. `type` is mandatory anyway for
unions, intersections, mapped/conditional types, and branded types.

## 9. Prefer `as const` Objects to Enums (Erasability Is the Forcing Function)

Enums are non-erasable syntax: they break Node 24 type stripping and error under
`erasableSyntaxOnly`. Numeric enums additionally emit IIFEs and historically accepted
arbitrary numbers. The 2026 default replacement:

```ts
// GOOD
const RiskLevel = {
  Low: "low",
  High: "high",
} as const;
type RiskLevel = (typeof RiskLevel)[keyof typeof RiskLevel];  // "low" | "high"

// Also fine for simple cases — plain literal union:
type RiskLevel = "low" | "high";

// BAD (new code)
enum RiskLevel { Low, High }     // numeric, IIFE, non-erasable
```

Nuance: don't blind-replace existing enums in a published API — enum members are part of
the public runtime contract. String enums in legacy code are tolerable; just don't add new ones.

## 10. Generics Discipline: A Type Parameter Must Earn Its Place

A type parameter is justified only if it *relates* two or more positions (input↔input,
input↔output). Ask "would a concrete type or `unknown` work?" — if yes, skip the generic.

```ts
// GOOD — T links input to output
function firstOrNull<T>(xs: readonly T[]): T | null { return xs[0] ?? null; }

// BAD — return-only generic: a disguised `as` cast, caller invents T with no evidence
function getConfig<T>(key: string): T { return store[key] as T; }
// Instead: return unknown and parse (§11), or type the store properly.
```

Same discipline for conditional/mapped types: use the simplest type that preserves the
information you need. A three-level conditional type that a discriminated union or two
overloads would replace is a maintenance liability and slows the checker. Reach for
advanced type-level programming only when it eliminates real duplication or unsafe casts.

## 11. Types Are Erased — Parse at Trust Boundaries, Schema-First

Annotations provide zero runtime protection. Everything crossing a trust boundary —
HTTP requests/responses, env vars, DB rows, file/JSON input, **LLM output** — must be
validated at runtime. Define the schema once and *derive* the static type, so the two
cannot drift:

```ts
// GOOD — single source of truth
import { z } from "zod";
const orderSchema = z.object({ id: z.string(), total: z.number().nonnegative() });
type Order = z.infer<typeof orderSchema>;
const order = orderSchema.parse(await res.json());   // typed AND verified

// BAD — hand-written twin interface drifts from reality
interface Order { id: string; total: number }
const order = (await res.json()) as Order;           // hope-driven development
```

Library choice (2026): **Zod 4** for server/Node/tRPC (deepest ecosystem, 6–14x faster
parsing than Zod 3); **Valibot** when bundle size dominates (edge/client, ~90% smaller); ArkType if
raw parse speed is the constraint. Do NOT validate internal function-to-function calls
already guaranteed by the type system — that's noise, not safety.

## 12. Error Handling: `unknown` Catches, `Error` Subclasses, Result for Expected Failures

- `catch` variables are `unknown` under `strict` (`useUnknownInCatchVariables`). Never
  annotate `catch (e: Error)`; narrow instead.
- Always throw `Error` (or subclasses) — never strings/objects (loses stack traces).
  Use `cause` to chain context. Custom error classes give `instanceof` narrowing.
- TypeScript has no `throws` clause — signatures can't advertise exceptions. For
  *expected* domain failures (validation, not-found, business rules), prefer returning a
  Result-style discriminated union so the failure is in the signature; keep `throw` for
  truly exceptional/programmer-error paths. This is a calibrated choice — pick one
  convention per layer and stay consistent.

```ts
// GOOD
class GeoLookupError extends Error {
  constructor(msg: string, opts?: { cause?: unknown }) { super(msg, opts); this.name = "GeoLookupError"; }
}
try { await lookup(place); }
catch (e) {
  if (e instanceof GeoLookupError) return fallback(place);
  throw e;                                   // don't swallow unknown errors
}

// GOOD — expected failure in the signature
type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };
function parseCoords(raw: string): Result<Coords, "malformed"> { /* ... */ }

// BAD
catch (e: any) { log(e.message); }           // e might not be an Error; any leaks
throw "lookup failed";                        // no stack, can't instanceof
```

## 13. `@ts-expect-error` Over `@ts-ignore`, Always With a Reason

`@ts-ignore` rots: when the underlying error is fixed, the suppression stays, masking the
next real error on that line. `@ts-expect-error` errors when unused, so it self-cleans.
Always append a description (typescript-eslint `ban-ts-comment` enforces ≥ a minimum length).

```ts
// GOOD
// @ts-expect-error — fixture intentionally omits required field to test validator
const bad = makeOrder({});

// BAD
// @ts-ignore
const bad = makeOrder({});
```

## 14. Lint With Type Information

Untyped linting misses the highest-value rule class. Use typescript-eslint v8+ flat
config with the type-checked presets and `projectService`:

```js
// eslint.config.js
import tseslint from "typescript-eslint";
export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,     // or recommendedTypeChecked for mixed teams
  ...tseslint.configs.stylisticTypeChecked,
  { languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } } },
);
```

Non-negotiable rules for async-heavy code: `no-floating-promises`, `no-misused-promises`,
the `no-unsafe-*` family (catches §4 `any` leakage mechanically), `ban-ts-comment`.
`projectService: true` (not manual `project` arrays) is the v8+ recommended setup.

## 15. Monorepos: Project References at ≥2 Shared Packages

A single app needs none of this. Once ≥2 packages share code: per-package
`composite: true` + `declaration` + `declarationMap` + `incremental`; a root solution
tsconfig listing `references`; build with `tsc -b` (fully supported by tsgo); pair with
pnpm workspaces for package linking. Whether to *build* shared packages or ship source
depends on whether a downstream bundler owns the deploy path. Full wiring and annotated
configs: [references/tsconfig-and-monorepo.md](references/tsconfig-and-monorepo.md).

## 16. Anti-Pattern Quick Reference (Review Checklist)

| Anti-pattern | Why it harms | Instead |
|---|---|---|
| `any` in exported signature | Disables checking at every call site | `unknown` + narrow (§4) |
| `as T` / `as unknown as T` to silence errors | Hides real mismatches; silent refactor breakage | `satisfies`, type guard, parse (§5, §11) |
| Return-type-only generic `<T>(): T` | Disguised cast | `unknown` + parse (§10) |
| New `enum` (esp. numeric) | Non-erasable; breaks Node type stripping | `as const` object / literal union (§9) |
| Hand-written type twin of a validator (or no validator) at a boundary | Type/runtime drift | Schema-first, `z.infer` (§11) |
| `catch (e: any)` / throwing strings | Unsafe access; lost stacks | `unknown` + `instanceof`; `Error` with `cause` (§12) |
| `@ts-ignore` | Rots silently | `@ts-expect-error` + reason (§13) |
| Optional-field state bags | Invalid state combinations compile | Discriminated union (§6) |
| Bare `string`/`number` IDs crossing domain boundaries | Transposed arguments compile | Branded types where transposition is a real risk (§7) |
| Deep conditional types where a union/overload suffices | Unreadable, slow checker | Simplest type that preserves info (§10) |
| `baseUrl` / node10 resolution / `es5` target / `outFile` in new configs | Deprecated in 6.0, removed in 7.0 | §3 emit strategies |
| ESLint without typed rules | Misses floating promises, `any` leakage | `strictTypeChecked` + `projectService` (§14) |
| `arr[i]!` to dodge `noUncheckedIndexedAccess` | Reintroduces OOB bugs | Narrow or iterate (§2) |

## Additional Resources

- Full annotated tsconfig per emit strategy, library/declaration settings, TS 6.0
  deprecation list, monorepo wiring, and TS 7/tsgo migration notes:
  [references/tsconfig-and-monorepo.md](references/tsconfig-and-monorepo.md)
- Research brief with sources: `.specs/skill-typescript-best-practices/research-brief.md`
