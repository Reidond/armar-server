---
name: react-best-practices
description: >
  React-specific best practices for the React 19+ era (React Compiler, Actions,
  Server Components, modern data fetching and state management). Defines what
  React 19 obsoletes (forwardRef, manual useMemo/useCallback, hand-rolled form
  state), effects discipline, 'use client' boundary placement, Server Function
  security, state-management decision ladders, and Testing Library norms.
  Auto-loads as background knowledge when writing or reviewing React components,
  hooks, JSX/TSX, or frontend code. Keywords: React, hooks, useEffect, useState,
  Server Components, RSC, Next.js, Vite, TanStack Query, Zustand, component
  design, re-render, memoization, React Testing Library.
user-invocable: false
metadata:
  type: reference
---

# React Best Practices (React 19+ Era)

## Role

Background knowledge for writing and reviewing React code. Current as of June 2026:
React 19.2.x, React Compiler 1.0 stable, Create React App sunset, framework-first
official guidance. The primary job of this skill is overriding stale pre-2024 defaults.

Scope: React-specific practices only. General TypeScript practices belong to
`typescript-best-practices`; framework-agnostic accessibility/CSS/security belong to
`web-dev-best-practices`.

## When This Skill Activates

- Writing or modifying React components, hooks, or JSX/TSX files
- Reviewing frontend code that uses React
- Choosing frontend architecture (framework, data fetching, state management)

---

## 1. React 19 Baseline: Do Not Emit Obsolete Patterns

These patterns are obsolete in React 19+. Never write them in new code; flag them in review:

| Obsolete | Replacement |
|---|---|
| `forwardRef(...)` | `ref` is a normal prop: `function Input({ ref, ...props })` |
| `<MyContext.Provider value={...}>` | `<MyContext value={...}>` |
| `ReactDOM.useFormState` | `useActionState` |
| Hand-rolled `isSubmitting`/`error` state for forms | Actions + `useActionState` / `useFormStatus` (§4) |
| Reflexive `useMemo`/`useCallback`/`memo` | React Compiler (§2) |
| `useEffect` data fetching | RSC / route loaders / TanStack Query (§8) |
| "Latest ref" pattern for effect callbacks | `useEffectEvent` (§12, stable since 19.2) |
| Create React App | Framework or Vite (§17) |
| Class components, HOCs, render props for logic reuse | Function components + custom hooks |

## 2. React Compiler: Trust It, Don't Hand-Memoize

The React Compiler (stable 1.0, Oct 2025) auto-memoizes components and hooks at build
time. It supports React 17/18/19 via Babel/Vite/Rsbuild/Metro plugins and a Next.js flag.

- **New projects**: enable the compiler; write plain code without `useMemo`/`useCallback`/`memo`.
- **Existing code**: do NOT bulk-delete existing memoization — removal can change compiled
  output; remove incrementally with profiling.
- **Still legitimate**: memoizing for non-React consumers (library interop needing
  reference identity), expensive *standalone* functions (compiler only memoizes
  components/hooks), and measured cases where compiler heuristics fall short.
- The compiler requires Rules of React compliance — `eslint-plugin-react-hooks` v6
  (with compiler-powered rules) is the lint baseline.

```jsx
// GOOD (compiler enabled) — plain code, compiler memoizes
function List({ data, onSelect }) {
  const sorted = expensiveSort(data);
  return sorted.map(item => <Row key={item.id} item={item} onClick={() => onSelect(item.id)} />);
}

// BAD — reflexive manual memoization noise in new code
function List({ data, onSelect }) {
  const sorted = useMemo(() => expensiveSort(data), [data]);
  const handle = useCallback(id => onSelect(id), [onSelect]);
  ...
}
```

Without the compiler (legacy setup), manual memoization remains valid — but only where
profiling shows it matters.

## 3. Effects Discipline: You Might Not Need an Effect

The highest-frequency React mistake category. An Effect is ONLY for synchronizing with
a system *outside* React (subscriptions, browser APIs, non-React widgets). Before writing
`useEffect`, check these in order:

1. **Derived data?** Compute during render. Never `useEffect` + `setState` to transform
   props/state.
2. **Responding to a user event?** Put the logic in the event handler, not in an effect
   watching a state flag.
