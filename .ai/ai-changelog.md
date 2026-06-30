# AI Infrastructure Changelog

> Reverse-chronological log of changes to the project's AI infrastructure:
> skills, conventions, rules, and workflow modifications.
>
> **How entries are added:** Automatically by AI workflows or manually via the `ai-changelog` skill.
>
> **Format:** Each entry follows the structured format defined in `.claude/skills/ai-changelog/SKILL.md`.

---

## 2026-06-30

### SKILL-ADDED: flatpak-development reference skill
- **What:** Created `.claude/skills/flatpak-development/` (SKILL.md + 3 reference files) — expert, research-backed guidance for AI agents authoring Flatpak manifests, building/linting with `org.flatpak.Builder`, configuring least-privilege sandboxes/portals, packaging Python/Qt/KDE apps with offline pinned dependencies, and publishing to Flathub. Auto-loads as background knowledge on Flatpak manifests, `finish-args`, `*.metainfo.xml`, and Flathub submissions.
- **Why:** `armar-manager` (PySide6/Kirigami desktop app) is the natural Flatpak target, and agents reliably produce broken manifests (network-during-build, sandbox holes, stale runtimes). The skill encodes the failure modes Flathub CI rejects so the first attempt passes. Includes the 2026 Flathub AI-authored-submission ban so agents don't lead users into a rejected submission.
- **Files:** `.claude/skills/flatpak-development/SKILL.md`, `.claude/skills/flatpak-development/references/manifest-reference.md`, `.claude/skills/flatpak-development/references/sandbox-permissions.md`, `.claude/skills/flatpak-development/references/flathub-publishing.md`, `CLAUDE.md`
- **Affected workflows:** None (standalone auto-loaded reference); created via skill-creation-workflow.

