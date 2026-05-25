# Frontend Coding Standards

Applies to everything under `frontend/`. Read this file before writing or reviewing any frontend code.

---

## Design Principles

Same four principles as the backend — mandatory, enforced in code review.

- **Single Responsibility** — each component, hook, and module has exactly one reason to change.
- **Open/Closed** — extend behaviour by composing new components or hooks, not by modifying existing ones.
- **DRY** — if the same logic appears more than once, extract it to a shared hook or utility before merging.
- **KISS** — prefer the simplest correct implementation. Three similar JSX lines are better than a premature abstraction.

---

## Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| Component file | PascalCase `.tsx` | `SideNavBar.tsx`, `ChatInput.tsx` |
| Hook file | camelCase `.ts`, `use` prefix | `useChat.ts`, `useSession.ts` |
| Store file | camelCase + `Store` suffix `.ts` | `conversationStore.ts`, `uiStore.ts` |
| Utility / lib file | camelCase `.ts` | `utils.ts`, `request.ts`, `api.ts` |
| Type file | camelCase `.ts` | `conversation.ts`, `routing.ts` |
| Component function | PascalCase | `export function ChatInput(...)` |
| Props interface | PascalCase + `Props` suffix | `ChatInputProps`, `ButtonProps` |
| Hook function | camelCase + `use` prefix | `useChat`, `useSession` |
| Event handler | `handle` prefix | `handleSend`, `handleKeyDown` |
| Domain constant object | SCREAMING_SNAKE | `MODULE_ID`, `SESSION_STATUS` |
| Derived type from constant | PascalCase | `ModuleID`, `SessionStatus` |
| Generic type parameter | `T` prefix + semantic name | `TData`, `TResponse`, `TItem` |
| Environment variable | `NEXT_PUBLIC_` prefix (client) | `NEXT_PUBLIC_API_BASE_URL` |
| CSS semantic class | lowercase-kebab | `.glass-panel`, `.ai-glow` |

---

## TypeScript Rules

### Domain Values — `as const` Objects (not `enum`, not bare `type` unions)

Any categorical domain value reused in more than one place must be defined as an `as const` object. Raw string literals for these cases are forbidden outside the definition file.

This mirrors the backend's `StrEnum` approach: a single canonical source, refactor-safe, iterable.

```ts
// ✓ Correct — single source in types/conversation.ts
export const MODULE_ID = {
  M1: 'M1_PROPERTY_NEEDS',
  M2: 'M2_LIFESTYLE',
  M3: 'M3_SUBURB_PREFERENCE',
  M4: 'M4_BUDGET',
  COMPLETE: 'COMPLETE',
} as const

export type ModuleID = typeof MODULE_ID[keyof typeof MODULE_ID]

// Usage
if (state.currentModule === MODULE_ID.M1) { ... }   // ✓ refactor-safe
if (state.currentModule === 'M1_PROPERTY_NEEDS') { ... }  // ✗ magic string

// ✗ Incorrect — bare union, string literals scattered across files
export type ModuleID = 'M1_PROPERTY_NEEDS' | 'M2_LIFESTYLE' | ...
```

TypeScript `enum` is forbidden — it has tree-shaking issues, numeric/string mixing footguns, and requires extra conversion when exchanging JSON with the backend.

`as const` objects live in the type file that owns their domain (`types/conversation.ts`, `types/routing.ts`). If a value is used only within a single component or hook, it may be defined at the top of that file.

### interface vs type

| Use case | Tool |
|---|---|
| Object shape: component Props, Store structure, DTO, API response | `interface` |
| Union type, derived type, function signature alias, utility type | `type` |

`interface` is preferred for object shapes because it produces clearer error messages and supports `extends` for composition. `type` is used for everything that `interface` cannot express.

