# 04 — Orchestrator

**Purpose**: Control flow. Which skill fires when. Where the HITL gates sit. How drift detection actually decides.

This is the file Claude Code consults during execution to know "what runs next."

---

## 1. Phase orchestration table

Maps each `/speckit.*` phase to which tab(s) it writes and which skills it consults.

| Phase command | Writes to | Consults skills |
|--------------|-----------|----------------|
| `/speckit.constitution` | Tab 2 → Principles, `constitution.md` (stack + DS lock) | none (Danh-led) |
| `/speckit.specify` | Tab 2 → Overview > Objectives, `spec.md` | `think-critique-prd`, `think-clarify` |
| `/speckit.clarify` | Tab 2 → UI Logic Trade-offs, User Insights, `clarify.md` | `ref-blueprint` |
| `/speckit.plan` | `plan.md`, prepares Tab 1 + Tab 4-C | `think-layout`, `think-logic`, `ref-prd` |
| `/speckit.tasks` | `tasks.md` (per-tab tasks) | `agent-orchestrate-tasks` |
| `/speckit.checklist` | `checklist.md` (pre-build gate) | `design-critics` |
| `/speckit.analyze` | Audit report (cross-doc consistency) | none |
| **`/build`** (custom) | Tab 1 (Prototype), Tab 4-C (Component view) | `think-layout`, `think-logic`, `design-component-build` |
| **`/sync.flow`** (custom) | Tab 3 (User Flow + user stories) | `craft-connect-flow` |
| **`/sync.erd`** (custom) | Tab 5 (ERD) | none |
| **`/handoff`** (custom) | Tab 4-S (Screen view) | `design-critics` |
| **`/skills.refresh`** (custom) | `.claude/skills/`, `constitution.md` pinned_tag | none |
| **`/check.drift`** (custom) | Drift report (no template write) | none |

---

## 2. Skill firing matrix

Maps trigger → skill → why → which tab(s) get touched.

| Trigger | Skill | Reason | Tab(s) |
|--------|-------|--------|--------|
| After `/speckit.specify` returns spec.md | `think-critique-prd` | Catch missing context before clarify | Tab 2 |
| Same trigger | `think-clarify` | Decide which ambiguities need user input | Tab 2 |
| `/speckit.clarify` running | `ref-blueprint` | Frame screen-level JTBD | Tab 2 |
| `/speckit.plan` running | `ref-prd` | Parse spec.md into structured plan input | Plan only |
| Same trigger | `think-layout` | Layout decisions for upcoming screens | Tab 1 prep |
| Same trigger | `think-logic` | State and rule decisions | Tab 1 prep |
| `/build` running | `think-layout`, `think-logic` | Per-screen layout + logic | Tab 1 |
| Same trigger | `design-component-build` | Component-variant rigor | Tab 4-C |
| `/sync.flow` running | `craft-connect-flow` | Multi-screen flow with conditions | Tab 3 |
| `/handoff` running | `design-critics` | Critique pass before declaring screen handoff-ready | Tab 4-S |
| `/speckit.checklist` running | `design-critics` | Final quality gate | checklist.md |
| Any task expected to spawn >2 subtasks | `agent-orchestrate-tasks` | Delegation framework | Variable |

### Required skills (must exist in cloned repo)

If any of these are missing at init, hard-fail:

- `think-critique-prd`
- `think-clarify`
- `ref-blueprint`
- `ref-prd`
- `think-layout`
- `think-logic`
- `design-component-build`
- `design-critics`
- `craft-connect-flow`
- `agent-orchestrate-tasks`

