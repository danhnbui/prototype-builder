# Front-end ticket template

A front-end ticket is the one page a developer opens to build one slice of a product: what to
build, in which states, with which edge cases, and how to tell it is done. This file is the
**single source of truth** for that structure. `ticket.py new` reads the `##` sections below (their
names, their order, whether each is required, and the tables they start from) and `ticket.py lint`
checks every ticket against them. Rename or reorder a section here and every new ticket follows.
Do not add a `##` heading that is not a ticket section; the explanation you are reading, and the
checklist at the end of this introduction, sit above the first section on purpose.

Section names are English and fixed. The text inside a section can be written in any language.

### Front matter

The first block of a ticket is a fenced block whose info string is `ticket`. It holds JSON with
sorted keys and a 2-space indent, and is written and refreshed by the tool, not by hand.

```json
{
  "components": [],
  "depends": ["T-sign-in"],
  "evidence": "annotation",
  "feature": "Account",
  "figma": null,
  "id": "T-profile-edit",
  "jira": null,
  "kind": "journey",
  "order": 20,
  "prototype": {"opens": "profile", "url": "https://example.com/prototype.html"},
  "rules": [],
  "scenarios": [],
  "screens": ["profile"],
  "source": {"digest": "0123456789abcdef0123456789abcdef01234567"},
  "title": "[Account] Edit profile details"
}
```

| Key | Meaning |
|---|---|
| `id` | Stable id: `T-` then kebab-case words. Never renumbered: deleting a ticket leaves every other id alone. Matches the file name. |
| `title` | `[Area] outcome phrase`. The area names where it lives, the phrase says what the user can do afterwards. |
| `feature` | The feature or epic the ticket belongs to. The index groups by it. |
| `kind` | `journey` (a flow across screens) · `component` (one reusable piece) · `rules` (behaviour and logic, little visible UI) · `region` (one part of a screen). |
| `order` | A number that sets the reading and build order in the index. Ties break by id. |
| `depends` | Ids of tickets that must be done first. Every id must have a ticket file. |
| `screens`, `components`, `rules`, `scenarios` | The project items this ticket is built from. Each must still exist. |
| `evidence` | `flow` or `annotation`. Which single form of evidence the Document section carries. |
| `prototype` | `url` is the base address of the live prototype. `opens` is the screen the link opens on. |
| `figma`, `jira` | A link, or null. |
| `source.digest` | A fingerprint of everything listed above at the time the ticket was written. When the project moves on, the ticket is reported as stale until someone reviews it and refreshes the digest. |

### Writing rules

- The body is read by people who cannot open the project's internals. Do not mention decision ids,
  lint codes, the registry file, or any render, spec or logic file path. Say what the product does.
- A required section is never left blank. If there is nothing to say, write one of the none words,
  alone: `None`, `N/A`, `Không có` or `Không áp dụng`.
- A table cell that does not apply says `N/A`. It is not left empty.
- Acceptance items are checkboxes (`- [ ]`) that someone who has not read the rest could verify.
- The Document section carries a prototype deep link (`?screen=<screen id>`) and exactly one
  evidence form.

### Pre-send checklist

- [ ] The title reads `[Area] outcome phrase`.
- [ ] Every required section is filled, or says None.
- [ ] States has all six rows, each filled or N/A.
- [ ] Every edge-case row has a message and a result.
- [ ] Roles is filled when the project has more than one role.
- [ ] Acceptance items can each be checked without reading anything else.
- [ ] Document holds a prototype link with `?screen=` and one evidence form, and the evidence file exists.
- [ ] Nothing in the body points at tool internals the recipient cannot open.
- [ ] Every id in Depends has a ticket.
- [ ] `python3 pb/tools/ticket.py lint <id>` is clean.

## Context

> **Required.** Why this ticket exists: the user's problem or goal, and where this slice sits in the feature. Two to four sentences.

## Scope

> **Required.** What this ticket delivers, which screens and components it touches, and what it deliberately leaves out.

## Solution

> **Required.** How the interface should work, step by step, in the order the user meets it. Describe behaviour, not implementation. Point at the prototype for look and feel.

## States

> **Required.** One row per state, always these six. Write N/A in a cell that does not apply.

| State | Appearance | Behaviour |
|---|---|---|
| Default | What the user sees first | What they can do |
| Loading | What shows while data is on its way | What is blocked meanwhile |
| Empty | What shows when there is nothing to list | The next action offered |
| Error | What shows when something fails | How the user recovers |
| Disabled | What shows when an action is unavailable | Why, and what unlocks it |
| No permission | What shows when the role may not use it | Where the user is sent or told |

## Edge cases

> **Required.** One row per case that changes what the user sees or can do. Preselected is what is already chosen when the case happens, Message is the exact text shown, Primary button is its label, Result is where the user ends up.

| Case | Preselected | Message | Primary button | Result |
|---|---|---|---|---|
| The email is already registered | The email typed so far | This email is already in use | Sign in | Stays on the form, the field is marked invalid |

## Roles

> **Required when the project has more than one role.** Which role sees, uses or is blocked from each capability. One column per role.

| Capability | role-a | role-b |
|---|---|---|
| Edit the profile | Yes | View only |

## Data & logic

> **Optional.** Inputs, validation rules, formats, ordering, and what is saved or sent when.

## Accessibility

> **Optional.** Focus order, keyboard use, labels, what is announced, contrast, motion.

## Acceptance

> **Required.** Checkboxes that make the ticket done. Each one is observable and tied to a scenario when one exists.

- [ ] A signed-in user can change their display name and sees it updated at once

## Open

> **Required.** Questions still unanswered, each with who can answer it. Write None when nothing is open.

## Document

> **Required.** Where to look. A prototype deep link with `?screen=<screen id>`, the place it opens at, and exactly one evidence form. Use `flow` (a hand-off page or step capture) or `annotation` (an annotated screenshot plus a numbered table, written here in the ticket).

- Prototype: https://example.com/prototype.html?screen=profile
- Opens at: Profile, with the edit button visible

Evidence form `flow`:

- Hand-off flow: handoff/tickets/T-profile-edit/flow.html

Evidence form `annotation`:

- Annotation: handoff/tickets/T-profile-edit/annotation.png

| # | Part | Spec |
|---|---|---|
| 1 | Display name field | 16px text, 48px high, placeholder shows the current name |

## Handoff notes

> **Optional.** Anything the receiving developer should know that is not a requirement: sequencing, risks, things already agreed in conversation.