```ts
// ✓ Object shapes → interface
interface ChatInputProps {
  onSend: (message: string) => void
  isLoading: boolean
  disabled?: boolean
}

interface ConversationStore {
  sessionId: string | null
  messages: UIMessage[]
  isLoading: boolean
}

// ✓ Unions, derived types → type
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ModuleID = typeof MODULE_ID[keyof typeof MODULE_ID]
type SendHandler = (content: string) => Promise<void>
```

### Null vs Undefined

Use `T | null` for all optional domain fields. Never use `T | undefined` for fields that represent absent backend data.

`undefined` is acceptable only for truly optional function parameters (`param?: T`) and React prop defaults.

```ts
// ✓ Domain null — matches backend Pydantic Optional[T] → None
interface M4Budget {
  budget_max: number | null
  deposit_amount: number | null
}

// ✓ Optional prop — acceptable undefined
interface SkeletonTextProps {
  width?: string   // undefined means "use default"
}

// ✗ Wrong — domain fields should not use undefined
interface M4Budget {
  budget_max?: number   // ambiguous: unset vs explicitly null
}
```

### No `any`

`any` is forbidden. Use `unknown` for genuinely unknown external data and narrow it before use. Use proper generics or union types for polymorphic cases.

```ts
// ✓
const raw: unknown = JSON.parse(text)
if (typeof raw === 'object' && raw !== null) { ... }

// ✗
const raw: any = JSON.parse(text)
```

### Function Signatures

All exported functions must have explicit parameter types and return types. Return type inference is allowed only for trivial one-liners where the type is obvious from reading the expression.

```ts
// ✓ explicit
export function formatAUD(amount: number): string { ... }
export function createInitialState(sessionId: string): ConversationStateDTO { ... }

// ✓ trivial inference — acceptable
const double = (n: number) => n * 2

// ✗ missing return type on non-trivial function
export function createInitialState(sessionId: string) { ... }
```

### Local Variables

Every local variable must be explicitly annotated, even when TypeScript can infer the type. This makes intent unambiguous and prevents silent widening when the right-hand side changes.

```ts
// ✓ explicit annotation on every local variable
function buildLabel(module: ModuleID): string {
  const prefix: string = 'Module'
  const index: number = MODULE_ORDER.indexOf(module)
  const label: string = `${prefix} ${index + 1}`
  return label
}

// ✗ relying on inference — type intent is invisible
function buildLabel(module: ModuleID): string {
  const prefix = 'Module'
  const index = MODULE_ORDER.indexOf(module)
  const label = `${prefix} ${index + 1}`
  return label
}
```

---

## Component Rules

### UI vs Container Separation

Every component must be either a **UI component** or a **Container component** — never both.

| | UI Component | Container Component |
|---|---|---|
| Responsibility | Render only — layout, styling, ARIA | Fetch data, call hooks, own business logic |
| Props | Receives all data and callbacks as props | May call hooks directly; passes data down to UI |
| Side effects | None | Allowed (`useEffect`, store reads, API calls) |
| Location | `src/components/ui/` | `src/components/` (or co-located with the page) |
| Testability | Render with props alone | Tested via hook + MSW, or integration test |

```ts
// ✓ UI component — pure rendering, no logic
interface MessageBubbleProps {
  content: string
  role: 'user' | 'assistant'
  isLoading: boolean
}

export function MessageBubble({ content, role, isLoading }: MessageBubbleProps) {
  return (
    <div data-role={role}>
      {isLoading ? <TypingIndicator /> : <p>{content}</p>}
    </div>
  )
}

// ✓ Container component — owns logic, delegates rendering
export function MessageList() {
  const messages: UIMessage[] = useConversationStore((s) => s.messages)
  const isLoading: boolean = useConversationStore((s) => s.isLoading)

  return (
    <ul>
      {messages.map((msg) => (
        <MessageBubble key={msg.id} content={msg.content} role={msg.role} isLoading={isLoading} />
      ))}
    </ul>
  )
}

// ✗ Mixed — UI component that also reads from the store
export function MessageBubble({ id }: { id: string }) {
  const msg = useConversationStore((s) => s.messages.find((m) => m.id === id))  // ← logic leak
  return <div>{msg?.content}</div>
}
```

