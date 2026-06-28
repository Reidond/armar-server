# tsconfig Emit Strategies, Monorepo Wiring, and the TS 6→7 Transition

Detailed companion to `typescript-best-practices` SKILL.md §1, §3, §15.
Current as of June 2026 (TypeScript 6.0 stable; 7.0 beta).

## 1. Shared Base Options (All Projects)

```jsonc
// tsconfig.base.json — applies to every strategy below
{
  "compilerOptions": {
    // Strictness (strict alone is NOT enough — see SKILL.md §2)
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,

    // Module hygiene
    "verbatimModuleSyntax": true,   // forces `import type` / `export type`;
                                    // emitted JS imports match source 1:1
    "isolatedModules": true,        // every file compilable in isolation
                                    // (required by bundlers/strippers)
    "moduleDetection": "force",     // all files are modules; no accidental scripts

    // Pragmatics
    "skipLibCheck": true,           // don't type-check node_modules .d.ts
    "resolveJsonModule": true,
    "target": "es2022",             // pin a concrete year; avoid `esnext` drift.
                                    // TS 6.0 defaults target to current-year ES;
                                    // pinning keeps output stable across TS upgrades.

    // TS 6.0 default changes you must now handle explicitly:
    "types": []                     // 6.0 no longer auto-enumerates @types/*.
                                    // List what you actually use, e.g. ["node"]
  }
}
```

Notes:
- `lib`: add `["es2022", "dom", "dom.iterable"]` only for code that runs in a browser
  (general web-platform guidance belongs to the `web-dev-best-practices` sibling skill).
- `rootDir`: since 6.0 defaults to the tsconfig directory — set `"rootDir": "./src"`
  explicitly when sources are nested, or output paths shift.

## 2. Strategy A — tsc Emits (Libraries, Plain Node Services)

```jsonc
{
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "module": "nodenext",          // implies moduleResolution nodenext
    "rootDir": "./src",
    "outDir": "./dist",
    "sourceMap": true,

    // Libraries only:
    "declaration": true,           // emit .d.ts — consumers need types
    "declarationMap": true         // go-to-definition lands in your source
  }
}
```

Rules under `nodenext`:
- Relative imports require real extensions as they will exist at runtime:
  `import { x } from "./util.js"` (yes, `.js`, even though the source is `.ts`).
- `package.json` needs correct `"type": "module"` (or `.mts`/`.cts` extensions) and
  an `"exports"` map for libraries. Dual CJS/ESM publishing is increasingly NOT worth
  it in 2026 — ship ESM-only unless consumers demonstrably require CJS.

## 3. Strategy B — Bundler Emits (Apps Built by Vite/esbuild/Rollup/Bun)

```jsonc
{
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "module": "preserve",          // mirrors how bundlers treat modules;
                                   // implies moduleResolution "bundler",
                                   // allows extensionless imports
    "noEmit": true                 // the bundler owns emit; tsc only type-checks
  }
}
```

Run `tsc --noEmit` (or `tsgo --noEmit`) in CI as the type gate — bundlers strip types
without checking them.

## 4. Strategy C — Node ≥24 Runs `.ts` Directly (Type Stripping)

Node 24 LTS strips types from `.ts`/`.mts` files by default (amaro; types replaced with
whitespace, so stack-trace line numbers match). Only *erasable* syntax survives.

```jsonc
{
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "module": "nodenext",
    "noEmit": true,
    "erasableSyntaxOnly": true,              // TS 5.8+: error on non-erasable syntax
    "rewriteRelativeImportExtensions": true, // lets you write "./util.ts" in imports
    "allowImportingTsExtensions": true
  }
}
```

Non-erasable syntax that `erasableSyntaxOnly` rejects (and Node throws on):
- `enum` (any kind)
- `namespace` / `module` blocks containing runtime values
- class constructor parameter properties (`constructor(private x: number)`)
- legacy experimental decorators

This config matches the Node.js documentation's recommendation (nodejs.org/api/typescript.html).

## 5. Monorepo: Project References

