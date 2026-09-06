---
name: pomogator-ui-review
description: >-
  Reviews Pomogator Mini App UI for production readiness: system theming,
  responsive layout, Notion-like document rendering, and anti-vibe-code quality.
  Use after frontend UI iterations or when asked to evaluate Mini App design.
---

# Pomogator Mini App UI review

Read `frontend/src/main.tsx`, `frontend/src/document.tsx`, `frontend/src/style.css`,
and `frontend/index.html`. Optionally skim related CSS/theme helpers.

## Verdict format (required)

Return exactly:

```
VERDICT: BLOCKED | NEEDS_WORK | SHIP
Score: N/10
```

Then 3–8 bullets of findings. If `SHIP`, one short sentence why. If not, list
**must-fix** items only (no nice-to-haves unless they block ship).

## Pass criteria (all required for SHIP)

1. **System colors** — UI uses Telegram theme vars and/or `prefers-color-scheme`;
   no hard-coded light-only branding that breaks dark mode; `color-scheme` set.
2. **Responsive** — readable on ~360px and ≥1024px; no horizontal overflow;
   touch targets ≥40px; desktop uses a comfortable reading width (not a stretched phone layout).
3. **Notion-like document** — real `ul`/`ol`, heading scale, callout, quote, divider,
   rich text emphasis; content is the hero, not chrome.
4. **Anti-vibe** — no decorative gradient blobs, no fake trust pills/emoji walls,
   no purple/cream AI clichés, no excessive glassmorphism/multi-shadow cards.
5. **Navigation** — Back + Home always available; paywall reachable and clear.
6. **Code quality** — no obvious broken states; theme applied before paint where possible.

## Fail examples

- Teal marketing hero with floating orb on a documentation page
- Orphan `<li>` without list wrappers
- Paywall only reachable from one obscure path
- Desktop content full-bleed edge-to-edge with 14px type
