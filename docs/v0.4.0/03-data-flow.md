# 03 — Data Flow

**Purpose**: Show how data moves through the system at three levels — init, per-prompt, and manual sync. Diagrams are Mermaid (Claude Code can render or read them as text).

---

## 1. Init flow (one-time per prototype)

When Danh runs `specify init --preset prototype-builder` in a fresh directory:

```mermaid
flowchart TD
    A[specify init --preset prototype-builder] --> B{Skill repo reachable?<br/>github.com/danhnbui/agent-skill-set}
    B -->|No| F1[HARD FAIL<br/>'Sync skills to repo first']
    B -->|Yes| C[git clone --depth 1 --branch v0.1.0<br/>→ .claude/skills/]
    C --> D{Required skills present?}
    D -->|No| F2[HARD FAIL<br/>list missing skills]
    D -->|Yes| E[Prompt: Design system source?]
    E --> F[Pull DS → ./design-system/<br/>Record in constitution.md]
    F --> G[Prompt: Code language?]
    G --> H[Prompt: Framework?]
    H --> I[Lock stack in constitution.md]
    I --> J[Copy template.html → ./prototype/]
    J --> K[Scaffold .specify/ structure]
    K --> L[READY for /speckit.constitution]

    classDef fail fill:#FCEBEB,stroke:#A32D2D
    class F1,F2 fail
```

### What gets created at init

| Path | Contents |
|------|----------|
| `./.claude/skills/` | Cloned skills, pinned tag |
| `./design-system/` | DS tokens + components |
| `./prototype/template.html` | Empty 5-tab scaffold |
| `./.specify/` | SpecKit standard structure |
| `./.specify/memory/constitution.md` | Includes stack lock + DS lock |
| `./.specify/presets.yml` | Preset metadata |
| `./.specify/extensions.yml` | Extension manifest + drift hooks |

---

## 2. Per-prompt flow (the main hot path)

Every time Danh sends a prompt and hits Enter:

```mermaid
flowchart TD
    P[User prompt + Enter] --> S{Prompt touches the trio?<br/>Tab 1 / Tab 2 / Tab 4-C}

    S -->|No, only Tab 3 / 4-S / 5 / no tab| EX[Execute normally<br/>No drift check]
    S -->|Yes| DC[Load Tab 2 principles<br/>from constitution.md]

    DC --> CMP[Compare proposed write<br/>against principles]
    CMP --> CK{Contradiction?}

    CK -->|No| WR[Write Tab 1 + Tab 2 + Tab 4-C<br/>via /build or auto-sync]
    CK -->|Yes| PA[PAUSE<br/>surface conflict to Danh]

    PA --> ASK["Ask: Approve override?<br/>(yes / no / revise)"]
    ASK --> WAIT[Wait for prompt + Enter]

    WAIT -->|yes| WR
    WAIT -->|revise| RV[Danh sends new prompt]
    WAIT -->|no| END[Stop, no write]

    RV --> P

    EX --> END2[End of turn]
    WR --> END2

    classDef gate fill:#FAEEDA,stroke:#854F0B
    class PA,ASK,WAIT gate
```

### Trio-touching detection

The trio-touching check is a lightweight regex/keyword scan over the prompt:

| Triggers trio check | Examples |
|--------------------|----------|
| Mentions Tab 1 concepts | "the prototype", "the screen", "the UI", "user can click" |
| Mentions Tab 2 concepts | "the objective", "the principle", "the rule" |
| Mentions Tab 4-C concepts | "this component", "the card", "the button", a known organism name |

If none match → drift check skipped. Saves ~60% of drift-check token cost.

### Drift check internals

The drift check is Option A — AI self-check. Specifically:

1. Read `.specify/memory/constitution.md` (cached after first read this session)
2. Extract the Principles section
3. For each principle, ask: "Does the proposed write contradict this?"
4. If any answer is yes → PAUSE
5. Token cost: ~700–1,500 per check (varies with principle count)

---

## 3. Manual sync flows (Tab 3, Tab 4-Screen, Tab 5)

These never auto-trigger. Danh runs the command explicitly.

### 3.1 `/sync.flow` — Tab 3 (User Flow)

```mermaid
flowchart LR
    A[Danh: /sync.flow] --> B[Read spec.md, plan.md]
    B --> C[Invoke craft-connect-flow skill]
    C --> D[Generate SVG flow diagram]
    D --> E[Generate user-stories list<br/>one per flow path]
    E --> F[Write to Tab 3 of template.html]
    F --> G[Confirm to Danh<br/>'Tab 3 updated, N stories generated']
```

