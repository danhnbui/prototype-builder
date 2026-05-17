---
description: Init-time scaffold for a new prototype project. Clones agent-skill-set at the pinned tag, copies template.html into ./prototype/, prompts for design system + stack, and locks both into constitution.md. Run this once, after `specify init` and before `/speckit.constitution`.
handoffs:
  - label: Establish Constitution
    agent: speckit.constitution
    prompt: Create the prototype constitution. Locks are already recorded — fill in the Principles section.
---

## User Input

```text
$ARGUMENTS
```

The user input may pre-supply: design-system URL, language, framework. If empty, prompt interactively.

## Goal

Bring a freshly-`specify init`ed directory into the state required by all other Prototype Builder commands:

1. `./.claude/skills/` populated by cloning `https://github.com/danhnbui/agent-skill-set` at pinned tag `v0.2.0`
2. `./prototype/template.html` copied from this extension's `assets/template.html`
3. `./design-system/` populated from the user-chosen source
4. `.specify/memory/constitution.md` updated with **Stack Lock** + **DS Lock** + **Skill Pinning** sections (Principles section deferred to `/speckit.constitution`)

## Execution flow

### Step 1 — Verify prereqs

- Confirm the current directory is a SpecKit project (presence of `.specify/`).
- Confirm `git` is installed and `gh auth status` (if repo is private) returns authenticated.
- If `./prototype/template.html` already exists OR `./.claude/skills/` is non-empty, ask before overwriting.

### Step 2 — Clone the skill repo (FR-5)

The default repo is **private**, so we use `gh repo clone` (relies on `gh auth` being configured) instead of plain `git clone`:

```bash
# Primary path — private repo via gh auth
gh repo clone danhnbui/agent-skill-set ./.claude/skills -- --depth 1 --branch v0.2.0

# Or, if the repo has been made public, plain git is fine:
# git clone --depth 1 --branch v0.2.0 https://github.com/danhnbui/agent-skill-set.git ./.claude/skills
```

If the user passed `--local-skills=<path>` in `$ARGUMENTS` (or `--local-skills` alone), skip the network clone entirely and copy from the local path (defaulting to `~/.claude/skills/`):

```bash
LOCAL_SRC=${LOCAL_SKILLS_PATH:-$HOME/.claude/skills}
mkdir -p ./.claude/skills
for skill in think-critique-prd think-clarify ref-blueprint ref-prd think-layout think-logic craft-connect-flow craft-research design-component-build design-critics agent-orchestrate-tasks; do
  if [ -d "$LOCAL_SRC/$skill" ]; then
    cp -R "$LOCAL_SRC/$skill" ./.claude/skills/
  fi
done
```

**Failure handling (G4 hard-fail)**:

If `gh repo clone` returns non-zero AND `--local-skills` wasn't passed, **HARD FAIL** with this exact message:

```
Skill repo not reachable. Either:
  1) Confirm github.com/danhnbui/agent-skill-set exists and `gh auth status` shows you're authenticated.
  2) Or pass --local-skills=<path> to copy from a local directory (defaults to ~/.claude/skills).
Then re-run /speckit.prototype-builder.scaffold.
```

Then stop. Do not continue with steps 3+.

### Step 3 — Verify required skills

The following skills MUST exist as folders with `SKILL.md` under `./.claude/skills/`:

- `think-critique-prd`
- `think-clarify`
- `ref-blueprint`
- `ref-prd`
- `think-layout`
- `think-logic`
- `craft-connect-flow`
- `design-component-build`
- `design-critics`
- `agent-orchestrate-tasks`

Optional (warn if missing but don't block):
- `craft-research`

**Failure handling**: If any required skill is missing, **HARD FAIL** with:

```
Skill repo cloned but missing required skills:
  - <skill-name>
  - <skill-name>
Re-run /speckit.prototype-builder.skills-refresh after the skills are added to the repo, then re-run scaffold.
```

### Step 4 — Copy template.html (FR-3)

SpecKit copies the entire extension directory into `.specify/extensions/<extension-id>/` at install time, so the asset lives at a deterministic project-relative path:

```bash
mkdir -p ./prototype
cp ./.specify/extensions/prototype-builder/assets/template.html ./prototype/template.html
```

If that path doesn't exist, fall back to looking it up:

```bash
EXT_PATH=$(specify extension info prototype-builder 2>/dev/null | grep -i 'install.path\|location' | head -1 | awk -F: '{print $2}' | xargs)
cp "$EXT_PATH/assets/template.html" ./prototype/template.html
```

Confirm to user: `"Tab 1–5 scaffold copied to ./prototype/template.html (~57KB, 1444 lines)."`

### Step 5 — Prompt for Design System (FR-6)

Ask the user:

```
Design system source?
  1) Git URL (e.g., https://github.com/propertyguru/hive-ui-core)
  2) Local path (e.g., ../my-ds/)
  3) Built-in (HIVE / Material / shadcn / Bootstrap)
Choose 1-3, or paste a URL/path directly:
```

Then pull or copy the DS into `./design-system/`. Verify `tokens.json` exists at the root of the pulled DS — if missing, warn and ask user to confirm.

### Step 6 — Prompt for Code Stack (FR-7)

Ask the user:

```
Code language? (HTML / React / Vue / Svelte / SwiftUI / Flutter / other):
Framework? (vanilla / Vite / Next.js / Nuxt / Remix / native / other):
```

Record both.

### Step 7 — Write locks into constitution.md

Update `.specify/memory/constitution.md` with:

```markdown
## Stack Lock
- **Language**: <chosen>
- **Framework**: <chosen>

## Design System Lock
- **Source**: <url-or-path>
- **Local path**: ./design-system/
- **Confirmed at**: <today ISO>

## Skill Pinning
- **Source**: https://github.com/danhnbui/agent-skill-set
- **Pinned tag**: v0.2.0
- **Local path**: ./.claude/skills/
```

If `constitution.md` doesn't yet exist (i.e., user hasn't run `/speckit.constitution`), this command writes those three sections AS a minimal constitution stub. The user's next step will be `/speckit.constitution` to fill in the Principles section.

### Step 8 — Confirm to user

Output:

```
✅ Prototype Builder scaffold complete.

Next steps:
  1. /speckit.constitution  — capture Principles (drives drift detection)
  2. /speckit.specify       — describe what you want to build
  3. /speckit.clarify       — capture User Insights + UI Logic Trade-offs
  4. /speckit.plan          — tech approach (uses your locked stack)
  5. /speckit.tasks         — break down by tab
  6. /speckit.prototype-builder.build    — write Tab 1 + Tab 4-Component
  7. /speckit.prototype-builder.sync-flow / handoff / sync-erd  — populate decoupled tabs

Open ./prototype/template.html in a browser to see the empty 5-tab scaffold.
```

## Important rules

- **NEVER skip step 3 (required-skills verification)** — proceeding without all required skills will cause downstream commands to fail.
- **NEVER write to `./design-system/` files** after step 5 — DS is read-only after init (HITL gate G2 protects this).
- **NEVER change the locked stack values** in subsequent commands — they trigger HITL gate G3.
- **NEVER fork SpecKit** — this command relies on SpecKit core being unmodified.
