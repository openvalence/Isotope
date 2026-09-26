# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## What this repo is

Design home for Isotope, the Valence accessory firmware. Nothing is built
yet. `README.md` says what Isotope is; `docs/DESIGN.md` holds the design
rulings and the open questions; read it before proposing anything.

## Pointers, not rules

- **Canon:** `../Valence/.claude/rules/governance.md`, via the pointer in
  `.claude/rules/governance.md`. Wire truth is `../Valence/spec/`. The Valence
  repo is READ-ONLY from here; what Isotope needs from it is an RFC.
- **Volatile truth:** this repo's dev board (`bd`, prefix `iso`). Measured
  numbers, what is built, pending rulings. Never status in prose.
- **Hub-side work** (beacon, join, declaration store, relationships) lands in
  `../Nucleus` and is filed on its board, never coded from here.

## Conventions

- American English throughout.
- Comments are constraints (what the code cannot show), not narration; the
  story goes in `docs/` with a pointer.
- **Host rule: use the Bash tool only, never the PowerShell tool.** It opens
  terminal windows on the operator's screen.
- Never add a `Co-Authored-By: Claude ...` (or similar AI co-author) trailer
  to git commit messages in this repo.