A UI component that needs to react to state must receive that state as a prop, not reach into a store or hook itself.

### Declaration Style — Named Function

Always use named `function` declarations, not arrow functions or `React.FC`. This applies to page components, layout components, and all shared components.

```ts
// ✓ Correct
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  loading?: boolean
}

export function Button({ variant = 'secondary', loading, children, ...rest }: ButtonProps) {
  return <button disabled={loading} {...rest}>{children}</button>
}

// ✓ Default export for pages (Next.js App Router requirement)
export default function ChatPage({ params }: { params: { sessionId: string } }) {
  return <main>...</main>
}

// ✗ Arrow function component
const Button = ({ variant }: ButtonProps) => <button>...</button>

// ✗ React.FC (deprecated implicit children type)
const Button: React.FC<ButtonProps> = ({ variant }) => <button>...</button>
```

### Props Interface

Declare the Props interface **immediately above** the component function in the same file. Do not export Props interfaces unless another component genuinely needs to extend them.

```ts
// ✓ co-located, unexported (default)
interface TypingIndicatorProps {
  className?: string
}

export function TypingIndicator({ className }: TypingIndicatorProps) { ... }

// ✓ exported only when needed for extension
export interface CardProps {
  title: string
}
// OtherCard extends CardProps in another file
```

### Prop Spreading

Never spread an unknown or `Record<string, unknown>` shape onto a DOM element. Only spread `HTMLElementAttributes` sub-types (as shown in Button above) after explicitly typing `rest`.

---

## Hook Rules

- Every hook starts with `use` — no exceptions.
- Each hook has a single responsibility. If a hook handles both fetching and UI state, split it.
- Hooks must have explicit return type annotations.
- Side effects (API calls, subscriptions) live in hooks, never directly in component render bodies.

```ts
// ✓ explicit return type
export function useChat(): { sendMessage: (content: string) => Promise<void>; isLoading: boolean } {
  ...
}

// ✓ or extract to a named interface when the return shape is complex
interface UseChatReturn {
  sendMessage: (content: string) => Promise<void>
  isLoading: boolean
}

export function useChat(): UseChatReturn { ... }
```

---

## Async Patterns

Unlike the backend, the `_async` suffix is **not** used in the frontend. React event handlers and hook functions follow standard camelCase.

Promise-returning functions must annotate their return type explicitly:

```ts
// ✓
async function sendMessage(content: string): Promise<void> { ... }

// ✗ no return type
async function sendMessage(content: string) { ... }
```

Never fire-and-forget without error handling inside components or hooks. Always handle the rejected case, at minimum with a `console.error` or a toast in P0.

```ts
// ✗ fire-and-forget
const handleSend = () => {
  sendMessage(input)
}

// ✓ error handled
const handleSend = async () => {
  try {
    await sendMessage(input)
  } catch (err) {
    // handle or surface to UI
  }
}
```

---

## State (Zustand) Rules

- Store files live in `src/stores/`. One store per domain concern.
- State fields are plain types — no class instances, no functions in the state slice.
- All mutations happen through named actions defined inside `create(...)`.
- Actions use imperative verbs: `setLoading`, `addMessage`, `clearSession`, `restoreFromStorage`.
- Do **not** read Zustand store state outside React components or hooks (no global `useStore.getState()` calls in lib/ or api/).

```ts
// ✓ store structure
export const useConversationStore = create<ConversationStore>((set, get) => ({
  sessionId: null,
  messages: [],
  isLoading: false,

  setLoading: (loading: boolean): void => set({ isLoading: loading }),
  addUserMessage: (content: string): void => set((state) => ({
    messages: [...state.messages, { id: uuid(), role: 'user', content, isLoading: false, timestamp: new Date() }],
  })),
  clearSession: (): void => set({ sessionId: null, messages: [], routing: null }),
}))
```

---

## Styling

### Theme Variables — Global First