3. **Resetting state when a prop changes?** Use a `key` to remount, not an effect.
4. **Fetching data?** Use the data layer (§8), not a hand-rolled effect.
5. **Notifying a parent / chaining state?** Restructure: one event handler updates
   everything. Effect chains (effect sets state → triggers next effect) cause render
   cascades and bugs.

```jsx
// GOOD — derived during render; reset via key
function Profile({ user }) {
  const fullName = `${user.first} ${user.last}`;       // derive, don't store
  return <ProfileForm key={user.id} user={user} />;     // key resets form state per user
}

// BAD — effect-as-derivation and effect-as-reset
function Profile({ user }) {
  const [fullName, setFullName] = useState('');
  const [draft, setDraft] = useState('');
  useEffect(() => { setFullName(`${user.first} ${user.last}`); }, [user]);
  useEffect(() => { setDraft(''); }, [user.id]);  // reset-on-prop-change anti-pattern
}
```

For legitimate effects: include all reactive dependencies honestly (never silence the
linter), always return cleanup for subscriptions/connections, and split unrelated
concerns into separate effects.

## 4. Forms and Mutations: Use Actions

React 19 Actions handle pending/error/optimistic state. Pass an async function to
`<form action={...}>` or wrap with `useActionState`:

```jsx
// GOOD
function Rename({ save }) {
  const [error, submitAction, isPending] = useActionState(
    async (prev, formData) => {
      const err = await save(formData.get('name'));
      return err ?? null;
    }, null);
  return (
    <form action={submitAction}>
      <input name="name" />
      <button disabled={isPending}>Save</button>
      {error && <p>{error}</p>}
    </form>
  );
}

// BAD — hand-rolled submit state (pre-19 pattern)
const [isPending, setIsPending] = useState(false);
const [error, setError] = useState(null);
const handleSubmit = async (e) => { e.preventDefault(); setIsPending(true); ... };
```

- `useFormStatus` gives descendants (e.g. a shared `SubmitButton`) pending state without
  prop drilling.
- `useOptimistic` shows the expected result immediately and reverts to the actual state
  when the action settles (so a failed action discards the optimistic value).
- After a *successful* action, React resets the form's uncontrolled fields; on a failed
  action (thrown or returned error) user input is preserved for correction.
- For mutations needing client-cache invalidation across views, prefer TanStack Query
  mutations (§8) — Actions and Query mutations solve overlapping problems; don't stack
  both on one form.

## 5. `use()` for Promises and Context

`use(promise)` suspends on a promise during render; `use(context)` reads context and —
unlike `useContext` — is allowed inside conditionals and loops.

- Pass promises **from Server Components to client components** and read them with
  `use()` inside a `<Suspense>` boundary.
- Do NOT create the promise during a client render (re-created every render → infinite
  suspense loops). Promises must come from a server component, a loader, or a cache.

## 6. Server vs Client Components: Boundary Mental Model

`'use client'` does NOT mean "renders only in the browser" — client components still SSR.
It marks a **bundle boundary**: this module and everything it imports ships to the client.
Server Components run only on the server, cost zero bundle bytes, and may be `async` and
fetch directly. Mental model: a server component is "just another framework loader."

Rules:
- **Server by default; client at the leaves.** When one button needs interactivity,
  extract the button into a small `'use client'` component — never mark the page/layout.
- Server components can render client components and pass serializable props (plus JSX
  `children` — which lets server-rendered content nest inside client wrappers).
- Client components cannot import server components — compose via `children` instead.
- No hooks-with-state, browser APIs, or event handlers in server components.

```jsx
// GOOD — page stays server; only the leaf is client
// page.jsx (server)
export default async function ProductPage({ params }) {
  const product = await db.products.get(params.id);   // direct data access
  return <><ProductDetails product={product} /><AddToCartButton id={product.id} /></>;
}
// add-to-cart-button.jsx
'use client';
export function AddToCartButton({ id }) { ... onClick ... }

// BAD — 'use client' at the top of the page because one handler errored
'use client';
export default function ProductPage() { ... entire tree now ships to client ... }
```

This applies in RSC frameworks (Next.js App Router, etc.). In a Vite SPA there are no
server components — see §8 and §17.

## 7. Server Functions Are Public Endpoints

Every `'use server'` function compiles to an **unauthenticated public HTTP endpoint**.
TypeScript types are erased — attackers can call it with any payload, bypassing page-level
guards. (Dec 2025 RSC CVEs made this concrete; keep React patched.)

