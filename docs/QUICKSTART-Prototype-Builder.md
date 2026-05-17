# Quick Start — Local prototype (skip SpecKit)

> **TL;DR**: For a fast one-off prototype, copy `~/Desktop/prototype-builder/` to a new folder and open Claude Code in it. Done in 10 seconds. No SpecKit, no GitHub, no install.

The 6 docs in this folder (HANDOFF, 01-srs, 02-architecture, 03-data-flow, 04-orchestrator, 05-execution-plan) describe the **full SpecKit + Preset + Extension** path. That's the right path for serious prototypes that ship, get handed off, or live across multiple sessions.

But often you just need to **build a single throwaway prototype quickly**. For that, use the local copy.

---

## The 10-second path

```bash
cp -R ~/Desktop/prototype-builder ~/Desktop/my-new-prototype
cd ~/Desktop/my-new-prototype
claude
```

Then say to Claude: **`Build a [whatever you want]`**.

The local copy already includes a self-contained Claude Code skill at `.claude/skills/prototype-builder/`. The skill loads `template.html` and guides Claude through filling the 5 tabs.

When done:

```bash
open template.html       # opens in your default browser
```

---

## Two paths, one foundation

Both paths produce the **same 5-tab `template.html`** as the deliverable. The difference is the workflow around it:

| Aspect | Local quick path | SpecKit path |
|---|---|---|
| Setup time | ~10 sec | ~15 min one-time install + ~2 min per project |
| Repos involved | 0 (everything local) | 2 — [agent-skill-set](https://github.com/danhnbui/agent-skill-set) + [spec-kit-extension-prototype-builder](https://github.com/danhnbui/spec-kit-extension-prototype-builder) (both Preset + Extension are in the latter as of v0.2.0) |
| Files in project | 4 (template + guide + skill bundle + zip) | 25+ (`.specify/`, `.claude/`, `design-system/`, `prototype/`, docs) |
| Drift detection across trio of tabs | ❌ — you self-police | ✅ — inline check in `/build`, pause-and-ask on violation |
| Stack lock (HITL gate G3) | ❌ | ✅ |
| Design system lock (HITL gate G2) | ❌ | ✅ |
| Tab 2 auto-sync from spec.md / clarify.md | ❌ — manual | ✅ — via `after_specify` / `after_clarify` hooks |
| Formal spec.md / plan.md / tasks.md artifacts | ❌ | ✅ |
| Handoff doc generation | ❌ — Claude writes it freeform | ✅ — `/speckit-prototype-builder-handoff` produces 7:3 Screen view |
| ERD with 5 guardrails | ❌ — Claude writes a Mermaid block | ✅ — `/speckit-prototype-builder-sync-erd` enforces |
| Skill repo pinning + refresh | ❌ — frozen in the local copy | ✅ — `/speckit-prototype-builder-skills-refresh` |
| Best for | One-off prototypes · fast iteration · solo work | Multi-session projects · formal handoff · team work |

---

## When to upgrade from local → SpecKit

You started with the local copy but now you need:

- **Multiple test sessions** with consistent principles → upgrade
- **More than 3 designers** working on it → upgrade
- **Engineering handoff** with documented trade-offs → upgrade
- **The prototype lives more than 1 week** → consider upgrading
- **Repeatable across many projects** → definitely upgrade (Preset + Extension is reusable)

To upgrade, install SpecKit once and then per-project run the unified install (one repo URL covers both Preset + Extension as of v0.2.0):

```bash
# One-time SpecKit install (skip if already installed)
brew install gh uv
gh auth login
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.8.11

# Per new prototype project
mkdir ~/Desktop/my-prototype && cd ~/Desktop/my-prototype
specify init . --integration claude --force

# Both halves come from one repo now
gh repo clone danhnbui/spec-kit-extension-prototype-builder /tmp/pb -- --branch v0.2.0
specify preset add --dev /tmp/pb         # one repo, two install commands (SpecKit treats them as separate concepts)
specify extension add --dev /tmp/pb

claude
# then in Claude Code, run in order:
#   /speckit-prototype-builder-scaffold
#   /speckit-constitution
#   /speckit-specify Build a [your idea]
#   /speckit-clarify
#   /speckit-plan
#   /speckit-tasks
#   /speckit-prototype-builder-build
#   /speckit-prototype-builder-sync-flow
#   /speckit-prototype-builder-handoff
#   /speckit-prototype-builder-sync-erd
# then: open prototype/template.html
```

Copy your existing local `template.html` content into the new project's `prototype/template.html` if you're upgrading mid-project.

---

## Source folder structure

`~/Desktop/prototype-builder/` (128 KB total) contains:

```text
prototype-builder/
├── template.html                              # The 5-tab scaffold (40 KB)
├── PROTOTYPE-BUILDER.md                       # Author's guide
├── QUICKSTART.md                              # Quick-copy instructions
├── files.zip                                  # Bundle of the 6 docs in this folder
└── .claude/
    └── skills/
        └── prototype-builder/
            ├── SKILL.md                       # The skill body
            └── references/
                ├── tab-1-prototype.md
                ├── tab-2-summary.md
                ├── tab-3-user-flow.md
                ├── tab-4-variants.md
                └── tab-5-erd.md
```

This entire folder is the unit of copy. Just `cp -R` it to a new location and Claude Code in that folder has everything needed.

---

## Verifying the local copy still works

Periodically (e.g., after a macOS reinstall), confirm the local copy is intact:

```bash
ls ~/Desktop/prototype-builder/template.html
ls ~/Desktop/prototype-builder/.claude/skills/prototype-builder/SKILL.md
ls ~/Desktop/prototype-builder/.claude/skills/prototype-builder/references/
```

All 3 should exist. If anything's missing, re-clone from GitHub:

```bash
# (The local copy isn't in a git repo today — consider committing it to a "personal-toolbox" repo for future restoration)
```

---

## Backing up the local copy

Since this folder is the only copy of the local quick-start path (not in either of the 2 active GitHub repos), consider:

1. **Manual zip** to iCloud Drive periodically:
   ```bash
   zip -r ~/Library/Mobile\ Documents/com~apple~CloudDocs/Backups/prototype-builder-$(date +%Y-%m-%d).zip ~/Desktop/prototype-builder/
   ```

2. **Commit to a personal-toolbox GitHub repo** (private, your account):
   ```bash
   gh repo create danhnbui/prototype-builder-local --private --source ~/Desktop/prototype-builder --push
   ```

3. **Or rely on Time Machine** if it's enabled.

The 128 KB is tiny — any backup strategy works.

---

## Related docs

- [HANDOFF.md](HANDOFF.md) — entry point for the full SpecKit path
- [01-srs.md](01-srs.md) through [05-execution-plan.md](05-execution-plan.md) — full specification
- [`~/Desktop/prototype-builder/PROTOTYPE-BUILDER.md`](../prototype-builder/PROTOTYPE-BUILDER.md) — author's guide to the 5-tab pattern
- [`~/Desktop/prototype-builder/QUICKSTART.md`](../prototype-builder/QUICKSTART.md) — the quick-copy instructions (lives with the source for self-documentation)