All colors, font sizes, spacing, shadows, and any other design tokens must come from the `@theme` block in `src/styles/globals.css`. Using Tailwind's built-in scale values (e.g. `text-blue-500`, `text-sm`, `p-4`) directly in components is **forbidden** for any value that represents a design decision.

**Decision tree when you need a design value:**

1. **It exists in `globals.css` `@theme`** → use the corresponding CSS variable class (e.g. `text-[--color-primary]` or a mapped utility).
2. **It doesn't exist yet** → either add it to `@theme` in `globals.css` yourself, or leave a `// TODO: needs theme token — ask designer` comment and flag it in the PR. Do not silently fall back to a Tailwind built-in.

```css
/* src/styles/globals.css — add new tokens here */
@theme {
  --color-primary: #1a56db;
  --color-surface: #0f172a;
  --font-size-chat: 0.9375rem;
  --radius-card: 0.75rem;
}
```

```tsx
// ✓ Uses theme token defined in globals.css
<p className="text-[--color-primary] text-[length:--font-size-chat]">Hello</p>

// ✗ Tailwind built-in color — bypasses the design system
<p className="text-blue-600 text-sm">Hello</p>

// ✓ Acceptable when no design decision is involved (layout mechanics)
<div className="flex items-center gap-2">...</div>
```

The exception for Tailwind built-ins: **layout and structural utilities** that carry no design opinion (`flex`, `grid`, `items-center`, `gap-*`, `w-full`, `overflow-hidden`, etc.) may use Tailwind defaults since they are not design tokens.

### Class Organisation — `cn()` + Category Lines

All `className` values with more than one category of utility must use the `cn()` helper from `src/lib/utils.ts` and split classes across lines by category. Never write a flat string of unrelated classes.

`cn()` combines `clsx` (conditional logic) and `tailwind-merge` (conflict resolution). The last class wins on conflict, so a `className` prop passed by the caller automatically overrides component defaults.

```ts
// src/lib/utils.ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merges Tailwind classes with conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
```

**Line order** (one line per category; omit categories that are unused):

| # | Category | Examples |
|---|---|---|
| 1 | Layout & display | `flex`, `grid`, `hidden`, `items-center`, `justify-between` |
| 2 | Sizing & spacing | `w-full`, `h-12`, `px-4`, `py-2`, `gap-3` |
| 3 | Typography | `font-medium`, `text-[length:--font-size-chat]`, `leading-tight` |
| 4 | Color | `text-[--color-primary]`, `bg-[--color-surface]` |
| 5 | Border & radius | `rounded-[--radius-card]`, `border`, `border-[--color-border]` |
| 6 | Effects | `shadow-md`, `opacity-50`, `transition-colors` |
| 7 | State & conditional | `hover:bg-[--color-hover]`, `isActive && '...'`, `className` prop |

```tsx
// ✓ cn() with category lines
<button
  className={cn(
    'flex items-center justify-center',       // layout
    'h-10 px-4 gap-2',                        // sizing & spacing
    'font-medium',                            // typography
    'text-[--color-on-primary] bg-[--color-primary]', // color
    'rounded-[--radius-card]',                // border & radius
    'transition-colors',                      // effects
    disabled && 'opacity-50 cursor-not-allowed', // state
    className,                                // caller override
  )}
>
  {children}
</button>

// ✗ Flat unorganised string
<button className="flex items-center h-10 px-4 font-medium text-white bg-blue-600 rounded-lg transition-colors disabled:opacity-50">
```

---

## Import Order

ESLint enforces this order (no manual sorting needed — Prettier handles formatting):

1. React and React types
2. Next.js
3. Third-party packages
4. `@/` path alias (internal src/)
5. Relative imports (`./`, `../`)

```ts
// ✓
import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { create } from 'zustand'
import { useConversationStore } from '@/stores/conversationStore'
import { formatAUD } from '@/lib/utils'
import type { ConversationStateDTO } from '@/types/conversation'
```

Type-only imports must use `import type` when importing types that are not used as values.

