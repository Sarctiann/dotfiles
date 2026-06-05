# AGENTS.md — HST Work Profile

This directory is the **canonical working
directory for all Augment agent artifacts** related to HST projects.

## Language

- All interactive messages to the user must be in **Spanish**, brief and to the point.
- Everything persisted to disk (file names, code, comments, documentation, commit messages, plans, etc.)
  must be in **English**, unless the user explicitly requests otherwise.

## Git

- Never create a git commit unless the user explicitly asks you to.

## Response Style

- Keep responses concise. List file changes as bullet points without explanations or justifications,
  unless the user explicitly requests them.
- Do not override response rules defined in sub-directory `AGENTS.md` files or loaded Skills.

## Workflow

- Check for `AGENTS.md` files in sub-directories when working on files inside them, and follow those too.
- You may modify any `AGENTS.md` file to keep it aligned with the project's current rules and conventions.
- Before using any skill, assess whether the task actually requires it. If it does, use the skill without asking.
- If the user says "Do it without asking", skip all confirmation prompts and proceed autonomously based on
  your best understanding of their intent.

---

## ⚠️ CRITICAL RULE: File Storage Location

**ALL agent-generated files MUST be stored in the `.augment_work_profile` directory,
NOT in `~/.augment/`.**

This includes:

| Artifact               | Path                                           |
| ---------------------- | ---------------------------------------------- |
| Plans                  | `<work-profile>/plans/`                        |
| Notes / scratch files  | `<work-profile>/`                              |
| Any other agent output | `<work-profile>/`                              |

### ❌ NEVER use

- `~/.augment/plans/`
- `~/.augment/` (any subdirectory)

### ✅ ALWAYS use

- `./plans/` for plan files
- `./` for any other work artifacts

**Rationale**: `~/.augment/` is a system-level directory shared across all projects and
users. This directory is project-scoped, version-control-adjacent,
and visible to the team working on HST projects.

---

## Agentic Skills

**Before responding to any request, ALSO check `./skills/` for a matching skill.**
If a skill matches the request, follow it exactly — user-level skills take precedence over project-level skills.

---

## Directory Structure

```
.augment_work_profile/
├── AGENTS.md          ← This file (rules for agents)
├── skills/            ← User-level skills (checked on every request)
│   └── *.md
└── plans/             ← Plan files for features, refactors, investigations
    └── plan-*.md
```

---

## Plan File Conventions

- **Naming**: `plan-<feature-or-ticket>-<YYYY-MM-DD>.md`
- **Example**: `plan-kaia-thread-cc15571-2026-05-04.md`
- Plans should include: feasibility verdict, architecture analysis, files to change,
  implementation steps as checkboxes.
- Mark steps `[x]` as they are completed during implementation.
