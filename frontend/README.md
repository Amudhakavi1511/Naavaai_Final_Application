# SIH 26006 — Chartering Decision Desk (Frontend)

Minimal demo dashboard for the Output & Interaction Layer (4.1–4.3):
recommendation + reason-coded explanation, a Decision Chart comparing
ranked alternatives, an "Engine Room" transparency panel (3.1–3.4), and a
What-If / sensitivity-analysis panel.

## Run it

Backend must be running first (from `../backend`):
```bash
cd ../backend
uvicorn app.api.main:app --reload
```

Then, in this directory:
```bash
npm install
npm run dev
```
Open the printed local URL (typically `http://localhost:5173`). Vite's dev
server proxies `/api/*` to `http://localhost:8000` (see `vite.config.ts`) —
no CORS setup needed in development.

`npm run build` produces a static production build in `dist/`.

## What's here

```
src/
  types.ts              TypeScript mirrors of the backend's response schemas
  api.ts                Fetch wrapper for /optimization/run and /optimization/what-if
  format.ts              usd()/pct()/riskColor() display helpers
  demo/
    cargo_requirement.json   Prefills the form with the SIH demo scenario
    scenario_set.json         The 40-scenario Monte Carlo bank (bundled — see note below)
  components/
    CargoForm.tsx          Cargo requirement input row
    RecommendationPanel.tsx  4.1 — headline, decision summary, reason-coded explanation
    DecisionChart.tsx        Ranked-alternatives bar chart (Recharts)
    EngineRoom.tsx           3.1/3.2/3.3-3.4 transparency accordion
    WhatIfPanel.tsx          4.2 — sensitivity-analysis controls + delta display
  App.tsx                  Orchestrates state, layout, empty/error/rejected states
```

## Design notes

- **Palette**: deep ink-navy control-room base, a single brass/amber accent
  reserved for the recommendation itself (the "this is the answer" moment),
  sea-green for feasible, muted rust for warnings/rejections. Deliberately
  not the generic cream+terracotta or near-black+neon-accent look.
- **Type**: two families only — Space Grotesk (headings/labels) and IBM
  Plex Mono (every number, ID, date — tabular alignment is functional here,
  not decorative). Both load from Google Fonts with a solid system-font
  fallback stack, since some sandboxed/offline environments block the CDN.
- **Layout**: a working desk, not a landing page — dense, grid-based, no
  uniform rounded cards. The recommendation panel gets one deliberate bold
  treatment (a thick left border); everything else stays flat with hairline
  dividers only.
- **Numbering discipline**: sequence numbers (3.1, 3.2, 3.3–3.4) appear only
  in the Engine Room, because that IS a genuine pipeline sequence — nowhere
  else uses numbered badges as decoration.

## Verified (headless browser click-through during development)

Full flow tested end-to-end via Playwright + screenshots: initial load,
Run → recommendation + Decision Chart + Engine Room render correctly with
real backend data, Engine Room accordion expand/collapse, What-If sliders
→ Run what-if → delta comparison, and the `NO_FEASIBLE_PORT` rejected-status
empty state. No console/page errors in any of these paths.

## Known limitations (stated, not hidden)

- The scenario bank (`demo/scenario_set.json`, ~806KB) is bundled directly
  into the JS bundle rather than fetched at runtime, since there's no
  Intelligence Layer (2.x) yet to generate one dynamically — this inflates
  the production bundle size, which is fine for a demo but would need
  addressing (fetch from an endpoint instead) once 2.x exists.
- CORS is wide-open (`allow_origins=["*"]`) on the backend for local demo
  convenience — a real deployment would restrict this to the actual
  frontend origin.
- The What-If panel's changes (freight/congestion/deadline/risk/vessel
  availability) don't include changing the destination port — so it can't
  help escape a `NO_FEASIBLE_PORT` result. This is a stated scope limit of
  the current `WhatIfChanges` contract (see the backend's `whatif_schemas.py`),
  not a frontend bug.
- No automated frontend test suite (unit or e2e) — verified manually via a
  headless-browser click-through (screenshots) during development; a
  Playwright test suite would be the natural next addition.

## Demo UX additions

- Local demo sign-in screen with persistent session in `localStorage`.
- Application shell with Decision Desk, Intelligence Layer and Port Intelligence workspaces.
- Intelligence workspace demonstrates the designed 2.x pipeline: source health, P10/P50/P90 forecast view, scenario bank, market-driver signals and governance controls.
- Port Intelligence workspace provides an illustrative East Coast gateway view and clearly labels demo/reference data; it is not a live regulatory certification.
- The authentication is intentionally demo-only: credentials are not sent to a server. A production deployment should replace this with backend authentication (OIDC/OAuth2/session or JWT), secure cookies, RBAC and audit logging.