---

## Server vs Client Components (Next.js App Router)

Default to **Server Components**. Add `'use client'` only when the component genuinely requires it, and push the boundary as far toward the leaf as possible.

**`'use client'` is required when the component uses:**
- React hooks (`useState`, `useEffect`, `useRef`, etc.)
- Browser APIs (`window`, `localStorage`, `navigator`, etc.)
- Event handlers (`onClick`, `onChange`, etc.)
- Zustand store reads

**`'use client'` is NOT needed for:**
- Components that only receive props and render JSX
- Components that fetch data via `async/await` at the top level
- Components that import Server-only utilities

```tsx
// ✓ Server Component — data fetching, no interactivity
export default async function SessionPage({ params }: { params: { sessionId: string } }) {
  const session = await fetchSession(params.sessionId)
  return <ChatLayout session={session} />
}

// ✓ 'use client' pushed to the leaf that needs interactivity
'use client'
export function ChatInput({ onSend }: ChatInputProps) {
  const [value, setValue] = useState('')
  return <input value={value} onChange={(e) => setValue(e.target.value)} />
}

// ✗ Entire page marked 'use client' just because one child needs it
'use client'
export default function SessionPage() { ... }
```

Never mark a layout or page `'use client'` because a child component needs hooks — extract the interactive part into its own Client Component instead.

---

## List Keys

The `key` prop on list items must be a **stable, unique identifier** from the data. Array index is forbidden as a key.

```tsx
// ✓ stable ID from data
{messages.map((msg) => (
  <MessageBubble key={msg.id} content={msg.content} role={msg.role} />
))}

// ✗ index — breaks React state on reorder or splice
{messages.map((msg, index) => (
  <MessageBubble key={index} content={msg.content} role={msg.role} />
))}
```

---

## Accessibility

Use semantic HTML elements. Never use a `<div>` or `<span>` where a semantic element exists.

| Intent | Use | Not |
|---|---|---|
| Clickable action | `<button>` | `<div onClick>` |
| Navigation link | `<a href>` or `<Link>` | `<div onClick>` |
| Form field label | `<label htmlFor>` | plain text next to input |
| Page section | `<main>`, `<nav>`, `<section>`, `<header>` | `<div>` |

Additional requirements:
- Every `<img>` must have a non-empty `alt` attribute (use `alt=""` only for decorative images).
- Interactive elements must be keyboard operable — no `onClick`-only handlers on non-interactive elements.
- Use ARIA attributes (`aria-label`, `aria-live`, `aria-busy`) only when semantic HTML alone is insufficient.

```tsx
// ✓
<button onClick={handleSend} aria-label="Send message" disabled={isLoading}>
  <SendIcon />
</button>

// ✗ div used as button — not keyboard accessible, no ARIA role
<div onClick={handleSend}>
  <SendIcon />
</div>
```

---

## Performance — `memo`, `useMemo`, `useCallback`

**Do not add these optimizations preemptively.** Apply them only in the scenarios explicitly recommended by the React team:

| API | Use only when |
|---|---|
| `React.memo` | A component re-renders visibly too often and profiling confirms it is the bottleneck |
| `useMemo` | An expensive pure computation (e.g. filtering a large list) is re-run on every render and profiling shows it |
| `useCallback` | A callback is passed as a prop to a `React.memo`-wrapped child and causing it to re-render unnecessarily |

```tsx
// ✗ Premature — no evidence of performance problem
const handleSend = useCallback(() => {
  sendMessage(input)
}, [input, sendMessage])

// ✓ Justified — MessageList is memo-wrapped and handleSend is its only changing prop
const handleSend = useCallback(() => {
  sendMessage(input)
}, [input, sendMessage])

export const MessageList = React.memo(function MessageList({ onSend }: MessageListProps) {
  ...
})
```

When in doubt, ship without the optimization and add it only after measuring with React DevTools Profiler.

---

## Barrel Files (`index.ts`)

