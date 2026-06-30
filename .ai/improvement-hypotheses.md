# AI Infrastructure Improvement Hypotheses

> Testable predictions about expected value from AI infrastructure changes.
> Each hypothesis is linked to a changelog entry and validated by periodic review.
>
> **Format:** See `.claude/skills/ai-improvement-tracker/SKILL.md`.
>
> **Status lifecycle:** PENDING → CONFIRMED | REFUTED | INCONCLUSIVE | SUPERSEDED

---

## 2026-06-30

### [SKILL-ADDED] flatpak-development reference skill
- **Category:** Quality
- **Hypothesis:** By front-loading the two dominant agent failure modes (network-during-build and over-broad `finish-args`) and forcing the `org.flatpak.Builder` + `flatpak-builder-lint` loop, we expect agent-authored Flatpak manifests to pass `flatpak-builder-lint` on the first attempt because the skill makes the exact checks Flathub CI runs explicit before the agent writes the manifest, rather than the agent discovering them through rejection.
- **Signal:** When packaging work begins on `armar-manager`, the first manifest draft passes `flatpak-builder-lint manifest`/`repo` with no rejection-grade findings (no `--filesystem=home`, no network in build, non-EOL runtime); few or no rework cycles attributable to the failure modes the skill names.
- **Risk:** The skill hardcodes mid-2026 runtime branch anchors (`25.08`, KDE `6.x`); if an agent treats these as values to paste rather than sanity-checks, it could emit an EOL runtime — the "verify-at-author-time" framing is meant to prevent this but may be skimmed.
- **Status:** PENDING
- **Changelog ref:** 2026-06-30 — SKILL-ADDED: flatpak-development reference skill

