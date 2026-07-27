# Design system (web UI)

> **Status:** ✅ living reference. The visual language of the web app, extracted
> from `webapp/frontend/src/index.css`. **Consult this before adding or
> changing any UI element**; when you deviate deliberately, update this file in
> the same PR. Single stylesheet, no CSS framework — keep it that way.
>
> **Live style guide: `/styleguide`** (dev-facing route, not in the nav —
> `pages/StyleGuide.tsx`). Every token, control, badge and pattern rendered by
> the real classes, token hexes read from the stylesheet at runtime, so it
> cannot drift. When this file and that page disagree, the page is right —
> then fix this file.

## Principles

- **One dark theme.** Near-black page, slightly lighter panels, 1px hairlines.
  No light mode, no theme switching.
- **Semantic colour only.** Colour communicates status or action, never
  decoration. Everything else is greyscale.
- **Rows of controls are uniform.** Any group of side-by-side controls shares
  one height, padding, and radius (see `.actions`). Never hand-tune a single
  control's size inside a row — that was the bug that prompted this file.
- **Density over chrome.** Small font sizes (12–15px), tight paddings, borders
  instead of shadows (the modal is the only shadow).

## Tokens (`:root`)

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#0f1115` | page background |
| `--panel` | `#171a21` | cards, rows, controls, topbar |
| `--line` | `#262b36` | ALL borders and hairlines — there is no `--border` token; never invent one |
| `--text` | `#e6e8ec` | primary text |
| `--muted` | `#8b93a1` | secondary text, labels, metadata |
| `--accent` | `#5b9bff` | links, active nav, primary action, hover borders, progress |
| `--open` / `--applied` / `--rejected` / `--suspected` / `--closed` | green / accent / red / yellow / grey | status badges only |

One-off colours in use (acceptable, don't multiply): `#c8f7c5` salary text,
`#f7a8a8` error text, `#20262f` pill fill, `#3a4250` "updated" badge,
`#0f1115` badge text.

## Typography

- Stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`,
  base **15px/1.5**.
- Scale: 24px page `h1` (20px under 520px) · 17px section/modal headings and
  brand · 14px nav, filters, facts, field labels · 13px buttons, row metadata ·
  12px pills/badges/`button.small`.
- Weights: 700 brand + company names, 600 badges + primary action. No italics
  except rendered ad Markdown.

## Shape & spacing

- Radius: **8px** interactive controls (buttons, inputs, selects, links-as-
  buttons, banner) · **10px** cards/rows/panels · **12px** modal · **999px**
  pills/badges. No other values.
- Gaps: 8px between controls in a row; 10–14px metadata gaps; 14–16px between
  blocks; `main` is `max-width: 880px` centred, 16px padding.
- Borders: `1px solid var(--line)` everywhere a surface meets the page.

## Controls

- **Neutral button / link-as-button** — `button` element or `<a class="btn">`
  (anchors that *act* like buttons, e.g. downloads): panel bg, `--line`
  border, radius 8, 13px, padding 7px 12px. Hover = accent border (border
  colour is THE hover affordance; no bg change). Disabled = `opacity .5`.
- **Primary action** — `.apply`: accent bg, white 600 text, accent border so
  its box height matches neutral buttons exactly. At most **one** per view.
- **Action row** — `.actions`: flex row, 8px gap; `.actions > *` forces every
  child (buttons, `.apply`, `a.btn`) to the same 13px / 8px 14px / radius-8
  box. Put any new detail-page control inside it and it sizes itself.
- **Small button** — `button.small`: 12px, inline with headings.
- **Inputs/selects** — panel bg, `--line` border, radius 8, 14px, padding
  8px 10px (`.filters`, `.field`).
- **Badges** — status pills, 999px radius, semantic bg + dark text.
  **Pills** — neutral count/tag chips (`#20262f` fill).

## Patterns

- **List row** (`.row`): panel card, radius 10, accent border on hover =
  clickable. Company 700 + title, then 13px muted `.row-meta` line.
- **Detail page**: `.back` link → `h1` → muted `.sub` with badge → `.facts`
  (hairline-bounded emoji facts strip) → `.actions` → `.ad` / `.notes` panels.
- **Modal**: fixed backdrop `rgba(0,0,0,.55)`, panel radius 12 + shadow,
  `min(560px, 92vw)`, top-aligned at 12vh.
- **Feedback**: `.muted` for loading/empty, `.error` red text inline, button
  label swaps for transient state ("Copied ✓" — 2s reset), topbar progress bar
  for long operations.
- **Icons — two distinct roles, don't mix them:**
  - *Controls* (buttons, links-as-buttons): inline SVG outlines from
    `components/Icon.tsx` (Lucide paths pasted in — still no package/icon-font
    dependency). 16px leading (14px for trailing indicators like
    external-link), `stroke="currentColor"` stroke-2, 6px gap (baked into the
    `button, a.btn` rule). Raw Unicode glyphs (⧉ ⬇ ↻) in captions are
    banned — they render at text size/weight and vary per platform.
  - *Data labels* (facts strip, list-row metadata): emoji (📍 🎚️ 💷) are the
    house style — they label values, not actions.

## Adding new UI — checklist

1. Reuse an existing class before writing a new one; extend a selector list
   (`button, a.btn`) rather than duplicating a ruleset.
2. Only `var(--…)` colours from the token table (semantic one-offs above are
   grandfathered, not precedent).
3. Radius from {8, 10, 12, 999}; borders always `--line`; hover = accent
   border.
4. New control in an existing row → it must inherit the row's sizing
   (`.actions > *`), not carry its own.
5. Verify visually: `npm run build`, serve locally, screenshot at desktop and
   ≤520px widths (the one breakpoint) before shipping.
