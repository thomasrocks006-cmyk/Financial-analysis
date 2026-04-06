# Bloomberg Terminal UI — Implementation Handoff
## Meridian Research Terminal · Session 19 → v2.0

---

## What This Does

Replaces the generic dark-blue AI app aesthetic with a full Bloomberg Terminal-style
interface. Pure black background, Bloomberg orange (#FF6600) accent, Courier New
monospace throughout, yellow field labels (#FFFF00), ALL CAPS everywhere, dense data
tables with no padding waste, command-line top bar with live market ticker.

Also fixes the two blockers from the gap analysis:
- `/runs/new` page (users couldn't start a run)
- `/runs` list page (Active Runs link was 404ing)

---

## Codespaces Setup — Run These First

```bash
# Open terminal in Codespaces, navigate to frontend
cd /workspaces/Financial-analysis/frontend

# Install dependencies (if not already done)
npm install

# Start dev server
npm run dev
# App runs at http://localhost:3000
```

---

## Files to Replace — In This Order

### 1. Design Tokens (do this first — everything inherits from here)

**`frontend/src/app/globals.css`** ← replace entirely

Copy `globals.css` from this handoff package. Key changes:
- All color variables repointed to Bloomberg palette
- `--text-label: #ffff00` added (new token for field labels)
- `--accent-faint`, `--error-faint`, `--success-faint` added (panel backgrounds)
- `--border-2` added (inner dividers, thinner than outer borders)
- `font-family` changed from Inter to `'Courier New', 'Lucida Console', monospace`
- `.report-content` table styles updated for Bloomberg table treatment
- No more `rounded-xl` anywhere — sharp corners throughout

After saving this file, hot-reload will immediately re-skin the entire app.
The existing components use `var(--accent)`, `var(--surface)` etc. so they
all pick up the new values automatically.

---

### 2. Layout Shell

**`frontend/src/components/layout/sidebar.tsx`** ← replace entirely

Copy `sidebar.tsx` from this handoff. Changes:
- Brand: "MERIDIAN / RESEARCH TERMINAL" replaces BarChart3 icon + "AI Research Platform"
- Run status chip: amber progress bar, S07/15 counter, stage name — all in orange
- Nav items: ALL CAPS, F-key shortcuts shown on right, no Lucide icons
- Active state: orange text + faint orange background, no rounded corners
- Footer: "SESSION 19 — v2.0 / AU MARKET · JPAM"
- Now uses `STAGE_COUNT` constant from types.ts (fixes hardcoded 15)

**`frontend/src/components/layout/top-bar.tsx`** ← replace entirely

Copy `top-bar.tsx` from this handoff. Changes:
- Bottom border becomes 2px solid orange (Bloomberg's signature chrome line)
- Left side: `>` command prompt — type a screen name + Enter to navigate
  (DASHBOARD, NEW RUN, RUNS, SAVED, SETTINGS — all wired to router.push)
- Centre: live run status with pulsing dot, stage counter, current stage name
- Right: rotating market ticker (SPX, NDX, ASX200, NVDA etc.) with green/red delta
- Far right: live AEST clock, updates every second

---

### 3. Core Components

**`frontend/src/components/ui/metric-card.tsx`** ← replace entirely

Copy `metric-card.tsx` from this handoff. Changes:
- No rounded corners (was `rounded-xl`)
- Label: yellow (`--text-label`) ALL CAPS + wide letter spacing
- Value: large mono number, colour driven by `trend` prop or explicit `valueColor`
- Trend indicator: ▲▼ symbols instead of arrows
- Removed icon prop (not Bloomberg-style)

**`frontend/src/components/pipeline/pipeline-tracker.tsx`** ← replace entirely

Copy `pipeline-tracker.tsx` from this handoff. Changes:
- Dense table layout: S# | STAGE NAME | STATUS | DUR columns
- Status column: CHECK/RUN/FAIL/WAIT abbreviations + symbolic prefix (✓ ► ✗ ○)
- Running stage: orange text, pulsing ► symbol, faint orange background
- Completed stages: green ✓, muted text
- Pending stages: gray, visually de-emphasised
- Progress bar: 1px orange line, not 6px rounded pill
- No Lucide icons — pure text/symbol
- Uses `STAGE_COUNT` constant (no hardcoding)
- Animating pulse uses local useState, not CSS class alone

---

### 4. New Pages — Fixes Both Blockers

**`frontend/src/app/runs/new/page.tsx`** ← CREATE THIS FILE (directory + file)

```bash
mkdir -p frontend/src/app/runs/new
```

Copy `runs-new-page.tsx` from this handoff → save as `page.tsx`.

Features:
- Ticker input: type + Enter to add, click chip to remove
- Four preset universe buttons: AI COMPUTE, AI INFRASTRUCTURE, POWER & ENERGY, ASX TECH
- Model selector: toggle buttons for the three Claude models
- Market selector: AU / US / GLOBAL / MIXED toggle
- Optional run label field
- Error state: Bloomberg red bordered box with error text
- Submit calls `startRun()` from api.ts then redirects to `/runs/{run_id}`
- Cancel button returns to previous page

**`frontend/src/app/runs/page.tsx`** ← CREATE THIS FILE

Copy `runs-page.tsx` from this handoff → save as `page.tsx`.

Features:
- 4-panel stat row: RUNNING / QUEUED / COMPLETED / FAILED with coloured counts
- Full runs table: Run ID (links to detail) · Universe · Status · Stage · Created · DEL
- Running rows highlighted with faint orange background + pulsing dot
- DEL button wired to `deleteRun()` (the cancel/abort gap is now fixed)
- Auto-refreshes every 3 seconds via React Query `refetchInterval`

---

### 5. Dashboard

**`frontend/src/app/page.tsx`** ← replace entirely

Copy `dashboard-page.tsx` from this handoff → save as `page.tsx`.

Changes:
- Header: "MERIDIAN RESEARCH TERMINAL" + "AI INFRASTRUCTURE PIPELINE — JPAM AU MARKET"
- Stat panels: 4-up grid with 1px gap (Bloomberg panel divider pattern)
- Run table: dense, monospace, no rounded corners, alternating row tints
- Added "SAVED REPORTS" section below run table
- All timestamps use existing `formatTimestamp` util

---

## After All Files Are Replaced

```bash
# In frontend/
npm run dev

# Check for TypeScript errors
npx tsc --noEmit

# If you get a font warning about Courier New not loading,
# that's fine — it falls back to Lucida Console then system monospace.
# No CDN font needed.
```

---

## What Still Needs Building (From Gap Analysis)

These were identified in the gap analysis and are NOT in this handoff.
Tackle them in this order after the visual redesign is applied:

| Priority | File | Gap |
|----------|------|-----|
| HIGH | `components/quant/quant-panel.tsx` | Add portfolio weight bar chart, factor exposure bars, drawdown chart using recharts (data is already in the store) |
| HIGH | `app/runs/[run_id]/page.tsx` (stages tab) | Call `getStageDetail()` and render actual output, not "available via API" |
| MED  | `components/ui/skeleton.tsx` | Build skeleton shimmer component, add to all loading states |
| MED  | `app/runs/[run_id]/page.tsx` (audit tab) | Remove raw JSON `<details>` block, replace with structured IC vote table |
| LOW  | `components/layout/top-bar.tsx` | Add "clear" button to dismiss stale run status after navigation |
| LOW  | `app/runs/[run_id]/page.tsx` | Add copy-to-clipboard button next to run ID |
| LOW  | `components/layout/sidebar.tsx` | Add hamburger + slide-in drawer for mobile |

---

## Design Token Reference

Use these in any new components you build:

```css
/* Backgrounds */
var(--background)    /* #000000 — pure black */
var(--surface)       /* #0a0a0a — panel background */
var(--surface-2)     /* #111111 — table header / elevated surface */
var(--surface-3)     /* #1a1a1a — deeply nested surfaces */
var(--accent-faint)  /* #1a0d00 — orange tint background (running rows etc.) */
var(--error-faint)   /* #1a0000 — red tint background */
var(--success-faint) /* #001a0a — green tint background */

/* Borders */
var(--border)        /* #444444 — panel/card borders */
var(--border-2)      /* #2a2a2a — row dividers, inner lines */

/* Text */
var(--text-primary)   /* #ffffff — primary data values */
var(--text-secondary) /* #888888 — secondary content */
var(--text-muted)     /* #555555 — timestamps, inactive items */
var(--text-label)     /* #ffff00 — field labels (Bloomberg yellow) */

/* Semantic */
var(--accent)         /* #ff6600 — Bloomberg orange, primary interactions */
var(--accent-hover)   /* #ff8533 — hover state */
var(--success)        /* #00cc44 — positive values, completed */
var(--error)          /* #ff3333 — negative values, failed */
var(--warning)        /* #ffaa00 — queued, caution */
var(--info)           /* #00ccff — cyan, durations, secondary highlights */
```

### Typography patterns

```tsx
// Section header (orange, ALL CAPS)
<span className="text-[var(--accent)] text-[10px] tracking-[.1em]">PIPELINE STATUS</span>

// Field label (yellow, ALL CAPS)
<span className="text-[var(--text-label)] text-[9px] tracking-[.1em]">QUALITY SCORE</span>

// Data value (white, mono)
<span className="text-[var(--text-primary)] text-xl tabular-nums">8.4/10</span>

// Positive number
<span className="text-[var(--success)] tabular-nums">+2.41%</span>

// Negative number
<span className="text-[var(--error)] tabular-nums">-3.2%</span>

// Muted secondary
<span className="text-[var(--text-muted)] text-[10px] tracking-[.06em]">14:22:41</span>

// Run ID / ticker (orange link)
<span className="text-[var(--accent)] text-[11px]">NVDA</span>
```

### Layout patterns

```tsx
// Panel with Bloomberg header bar
<div className="border border-[var(--border)]">
  <div className="bg-[var(--surface-2)] border-b border-[var(--border)] px-3 py-2">
    <span className="text-[var(--accent)] text-[10px] tracking-[.1em]">PANEL TITLE</span>
  </div>
  {/* content */}
</div>

// Stat grid (Bloomberg panel-divider style)
<div className="grid grid-cols-4 border border-[var(--border)]"
     style={{ gap: "1px", background: "var(--border)" }}>
  <div className="bg-[var(--surface)] px-4 py-3">
    <div className="text-[var(--text-label)] text-[9px] tracking-[.1em] mb-2">LABEL</div>
    <div className="text-2xl tabular-nums text-[var(--accent)]">42</div>
  </div>
</div>

// Dense table row
<div className="grid px-3 py-2 border-b border-[var(--border-2)]"
     style={{ gridTemplateColumns: "2fr 2fr 90px 80px" }}>
  ...
</div>

// Running state row
<div className={cn(
  "border border-[var(--border-2)]",
  status === "running" && "bg-[var(--accent-faint)]"
)}>

// Action button (Bloomberg style)
<button className="px-4 py-1.5 bg-[var(--accent)] text-black text-[10px] tracking-[.1em] hover:bg-[var(--accent-hover)]">
  INITIATE [GO]
</button>

// Ghost button
<button className="px-4 py-1.5 border border-[var(--border)] text-[var(--text-muted)] text-[10px] tracking-[.08em] hover:border-[var(--accent)] hover:text-[var(--accent)]">
  CANCEL
</button>
```

---

## Common Gotchas

1. **No `rounded-*` classes on new components.** Bloomberg terminal has zero border
   radius anywhere. If you catch yourself writing `rounded-lg`, stop.

2. **Use `text-[var(--text-label)]` (yellow) for field labels, not `text-[var(--text-muted)]`.**
   The yellow is what makes data fields instantly scannable — it's the Bloomberg signature.

3. **ALL CAPS for labels and headers.** Use `.toUpperCase()` or `uppercase` Tailwind class.
   Body copy in report markdown is mixed-case; everything else in the UI shell is uppercase.

4. **`tabular-nums` on every number.** Monospace + tabular-nums keeps columns aligned.

5. **Tailwind grid with CSS var gap for panel dividers:**
   ```tsx
   style={{ gap: "1px", background: "var(--border)" }}
   ```
   This is the Bloomberg "thick border between panels" pattern — the gap itself
   becomes the border by setting background to the border colour.

6. **`STAGE_COUNT` not `15`.** Import from `@/lib/types` — it's already exported.
