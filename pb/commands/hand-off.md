---
description: "[Deprecated alias] Renamed to /pb:handoff-close in v1.5.1. Delivers the prototype (--people / --context)."
---

# /pb:hand-off — alias for `/pb:handoff-close`

`/pb:hand-off` was renamed to **`/pb:handoff-close`** in v1.5.1. This alias keeps existing
muscle memory, scripts, and older projects working; it will be removed in a future major
release.

**Execute [`handoff-close.md`](handoff-close.md) exactly**, as if the user had invoked
`/pb:handoff-close`, preserving any arguments passed to `/pb:hand-off` (e.g. `--people`,
`--context`, `--out <dir>`).