User-stories generated alongside the flow act as the future test checklist (per Tab 3 guardrail #2).

### 3.2 `/handoff` — Tab 4 Screen view

```mermaid
flowchart LR
    A[Danh: /handoff] --> B[Check drift trio first<br/>via before_handoff hook]
    B --> C{Drift?}
    C -->|Yes| P[PAUSE — fix drift first]
    C -->|No| D[For each screen in Tab 1:<br/>extract elements]
    D --> E[For each element:<br/>resolve DS tokens + sizing]
    E --> F[Render 7:3 layout per screen]
    F --> G[Write to Tab 4 Screen view]

    classDef gate fill:#FAEEDA,stroke:#854F0B
    class P gate
```

The right panel only emits **spec tokens + sizing** — never code. Code stays in Tab 1.

### 3.3 `/sync.erd` — Tab 5

```mermaid
flowchart LR
    A[Danh: /sync.erd] --> B[Read spec.md, plan.md]
    B --> C[Extract entity-like nouns]
    C --> D[Generate Mermaid erDiagram]
    D --> E[Apply ERD guardrails<br/>PK / FK / cardinality checks]
    E --> F{All checks pass?}
    F -->|No| W[Warn Danh, write anyway with TODOs]
    F -->|Yes| G[Write to Tab 5]
```

---

## 4. Skill refresh flow

```mermaid
flowchart TD
    A[Danh: /skills.refresh] --> B[Read pinned tag from constitution.md]
    B --> C[git fetch --tags in ./.claude/skills/]
    C --> D[List tags newer than pinned]
    D --> E{Any newer?}
    E -->|No| Z[Confirm: already latest]
    E -->|Yes| F["Prompt: Pin to <new tag>?"]
    F --> G{Danh approves?}
    G -->|No| Z
    G -->|Yes| H[git checkout new tag]
    H --> I[Update constitution.md pinned_tag]
    I --> J[Verify required skills still present]
    J --> K{All present?}
    K -->|No| L[ROLLBACK to previous tag<br/>report missing]
    K -->|Yes| M[Confirm: pinned to new tag]
```

Rollback on missing skills protects against breaking changes in the external repo.

---

## 5. Drift audit flow (manual)

When Danh runs `/check.drift`:

```mermaid
flowchart TD
    A[Danh: /check.drift] --> B[Read constitution.md principles]
    B --> C[Read current Tab 1 contents]
    C --> D[Read current Tab 2 contents]
    D --> E[Read current Tab 4-C contents]
    E --> F[For each principle:<br/>check against each trio member]
    F --> G[Generate drift report]
    G --> H{Any drift?}
    H -->|No| Z[Report: clean]
    H -->|Yes| I[Report: list violations + locations]
```

This is the "did anything slip past the per-prompt check?" audit. Run after marathon sessions.

---

## 6. Token-cost data flow

A 50-turn session, scoped drift check:

```mermaid
flowchart LR
    A[50 prompts] --> B[~40 touch trio]
    A --> C[~10 don't touch trio]
    B --> D[Drift check: ~1000 tokens × 40<br/>= ~40K tokens]
    C --> E[No drift check<br/>= 0 tokens]
    D --> F[Total drift cost: ~40K]
    E --> F
    F --> G[NFR-1 ceiling: 30K]

    classDef warn fill:#FAEEDA,stroke:#854F0B
    class G warn
```

Note: the 40K estimate slightly exceeds NFR-1's 30K target. Mitigations:

| Mitigation | Savings |
|-----------|---------|
| Cache parsed principles in session | ~30% |
| Shorter principles (≤3 lines each) | ~20% |
| Skip drift check if last 3 turns were clean | ~25% |

These are post-Phase-7 optimizations. v1.0 ships with raw Option A.

---

## 7. Data dependencies summary

Compact view of what reads from what:

| Reader | Source(s) |
|--------|-----------|
| Drift check | `constitution.md` |
| Tab 1 (`/build`) | `spec.md`, `plan.md`, `tasks.md`, `design-system/` |
| Tab 2 overview | `spec.md` (Objectives), `constitution.md` (Principles) |
| Tab 2 user insights | `clarify.md`, external research artifacts (Danh-provided) |
| Tab 2 UI logic | `clarify.md` |
| Tab 3 (`/sync.flow`) | `spec.md`, `plan.md`, `craft-connect-flow` skill |
| Tab 4-Component | `plan.md`, `design-system/`, `design-component-build` skill |
| Tab 4-Screen (`/handoff`) | Tab 1 HTML, `design-system/`, `design-critics` skill |
| Tab 5 (`/sync.erd`) | `spec.md`, `plan.md`, ERD guardrails (this doc) |
| `/skills.refresh` | external repo only |
| `/check.drift` | `constitution.md`, current `template.html` |