Every `src/` subdirectory that contains more than one exported module **must** have an `index.ts` that re-exports its public surface. Consumers import from the directory, never from individual files within it.

```
src/
├── components/
│   ├── index.ts          ← re-exports all public components
│   ├── ChatInput.tsx
│   └── MessageList.tsx
├── hooks/
│   ├── index.ts
│   └── useChat.ts
└── stores/
    ├── index.ts
    └── conversationStore.ts
```

```ts
// src/components/index.ts
export { ChatInput } from './ChatInput'
export { MessageList } from './MessageList'

// ✓ Consumer imports from the directory
import { ChatInput, MessageList } from '@/components'

// ✗ Consumer imports from the file directly
import { ChatInput } from '@/components/ChatInput'
```

Only export symbols that are part of the public API of that directory. Internal helpers used only within the directory are not re-exported.

---

## Test Selectors — `data-testid`

Use `data-testid` attributes as the selector of last resort — only when no accessible role, label, or text query can uniquely identify the element.

**Naming convention:** `kebab-case`, scoped to the component: `<component>-<element>`.

```tsx
// ✓ Accessible query preferred — no data-testid needed
screen.getByRole('button', { name: /send/i })
screen.getByLabelText('Message input')

// ✓ data-testid only when no semantic selector exists
<div data-testid="message-list-empty-state">No messages yet</div>
screen.getByTestId('message-list-empty-state')

// ✗ data-testid where an accessible query would work
<button data-testid="send-button">Send</button>
```

`data-testid` attributes must be stripped in production builds. Configure this in `next.config.js` using the `reactRemoveProperties` compiler option.

---

## Comment Rules

**Components and hooks: no JSDoc.** The Props interface is the documentation. Write a comment only when the *why* is non-obvious: a hidden constraint, a workaround for a browser bug, a non-obvious invariant.

**`lib/` pure functions: one-line JSDoc** describing parameters and return value. No multi-paragraph docstrings.

```ts
// ✓ lib/utils.ts — one-line JSDoc for pure functions
/** Formats an AUD integer for display. formatAUD(1200000) → '$1,200,000' */
export function formatAUD(amount: number): string { ... }

/** Returns a fresh ConversationStateDTO with all fields null and status IN_PROGRESS. */
export function createInitialState(sessionId: string): ConversationStateDTO { ... }

// ✓ Component — no JSDoc; Props interface is sufficient documentation
interface BorrowingCapacityCardProps {
  data: BorrowingCapacityResult
}

export function BorrowingCapacityCard({ data }: BorrowingCapacityCardProps) {
  // disclaimer must always be rendered — compliance requirement
  return (
    <div>
      ...
      <p>{data.disclaimer}</p>
    </div>
  )
}

// ✗ Redundant JSDoc on a component
/**
 * Displays the borrowing capacity card.
 * @param data - The borrowing capacity result.
 */
export function BorrowingCapacityCard(...) { ... }
```

---

## Formatting

Prettier handles all formatting. Do not override Prettier decisions with `// prettier-ignore` without a documented reason in the same line comment. Configuration is in `frontend/.prettierrc`.

---

## Key Invariants

These must never be violated regardless of context:

1. **Complete state replacement** — `setUpdatedState` in `conversationStore` must do a full replacement (`state = updatedState`), never `Object.assign` or spread merge. Owned by `conversationStore.ts`.

2. **No magic domain strings** — any string used as a domain identifier in more than one file must be defined as an `as const` object entry. Inline string literals for domain values are forbidden outside the definition file.

3. **No direct axios/fetch in components** — all HTTP calls go through `lib/api.ts` (which uses `lib/request.ts`). Components and hooks import from `lib/api.ts` only.

4. **disclaimer always rendered** — `BorrowingCapacityCard` must always render `data.disclaimer`. It is a compliance requirement and must not be conditionally hidden.

5. **`T | null` for domain optionals** — backend Pydantic `Optional[T]` serialises to `null`, never `undefined`. Frontend types must match.