Use when ≥2 packages share code. A single app gains nothing from this.

Layout:

```
tsconfig.base.json            # shared compilerOptions (section 1)
tsconfig.json                 # solution file: references only, no files
packages/
  core/   tsconfig.json
  api/    tsconfig.json       # depends on core
```

Solution root:

```jsonc
// tsconfig.json
{
  "files": [],
  "references": [{ "path": "./packages/core" }, { "path": "./packages/api" }]
}
```

Per-package:

```jsonc
// packages/core/tsconfig.json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "composite": true,        // required for referenced projects
    "declaration": true,      // references consume .d.ts, not source
    "declarationMap": true,   // cross-package go-to-definition
    "incremental": true,      // .tsbuildinfo caching
    "rootDir": "./src",
    "outDir": "./dist"
  },
  "include": ["src"]
}

// packages/api/tsconfig.json — add:
//   "references": [{ "path": "../core" }]
```

Operational rules:
- Build with `tsc -b` (build mode) — it orders projects by the reference graph and skips
  up-to-date ones. **tsgo/TS 7 fully supports `--build`, `--incremental`, and project
  references**, so this layout is forward-compatible.
- Pair with pnpm workspaces: workspaces handle runtime package linking
  (`"@app/core": "workspace:*"`); references handle type-checking/build ordering.
  You need both; neither replaces the other.
- Path aliases (`paths`) across packages instead of references force whole-repo
  re-checks and break encapsulation — use workspace imports.
- Ship built packages vs. source? Ask whether something downstream already bundles them.
  Bundler-owned deploy path → ship source and let it bundle. Installable/self-contained
  package tree required → build with `tsc -b`.

## 6. TypeScript 6.0 Deprecations (Removed in 7.0)

Never introduce these in new configs; remove them when touching existing ones.
`--ignoreDeprecations: "6.0"` is a temporary escape hatch only.

| Deprecated | Replacement |
|---|---|
| `target: "es5"`, `downlevelIteration` | `target: "es2015"`+ (floor is now ES2015) |
| `moduleResolution: "node"` (node10), `"classic"` | `"nodenext"` or `"bundler"` |
| `module: "amd" \| "umd" \| "system" \| "none"` | `"nodenext"`, `"preserve"`, or `"esnext"` |
| `baseUrl` | prefixed `paths` entries, or package.json `imports` (`#/` subpaths) |
| `outFile` | a bundler (also removed entirely in TS 7) |
| `esModuleInterop: false`, `allowSyntheticDefaultImports: false` | leave both true |
| import assertions `assert { type: "json" }` | import attributes `with { type: "json" }` |
| namespaces via legacy `module` keyword | `namespace` (or better: ES modules) |

Other 6.0 default changes to be aware of: `strict: true`, `module: "esnext"`,
`types: []`, `rootDir` = tsconfig dir, `noUncheckedSideEffectImports: true`.

## 7. TypeScript 7 (tsgo) Status and Migration Notes

- TS 7 = native Go port ("Corsa"), ~10x faster (VS Code repo: 78s → 7.5s full check).
  Type checking is structurally identical to 6.0; 99.6% of the compiler test suite passes.
- Beta: `npm i -D @typescript/native-preview@beta` → `tsgo` CLI. Stable will ship as the
  regular `typescript` package with the `tsc` command. To keep 6.x alongside:
  `npm i -D typescript@npm:@typescript/typescript6`.
- Migration bar: a project that compiles cleanly on 6.0 *without deprecated options*
  works on 7.0. There is no "tsgo dialect".
- Known gaps at beta (verify against current release notes before relying on these):
  - Stable programmatic compiler API deferred to ≥7.1 — tools built on the TS API
    (custom transformers, API-based codegen) need updates.
  - Legacy TS Server plugins do not work; the new architecture is LSP-based
    (a "Corsa API" for plugins is planned).
  - `outFile` removed.
- CI tip during the transition: run `tsgo --noEmit` as the fast type gate; keep `tsc`
  only if you depend on API-based tooling that hasn't migrated.