In EVERY Server Function:
1. Validate inputs at runtime (e.g. zod) — never trust typed arguments.
2. Authenticate and authorize *inside the function* — a check in the page does not
   protect the action; verify ownership of any user-supplied ID.
3. Never close over secrets in inline actions; return sanitized errors only.

```ts
// GOOD
'use server';
export async function deletePost(formData: FormData) {
  const { id } = schema.parse({ id: formData.get('id') });
  const user = await getSession();
  if (!user || !(await ownsPost(user.id, id))) throw new Error('Forbidden');
  await db.posts.delete(id);
}

// BAD — trusts types and page-level auth
'use server';
export async function deletePost(id: string) { await db.posts.delete(id); }
```

## 8. Data Fetching Ladder

Never fetch with hand-rolled `useEffect` (races, no cache, waterfalls). Choose by context:

| Context | Initial route data | Client-interactive data |
|---|---|---|
| RSC framework (Next.js App Router) | Server Components / server `fetch` | TanStack Query in client components |
| Vite SPA / framework-mode router | Route loaders (React Router / TanStack Router) | TanStack Query |

- **Loaders/RSC** own render-blocking initial data — fetch-before-render eliminates
  waterfalls.
- **TanStack Query** owns *client async state*: background refetch, optimistic mutations,
  pagination/infinite scroll, dedupe, polling. If data is fetched exclusively on the
  server and never revalidated client-side, you don't need Query (TkDodo's rule).
- Hybrid norm: prefetch on the server / in the loader, hydrate the QueryClient, then
  `useSuspenseQuery` in components — loader gets data early, Query keeps it fresh.
- Never copy fetched data into `useState`/Zustand/Redux "to use it" — the Query cache
  (or RSC payload) is the source of truth; copying creates manual-sync bugs.

Setup details: [references/data-fetching-and-state.md](references/data-fetching-and-state.md).

## 9. State Management Decision Ladder

Work top-down; stop at the first match. Reaching for a global store is the last step:

1. **Server data** → TanStack Query / RSC (§8). Not a client store.
2. **Form state** → form actions (§4) or react-hook-form for complex client validation.
3. **Sharable via URL** (filters, tabs, pagination) → URL search params.
4. **Local to one component/subtree** → `useState` / `useReducer`; lift only as far as needed.
5. **Read-mostly app-wide values** (theme, locale, current user) → Context.
6. **Shared, frequently-updated client state** → Zustand (~3KB, selector subscriptions).
7. **Many independent fine-grained pieces** → Jotai (atomic model).
8. **Large team needing enforced architecture/devtools** → Redux Toolkit (rarely justified for new apps).

Most state is over-globalized. `useState` colocated with its UI is the correct default,
and most "we need Redux" cases dissolve once server data moves to Query.

## 10. Context Discipline

Context is dependency injection, not a state manager. Every consumer re-renders on every
value change.

- Use for low-frequency values (theme, auth identity, compound-component wiring).
- Stabilize the provider `value` object (the React Compiler does this automatically in
  compiled code; only hand-`useMemo` it in non-compiler setups); split frequently-changing
  values into separate contexts; split state and dispatch contexts.
- High-frequency shared state in Context → move to Zustand/Jotai (selector-based
  subscriptions re-render only actual users).

## 11. Component Design

- **Composition over configuration**: when a component sprouts boolean props
  (`showIcon`, `isCompact`, `withFooter`...), replace variants with composed `children` /
  slot props or compound components (`<Tabs><Tabs.List/><Tabs.Panel/></Tabs>`,
  context-backed).
- **Custom hooks** are the logic-reuse primitive — extract any non-trivial stateful logic
  (`useDebounce`, `usePagination`) instead of render props/HOCs.
- **Never define a component inside another component** — it remounts on every parent
  render, destroying state. Define at module top level; pass data via props.
- Prefer passing `children`/JSX over prop drilling through layers; Context only when
  composition can't reach (§10).
- Keep components presentational where possible; isolate data access at route/feature
  boundaries.

## 12. `useEffectEvent` (Stable Since 19.2)

Extracts *event-like* logic from effects so non-essential reactive values don't retrigger
the effect:

```jsx
function ChatRoom({ roomId, theme }) {
  const onConnected = useEffectEvent(() => showNotification('Connected!', theme));
  useEffect(() => {
    const conn = createConnection(roomId);
    conn.on('connected', () => onConnected());
    conn.connect();
    return () => conn.disconnect();
  }, [roomId]); // theme changes no longer reconnect the chat
}
```

