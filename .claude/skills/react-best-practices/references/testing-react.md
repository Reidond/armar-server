# Testing React — Extended Patterns

Companion to SKILL.md §15. Load when writing or reviewing React component tests.
Primary sources: Testing Library docs; Kent C. Dodds, "Common mistakes with React
Testing Library".

## 1. Canonical Test Shape (Vitest + RTL + user-event)

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

test('submits the rename form', async () => {
  const user = userEvent.setup();          // one setup per test, before render
  const onSave = vi.fn();
  render(<RenameForm onSave={onSave} />);

  await user.type(screen.getByRole('textbox', { name: /name/i }), 'New title');
  await user.click(screen.getByRole('button', { name: /save/i }));

  expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  expect(onSave).toHaveBeenCalledWith('New title');
});
```

## 2. Query Selection

Priority order (accessibility-aligned):

1. `getByRole('button', { name: /save/i })` — also verifies the accessible name
2. `getByLabelText` — form fields
3. `getByPlaceholderText`, `getByText`, `getByDisplayValue`
4. `getByAltText`, `getByTitle`
5. `getByTestId` — last resort for non-semantic containers

Variant semantics:
- `getBy*` — element must exist now; throws otherwise.
- `queryBy*` — ONLY for asserting absence: `expect(queryByText(...)).not.toBeInTheDocument()`.
- `findBy*` — async appearance; replaces `waitFor(() => getBy...)`.

```tsx
// GOOD
screen.getByRole('heading', { name: /risk summary/i });

// BAD — implementation-coupled, no a11y signal, breaks on markup changes
container.querySelector('.risk-summary > h2');
```

## 3. Common Mistakes Catalog (review checklist)

| Mistake | Fix |
|---|---|
| Destructuring `render` (`const { getByText } = render(...)`) | Use `screen.*` |
| `fireEvent.change` / `fireEvent.click` | `await user.type` / `await user.click` (fires full real event sequences: pointer, focus, keydown...) |
| Manual `act(...)` wrapping | RTL wraps render/events already; an "act" warning means an unawaited update — find it, don't wrap it |
| `waitFor` with side effects in the callback | Perform the action first; `waitFor` only asserts |
| `waitFor(() => {})` empty callback | `await findBy*` the expected element |
| Asserting state values, instance methods, hook internals | Assert rendered output and callbacks |
| Snapshot-testing whole components | Targeted assertions on what matters |
| `cleanup` imported manually | Automatic when the runner exposes `afterEach` globally (Vitest: `globals: true`) |
| Testing a custom hook by poking internals | Test through a component, or `renderHook` from `@testing-library/react` for reusable library hooks |
| Wrapping every test in providers ad hoc | One custom `render` with a `wrapper` (router, QueryClientProvider, theme) in `test-utils.tsx` |

## 4. Async UI and Network

- Mock at the network boundary with **MSW** — tests then survive refactors from
  `useEffect` fetch → Query → loaders, because they don't know how fetching happens.
- For TanStack Query tests: create a fresh `QueryClient` per test with
  `retry: false`; assert loading → success states via `findBy*`.
- Fake timers and `user-event` need wiring: `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`.

```tsx
// GOOD — MSW handler per scenario
server.use(http.get('/api/risks/:id', () => HttpResponse.json(riskFixture)));
render(<RiskPanel id="r1" />, { wrapper: createWrapper() });
expect(await screen.findByRole('heading', { name: /flood risk/i })).toBeInTheDocument();

// BAD — mocking your own hook couples the test to implementation
vi.mock('./useRisk', () => ({ useRisk: () => ({ data: riskFixture }) }));
```

## 5. What to Test at Which Level

- **Component tests (most tests)**: user-visible behavior of a component/feature with
  real children and MSW-mocked network.
- **Hook tests (`renderHook`)**: only for reusable, library-like hooks; app hooks are
  covered through their components.
- **E2E (Playwright)**: critical flows, real backend or full MSW; not a substitute for
  component tests.
- Server Components (async, data-accessing) are not unit-testable with RTL in a stable
  way as of mid-2026 — cover them via E2E or extract their pure logic into testable
  functions; test the client components they render normally.

## 6. Vitest Setup Notes

- `environment: 'jsdom'` (or `happy-dom`); `setupFiles` registers `@testing-library/jest-dom/vitest`
  matchers and MSW server lifecycle (`beforeAll listen / afterEach resetHandlers / afterAll close`).
- In a Vite project, reuse the app's Vite config (`vitest/config` + same plugins) so JSX,
  the React Compiler plugin, and path aliases behave identically in tests.
- Vitest Browser Mode (running component tests in a real browser) is maturing as an
  alternative to jsdom — fine to adopt for new projects when jsdom fidelity bites
  (layout, real events), but jsdom remains the low-friction default.
- Lint: `eslint-plugin-testing-library` + `eslint-plugin-jest-dom` catch most of §3
  automatically.
