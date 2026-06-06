# Constitution — Property Auth

> Durable rules for this prototype. The build loop reads this before any **trio** write
> (a screen, a component, or logic). Keep it lean — rules only, no governance ceremony.

## Principles

<!-- Numbered, falsifiable rules the drift gate checks each trio write against.
     One line each. Examples: -->
1. Error states show BOTH a danger border AND error text — never border alone.
2. One primary action per screen.
3. Every interactive element has a visible focus state.
4. All color / space / radius / shadow come from tokens — no raw hex or arbitrary px.

## Stack Lock

- **Language:** TypeScript
- **Framework:** React

Locked at `/pb:init`. A switch requires explicit approval **and** a `decisions.md` entry.

## Design System Lock

- **Name:** example-ds
- **Source:** built-in
- **Reference:** `design-system/example-ds/example-ds.md`

No style outside the DS tokens / components without a logged override (see `decisions.md`).
