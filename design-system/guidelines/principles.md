# Design Principles

> The **why** behind every design decision. These are aspirational beliefs; not directly testable.
> For enforceable rules, see [rules.md](./rules.md).

### 1. Errors state the outcome, never color alone
Every error, lockout, and block communicates in words what happened and what the user should do next. Color reinforces the message but never carries it alone — a red border always pairs with explanatory text. This keeps the flow legible for colour-blind users and screen readers.

### 2. Edge cases are first-class
Throttled paths, lockouts, hard-block terminal states, empty states, and offline behavior receive the same design rigor as the happy path. Rate limits, expiry windows, and attempt counters are surfaced in the UI and documented in the flow notes — they are product behavior, not afterthoughts.

### 3. Tokens, not raw values
Colors, spacing, radii, and typography MUST resolve through design tokens declared in [foundations/](../components/foundations/). Inline hex values, raw `px` literals, and ad-hoc color names are signals of design drift, not flexibility.

### 4. One primary action per screen
The dominant call-to-action on any screen MUST be visually singular. Secondary actions use lower-emphasis variants (ghost, link). Two equally-emphasized primaries on the same screen is a forbidden pattern.

### 5. Composition over branching
When two components share 80%+ of their anatomy, they MUST be one component with a `variant` prop — not two separate components. The DS catalog stays compact; intent stays clear at the call site.
