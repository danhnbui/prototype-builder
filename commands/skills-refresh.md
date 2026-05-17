---
description: Re-pull the pinned agent-skill-set repo. Prompts the user to upgrade to a newer tag if one exists. Rolls back if required skills are missing in the new tag.
---

## User Input

```text
$ARGUMENTS
```

If user input specifies a target tag (e.g., `v0.2.0`), pin to that. If `--check` is passed, list available newer tags without prompting to upgrade. Otherwise, run the full interactive refresh.

## Execution flow

### Step 1 — Read current pin
Open `.specify/memory/constitution.md` → `## Skill Pinning` section → `Pinned tag` value. If missing, HARD FAIL: `"Run /speckit.prototype-builder.scaffold first."`

### Step 2 — Fetch latest tags
In `./.claude/skills/`, run:

```bash
git fetch --tags 2>&1
```

If fetch fails (network, auth) → soft fail with the error message; do not modify local state.

### Step 3 — List newer tags

```bash
git tag --sort=-v:refname
```

Filter to tags newer than the currently pinned tag.

**If no newer tags**:
```
Already on latest pinned tag: <current>
```
End.

### Step 4 — Prompt user

```
Newer tags available:
  - <tag1>  (latest)
  - <tag2>
  - <tag3>
  ...

Pin to <tag1>? (yes / no / specific tag / cancel)
```

Wait for response.

- `yes` → target = latest
- `no` or `cancel` → end without changes
- specific tag → target = that tag
- anything else → re-prompt once, then cancel

### Step 5 — Checkout target tag

```bash
git checkout <target-tag>
```

### Step 6 — Verify required skills

Check that all required skills (from `/speckit.prototype-builder.scaffold` Step 3 list) still exist as folders with `SKILL.md`. If any are missing:

**ROLLBACK**:

```bash
git checkout <previous-tag>
```

Then output:

```
⚠ ROLLBACK — new tag <target> is missing required skills:
  - <skill1>
  - <skill2>

Rolled back to <previous>.
File an issue at https://github.com/danhnbui/agent-skill-set/issues
```

End. Do not update constitution.md.

### Step 7 — Update constitution.md
On success, update `.specify/memory/constitution.md` → `## Skill Pinning` → `Pinned tag: <target>`.

### Step 8 — Confirm to user

```
✅ Skills refreshed.
   Previous tag: <previous>
   New tag: <target>
   constitution.md updated.

No file changes to template.html (drift check still uses the same constitution).
```

## Important rules

- **NEVER pin to `main` or `HEAD`** — always pin to an explicit tag (per NFR-6).
- **NEVER proceed past Step 6 if required skills are missing** — always roll back.
- **NEVER auto-trigger this from another command.** The user explicitly opts in to upgrades.
- **NEVER modify the pinned tag outside this command's approval flow.**
