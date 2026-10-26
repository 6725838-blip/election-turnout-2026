# Design system — election night studio

## World
Israeli civic election-night control room: cool paper, deep ink, amber live accent. Not SaaS blue, not cream/terracotta, not purple gradients.

## Tokens
- Paper: `#e6e9e7` page · `#f7f8f7` surface · `#ffffff` elevate
- Ink: `#0b1218` · muted `#3d4f5c`
- Live accent: `#b86a0a` (amber) · positive `#0d6b58` · negative `#9a3040`
- Rules: `#c5d0cb` hairlines · radius `4px` (utilitarian, not soft SaaS)

## Type
Heebo only (Hebrew). Body ≥15px. Display numbers heavy + tabular. No eyebrow/kicker above titles.

## Layout
One composition: dark masthead with countdown + live status, then group board (list on a single surface) beside national rate as the sole large metric. Insights, day chart, locality table follow. No nested cards; group accent is a small swatch, not a thick side stripe.

## Motion
One intentional moment: masthead settle on load. Live connection uses a restrained pulse on the status dot only. Honor `prefers-reduced-motion`.