Hard rules: never list an effect event in a dependency array; only call it from effects;
declare it next to the effect that uses it; do not pass it to other components/hooks.
It is NOT a license to silence the exhaustive-deps linter for genuinely reactive values.

## 13. Keys and List Rendering

- `key` must be a **stable identity** (database ID). Array index is acceptable ONLY for
  static, never-reordered, never-filtered lists; otherwise it misassociates state and
  DOM across reorders/insertions.
- Never generate keys at render time (`key={Math.random()}`, `key={crypto.randomUUID()}`)
  — forces full remount every render.
- `key` doubles as the intentional state-reset tool (§3).

## 14. Performance

Order of operations: measure first (React DevTools Profiler; React 19.2 Performance
Tracks in Chrome DevTools), then fix. React-specific levers, in priority order:

1. Eliminate unnecessary renders structurally: colocate state down; lift content up
   (pass `children` so the stateful wrapper doesn't re-render them).
2. Enable the React Compiler (§2) before any manual memoization campaign.
3. Mark non-urgent updates with `useTransition`/`useDeferredValue` (typing, filtering
   large lists) instead of debounce hacks.
4. Use `<Suspense>` boundaries for progressive loading; `<Activity mode="hidden">`
   (19.2) to keep off-screen views (tabs, back-stack) warm instead of CSS-hiding or
   unmount/remount.
5. Virtualize long lists (TanStack Virtual) — memoization doesn't fix 10k DOM nodes.

## 15. Testing React Components

Testing Library + `user-event` on Vitest (the 2026 default runner; Jest remains fine in
legacy suites). Core principle: test what the user sees and does, never implementation
details (state values, instance methods, re-render counts).

- Query priority: `getByRole` (with accessible name) > `getByLabelText` >
  `getByPlaceholderText`/`getByText` > `getByTestId` (last resort).
- Use `screen.getBy...`, not destructured `render` results or `container.querySelector`.
- Use `await user.click(...)` (`userEvent.setup()`) — not `fireEvent` — to simulate real
  interaction sequences.
- `findBy*` / `waitFor` for async UI; never wrap in manual `act()` (RTL already does);
  never `waitFor` with side effects inside the callback.
- Mock at the network boundary (MSW) rather than mocking your own hooks/components.
- Lint baseline: `eslint-plugin-testing-library`, `eslint-plugin-jest-dom`.

Extended patterns and examples: [references/testing-react.md](references/testing-react.md).

## 16. Anti-Pattern Review Checklist

When reviewing React code, scan for these (all detailed above):

effect-for-derived-state · effect chains · effect-as-event-handler · useEffect fetching ·
effect-based prop reset (use `key`) · index/random keys · `'use client'` above the leaves ·
unvalidated Server Functions · Context for hot state · server data copied into client
stores · reflexive memoization under the compiler · `forwardRef` in new code · components
defined inside components · boolean-prop proliferation · `useState` mirroring props ·
hand-rolled form pending/error state · conditional or looped hooks · implementation-detail
tests / `fireEvent` / `container` queries.

## 17. Project Setup Defaults (2026)

CRA is dead (sunset Feb 2025). Official guidance is framework-first:

| Situation | Default |
|---|---|
| Full-stack app, public-facing pages, SEO, RSC benefits | Next.js (App Router) |
| Full-stack with web-standards lean / existing RR codebase | React Router v7 (framework mode) |
| SPA: dashboards, admin panels, internal tools | Vite + TanStack Router or React Router + TanStack Query |
| Type-safe full-stack on TanStack primitives (newer, smaller ecosystem) | TanStack Start |
| Native mobile | Expo |

Baseline for any choice: React 19.2+, React Compiler enabled, `eslint-plugin-react-hooks`
v6, Vitest + Testing Library, StrictMode on in development (it intentionally double-invokes
renders/effects to surface impure code — never "fix" by removing it).

## Additional Resources

- [references/data-fetching-and-state.md](references/data-fetching-and-state.md) —
  Query+RSC hydration setup, Query v5 idioms, Zustand/Jotai usage patterns.
- [references/testing-react.md](references/testing-react.md) — full RTL example suite,
  async patterns, MSW setup, common-mistake catalog.
