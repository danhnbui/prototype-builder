# Decisions — Property Auth

> The why-log. One entry per trade-off resolved, gate override, or lock change. Newest first.
> Appended automatically by `/pb:clarify` (UI Logic Trade-offs) and by the build loop on a
> drift-gate override.

<!-- Template entry — copy below this line:

## YYYY-MM-DD — <short title>
- **Decision:** <what was chosen>
- **Why:** <one or two lines>
- **Alternatives:** <what was rejected, and why not>
- **Affects:** <screens / components / tokens / logic>

-->

## 2026-06-05 — OTP vs magic link
- **Decision:** 6-digit OTP
- **Why:** Stays in-app on mobile; lower abandon than leaving for an email client.
- **Alternatives:** Magic link (rejected — context switch)
- **Affects:** Prototype, UX Design