Optional skills (warned if missing but don't block):

- `craft-research` (used if Danh asks for competitor analysis)
- `think-critique-prd` extensions (heuristics packs, if any)

---

## 3. Drift detection logic (Option A, scoped)

### 3.1 Trigger

A prompt triggers drift detection IF AND ONLY IF the prompt's text matches any pattern in the trio-touching detector.

**Detector pseudocode**:

```
function touches_trio(prompt: str) -> bool:
    # Tab 1 patterns
    if re.search(r'\b(prototype|screen|page|UI|view|user (can|will|sees))\b', prompt, re.IGNORECASE):
        return True
    # Tab 2 patterns
    if re.search(r'\b(objective|principle|rule|principle|goal|hypothesis)\b', prompt, re.IGNORECASE):
        return True
    # Tab 4-C patterns: known organism names (Danh-provided per project)
    for organism in current_organism_names():
        if organism.lower() in prompt.lower():
            return True
    return False
```

Tab 3 / Tab 4-S / Tab 5 keywords (e.g., "flow", "ERD", "handoff", "schema") do NOT trigger the check — those tabs are decoupled by design.

### 3.2 Check procedure

When `touches_trio(prompt) == True`:

```
1. Load .specify/memory/constitution.md (cache after first read this session)
2. Extract the "Principles" section (numbered list)
3. Plan the proposed write
4. For each principle in order:
     ask internally: "Does this proposed write contradict principle N?"
     if yes:
       collect the violation
5. If any violations collected:
     PAUSE
     print proposed write
     print violations (numbered, with principle text)
     ask: "Approve override? (yes / no / revise)"
     wait for prompt + Enter
6. If no violations:
     proceed with write
```

### 3.3 Pause-and-ask UX

When the pause fires, Claude Code should print exactly this shape:

```
⏸ DRIFT DETECTED

Proposed write:
  [tab affected]: [summary of write]

Violates principle(s):
  #N — "[principle text]"
     because: [one-line reason]

Approve override?  (yes / no / revise)
```

Then stop and wait. Do not continue. Do not interpret silence as approval.

### 3.4 Edge cases

| Situation | Behavior |
|-----------|----------|
| Constitution.md missing | HARD FAIL: "Run /speckit.constitution first" |
| Principles section empty | Treat as no principles → no drift check possible → proceed but warn |
| Prompt mentions trio keywords but doesn't actually write | Skip check (no write = no drift possible) |
| Multiple violations in one prompt | Surface ALL of them in the pause, not just the first |
| Danh says "revise" | Stop, wait for new prompt; new prompt re-enters at step 1 |

---

## 4. HITL gate placement

The gates from HANDOFF.md, expanded:

### G0 — Pre-init skill repo confirmation

**When**: Before running Phase 1 of the execution plan.
**Trigger**: Always — Phase 0 is Danh's side task.
**Action**: Wait for explicit "skill repo ready" message from Danh.
**Pass condition**: Danh confirms in chat.
**Fail condition**: Skip this and run init anyway → guaranteed failure at G4.

### G1 — Drift detected

**When**: Drift check returns violations.
**Trigger**: Any trio-touching prompt with a contradiction.
**Action**: Pause-and-ask per section 3.3.
**Pass condition**: Danh types `yes` + Enter.
**Fail condition**: Proceed silently → permanent drift in Tab 2.

### G2 — Design system override

**When**: A `/build` or `/handoff` attempts to use styles outside `./design-system/`.
**Trigger**: Any inline style, any external CSS import, any color hex not in tokens.json.
**Action**: Pause. Show offending styles. Ask: `"Extend DS or override this once? (extend / override / cancel)"`
**Pass condition**: Danh chooses extend or override.
**Fail condition**: Silently inject random styles → DS drift.

### G3 — Code stack switch

**When**: A `/build` attempts to use a language or framework other than the one locked at init.
**Trigger**: Detected by checking generated code against constitution.md's stack lock.
**Action**: Pause. Show the attempted change. Ask: `"Switch stack from X to Y? (yes / no)"`
**Pass condition**: Danh approves AND updates constitution.md.
**Fail condition**: Silently mix stacks → unrunnable prototype.

### G4 — Skill repo unreachable

**When**: `specify init` runs but skill repo doesn't exist or is private without auth.
**Trigger**: `git clone` returns non-zero.
**Action**: HARD FAIL with the FR-5 error message. Do not proceed.
**Pass condition**: Danh fixes repo access and re-runs init.
**Fail condition**: Try to proceed without skills → every skill-firing trigger throws.

### G5 — Per-task check-in (Phases 1–6)

**When**: After each task in the execution plan.
**Trigger**: Task marked done by Claude Code.
**Action**: Brief check-in: "Task X.Y done. Outputs: [list]. Proceed to X.Z?"
**Pass condition**: Danh says yes or stays silent for >N minutes (autoproceed).
**Fail condition**: Skip the check-in → no rollback point if a task is wrong.

### G6 — Phase 7 final acceptance

**When**: All Phase 7 sub-tasks complete.
**Trigger**: Acceptance test run.
**Action**: Show full test results. Ask: `"Ship the preset? (yes / no / iterate)"`
**Pass condition**: Danh approves.
**Fail condition**: Declare ship without approval → premature release.

---

## 5. Failure modes & recovery

| Failure | Symptom | Recovery |
|---------|---------|----------|
| Skill repo down mid-session | `/skills.refresh` fails | Stay on current pinned tag; warn Danh; continue |
| Skill repo down at init | `specify init` fails at clone | G4 path: hard fail, Danh fixes |
| `constitution.md` corrupted | Drift check throws | Show parse error; ask Danh to regenerate |
| Two principles contradict each other | Drift check has logic conflict | Surface both principles to Danh; ask which wins |
| `template.html` exceeds 3,000 lines | NFR-4 threshold crossed | Flag for migration to Vite scaffold; don't auto-migrate |
| DS lock violated by external library | G2 fires every prompt | Suggest extending DS to include needed tokens |
| Tab 1 references organism not in Tab 4-C | Trio inconsistency | Surface as drift; ask Danh to add organism or remove reference |
| `tasks.md` declares an unknown skill | Skill firing throws | Surface missing skill; suggest `/skills.refresh` |

---

## 6. Session lifecycle

A typical Claude Code session, end to end:

```
1. Open repo
2. Read HANDOFF.md (this package) if first time
3. Check constitution.md exists → if not, run /speckit.constitution
4. Wait for Danh's first prompt
5. For each prompt:
     a. Detect trio-touching (section 3.1)
     b. If yes: load principles, drift check (section 3.2)
     c. If drift: pause-and-ask (section 3.3); on yes → continue
     d. Determine which command/skill to invoke (sections 1 + 2)
     e. Execute, write to applicable tab(s)
     f. Auto-sync trio tabs if relevant
     g. Confirm to Danh: "Updated Tab X, Y, Z"
6. On /sync.flow, /sync.erd, /handoff → run section 3 of data-flow.md
7. On /skills.refresh → run section 4 of data-flow.md
8. On /check.drift → run section 5 of data-flow.md
9. End of session: no special teardown
```

---

## 7. What Claude Code must NEVER do

(Reinforces HANDOFF.md hard rules with orchestrator-specific detail)

1. **Never silently update Tab 2 without firing a drift check** if the update was triggered by a prompt rather than a skill output.
2. **Never call a skill not listed in section 2** without escalating to Danh.
3. **Never write to a `.specify/` file other than the ones documented in `02-architecture.md` section 3.**
4. **Never proceed past G1 just because the violation seems minor.** The whole point of G1 is that Danh decides what's minor.
5. **Never modify the pinned tag in `constitution.md` outside of `/skills.refresh`'s approval flow.**
6. **Never bypass the trio-touching detector** by checking drift on every prompt "just to be safe." The scoping is deliberate — unscoped drift checks burn NFR-1.
7. **Never invoke `agent-orchestrate-tasks` for fewer than 3 subtasks.** That skill is for genuine multi-step work; cheap to fire, expensive in context.

---

## 8. Where this document gets updated

Triggers for revising `04-orchestrator.md`:

| Change | Update needed |
|--------|--------------|
| New skill added to required set | Section 2 + section 3.1 |
| New custom command added | Section 1 + 2 |
| Drift detection algorithm changes | Section 3 |
| Gate added or removed | Section 4 |
| Failure mode discovered in practice | Section 5 |

Any of these → bump to v1.1, re-review with Danh.
