# Data Fetching and State — Detailed Patterns

Companion to SKILL.md §8–§10. Load when implementing the data layer or a global store.

## 1. TanStack Query v5 Idioms

```tsx
// Query options factory — single source of truth for key + fn, reusable
// across useQuery, prefetching, and loaders.
import { queryOptions } from '@tanstack/react-query';

export const postQueries = {
  detail: (id: string) =>
    queryOptions({
      queryKey: ['posts', id],
      queryFn: () => fetchPost(id),
      staleTime: 60_000,
    }),
};

function Post({ id }: { id: string }) {
  const { data } = useSuspenseQuery(postQueries.detail(id)); // data is non-undefined
  return <article>{data.title}</article>;
}
```

- Prefer `useSuspenseQuery` + a `<Suspense>`/error boundary over `isLoading`/`isError`
  branching when the route shell already provides boundaries.
- Set a sensible `staleTime` (default 0 means refetch-on-mount/focus everywhere);
  most apps want 30s–5min for read-heavy data.
- Mutations: invalidate by key prefix on success; use `onMutate` rollback pattern (or
  React 19 `useOptimistic` in form-action flows) for optimistic UI.
- Treat the Query cache as the single owner of server data. Selecting/transforming:
  use the `select` option, not a copy in `useState`/`useEffect`.

## 2. Hybrid: RSC / Loader Prefetch + Client Hydration

Next.js App Router (server prefetch, stream, hydrate):

```tsx
// app/posts/[id]/page.tsx (server component)
export default async function PostPage({ params }) {
  const queryClient = new QueryClient();
  await queryClient.prefetchQuery(postQueries.detail(params.id));
  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Post id={params.id} /> {/* 'use client'; useSuspenseQuery hits the hydrated cache */}
    </HydrationBoundary>
  );
}
```

TanStack Router (isomorphic loaders seed the cache; Query keeps it fresh):

```tsx
export const Route = createFileRoute('/posts/$id')({
  loader: ({ context: { queryClient }, params }) =>
    queryClient.ensureQueryData(postQueries.detail(params.id)),
  component: Post,
});
```

React Router v7 framework mode: same shape with `loader` + `queryClient.ensureQueryData`,
reading via `useSuspenseQuery` in the component (not `useLoaderData`) so background
refetching still works.

Guidance:
- Loaders should `ensureQueryData`/`prefetchQuery`, not return raw fetch results that
  bypass the cache.
- Don't `await` non-critical prefetches in RSC — kick them off and let Suspense stream.
- A `QueryClient` on the server must be created per-request (never module-level —
  cross-request data leaks).

## 3. When You Don't Need TanStack Query

- All data is fetched in Server Components and mutated through Server Functions with
  framework-level revalidation (`revalidatePath`/`revalidateTag` in Next.js): the
  framework is your cache; adding Query is redundant complexity.
- One-shot static data in a small SPA: a loader alone may be enough.
- Add Query when you need: background refetch/focus refetch, optimistic mutations with
  rollback, infinite scroll, polling, offline/retry, or shared cache across routes.

## 4. Zustand Patterns

```ts
import { create } from 'zustand';

interface UiStore {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiStore>()((set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));

// GOOD — select the slice you use; component re-renders only when it changes
const open = useUiStore((s) => s.sidebarOpen);

// BAD — subscribes to the whole store; re-renders on every change
const { sidebarOpen } = useUiStore();
```

- Keep stores small and per-domain (uiStore, cartStore) — not one app-wide blob.
- Actions live inside the store; components never `setState` store internals directly.
- Never mirror TanStack Query data into a store.
- SSR/RSC caveat: module-level stores are shared across requests on the server — in
  Next.js, create the store per-request and provide it via context (see Zustand's
  Next.js guide).

## 5. Jotai Patterns

```ts
const searchAtom = atom('');
const filtersAtom = atom<Filters>({ status: 'all' });
const visibleItemsAtom = atom((get) =>
  applyFilters(get(itemsAtom), get(searchAtom), get(filtersAtom)),
); // derived atom — recomputes only when inputs change
```

Choose Jotai over Zustand when state is many small independent values with derivations
(filter panels, canvas/editor state); choose Zustand when state is a few cohesive slices
with imperative actions.

## 6. URL State

Filters, sort, pagination, active tab, open-modal-id: put them in search params so views
are linkable and survive reload. Use the router's typed search-param APIs (TanStack
Router validates/types them) or `useSearchParams`; in Next.js consider `nuqs`. URL state
needs no store, no context, no Query.
