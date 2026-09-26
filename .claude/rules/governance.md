---
paths:
  - "**"
---

# Governance: a pointer, not a copy

Isotope follows the Valence Canon. It does not restate it.

- **Doctrine home:** `../Valence/.claude/rules/governance.md` (C-1..C-12: one
  fact one home, status-never-in-prose, stamp-or-hearsay, the Canon Flag duty,
  frozen list, amendment ritual, American English, comments-are-constraints).
  Read it there; a copy here would be a second home for the same fact, which
  C-1 forbids.
- **Wire numbers, protocol behavior:** the Valence repo
  (`spec/registry/registry.yaml`, `spec/SPEC.md`). Never a code-local magic
  number for anything wire-visible. A gap in the spec is fixed in the Valence
  repo FIRST, then coded against here. `docs/DESIGN.md` names each RFC it is
  waiting on.
- **The Valence repo is READ-ONLY from here.** Changes there are RFCs.
- **Volatile truth** (what is measured, what is built, open questions) lives
  on this repo's own dev board: `bd`, prefix `iso`. Not in prose here.
- **Design rulings** live in `docs/DESIGN.md`, one home.

Isotope is an ACCESSORY. It never commands a machine's motion and never
talks to a client. It declares itself to a hub, obeys the hub, and fails safe
without it.
