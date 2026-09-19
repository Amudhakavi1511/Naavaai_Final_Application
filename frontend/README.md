# Naavaai — Maritime Procurement Portal (Frontend)

SIH 26006. Government-of-India-styled portal over the Output & Interaction
Layer (4.1–4.3): a cargo-requirement desk, the reason-coded recommendation,
a ranked-alternatives chart, a "Working shown" transparency panel over the
3.1–3.4 feasibility output, and what-if sensitivity analysis — connected
live to the backend, with no hardcoded reference data of its own.

## Run it

Backend must be running first (from `../backend`) — the frontend has no
fallback data and shows a connection-problem screen until it's reachable:
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
no CORS setup or `.env` file needed in development.

`npm run build` produces a static production build in `dist/`. For a
deployed build, set `VITE_API_BASE_URL` to the backend's origin — see
`.env.example`.

## What's here

```
src/
  types.ts                 TypeScript mirrors of the backend's response schemas,
                             including the /reference/bootstrap contracts
  api.ts                    Fetch wrapper: fetchBootstrap(), runOptimization(),
                             runWhatIf(), defaultCargo()
  labels.ts                 Port-id/commodity-id -> display name, populated once
                             from the bootstrap response (registerReference())
  format.ts                 usd()/pct() display helpers
  components/
    AppShell.tsx             Masthead, tricolour rule, side navigation, text-size control
    Login.tsx                 Demo sign-in
    PortalOverview.tsx        Landing section
    CargoForm.tsx              Cargo requirement input — built entirely from
                                the reference data passed in as a prop
    RecommendationPanel.tsx     4.1 — headline, decision summary, reason-coded explanation
    DecisionChart.tsx            Ranked-alternatives bar chart (Recharts)
    EngineRoom.tsx                 Feasibility/candidate transparency accordion ("Working shown")
    WhatIfPanel.tsx                 4.2 — sensitivity-analysis controls + delta display
    IntelligenceLayer.tsx            Forecast chart + scenario-bank summary (reference-driven)
    PortIntelligence.tsx              East Coast gateway table (reference-driven)
    DecisionRegister.tsx               Session decision history
  App.tsx                   Fetches reference data on load; orchestrates state,
                              layout, and the connecting/error/empty/rejected states
```

## Connected to a live backend (this session)

The frontend previously shipped its own hardcoded copy of the loading-port
network and posted an 800 KB scenario bank back to the server on every
request. Both are gone:

- `App.tsx` fetches `GET /reference/bootstrap` once on load and holds it in
  state; every page — the cargo form, port intelligence, market intelligence,
  the overview tiles — renders from that one payload rather than from
  anything hardcoded in the frontend.
- The old `src/reference.ts` (hardcoded countries/ports) and `src/demo/`
  (bundled `cargo_requirement.json` + the 806 KB `scenario_set.json`) are
  both deleted. `src/labels.ts` replaces the port/commodity name lookups,
  populated once from the bootstrap response instead of a static table.
- `scenario_set` is no longer sent on `/optimization/run` or
  `/optimization/what-if` — the backend uses its own bundled bank.
- The default cargo requirement — including the departure/deadline dates —
  now comes from `bootstrap.default_cargo`, computed server-side against the
  scenario bank's actual forecast horizon, instead of a client-side guess
  like "today + 7 days" that could fall outside what the engine can price.
- New states in `App.tsx`: a "Connecting to the decision service" screen
  while bootstrap loads, and a proper "service unavailable" screen with a
  retry button and the server's actual error text — never a silent fallback
  to stale local data.

Bundle size dropped from 950 KB to 639 KB with the scenario bank gone.

## Design notes

The interface follows Government of India web conventions (GIGW): tricolour
rule above a white masthead with the national emblem and department line,
Ashoka-blue side navigation, breadcrumb, and a working A / A / A text-size
control in the masthead that scales the whole page (it writes `--root` via
`data-textsize` on `<html>` and persists in `localStorage`).

- **Palette**: `#14315b` navy for navigation and the recommendation band,
  `#1a5fa8` for actions and links, saffron and India green reserved for the
  tricolour rule and the active-nav marker only. Semantic green/amber/red for
  pass, caution and fail states.
- **Type**: Noto Sans throughout — the family the Government of India uses for
  its multilingual portals — with Noto Sans Mono for figures, vessel IDs and
  dates where tabular alignment matters. Both load from Google Fonts with a
  system fallback stack, since sandboxed environments block the CDN.
- **Type sizes**: the root is 17px and everything is sized in `rem`, so no text
  in the interface falls below roughly 14px.
- **Numbering**: removed everywhere it was decorative — sidebar step numbers,
  eyebrow labels, numbered lists used purely as bullets. Numbers appear only
  where they carry meaning (quantities, costs, dates, scenario counts). The
  evidence panel is "Working shown" with plain section names rather than the
  underlying spec's `3.1`/`3.2` module numbering.
- **Emphasis**: one loud element per screen. On the decision desk it is the
  navy recommendation band; everything else is flat white with hairline rules.
- **Copy**: rewritten from system vocabulary to charterer vocabulary —
  "No feasible vessel" became "No vessel can carry this cargo", `CVaR 80`
  is labelled "worst-case average", and empty and error states say what to do next.

## Accessibility

- Skip-to-content link, `aria-current` on the active nav item, `aria-expanded`
  on every disclosure, `aria-pressed` on the text-size control, `role="alert"`
  on error notices, real `<table>` markup with `<th scope="col">` for the port
  and register tables.
- Visible 3px focus ring on every interactive element.
- `prefers-reduced-motion` respected.
- Text reflows to a single column at 620px with no horizontal scrolling; data
  tables collapse to stacked rows on small screens.

## Loading countries and ports

All of it comes from the backend now — nothing is hardcoded here. `GET
/reference/bootstrap` returns 33 loading ports across 11 countries India
actually imports dry bulk from (Australia, Indonesia, United States,
Mozambique, South Africa, Canada, Russia, Colombia, Brazil, Oman, UAE), each
tagged with its commodities, plus the 6 East Coast discharge ports.

There's no longer a per-port "not in demo data" flag in the frontend, because
the backend now derives a sailing distance for essentially every port pair
(see `../backend/app/api/route_distances.py`), so almost every lane the form
offers actually runs. A lane can still come back `NO_FEASIBLE_STRATEGY` or
`NO_FEASIBLE_PORT` — that's the engine correctly reporting a real feasibility
limit (e.g. Beira's shallow draft), not missing reference data, and the
decision desk surfaces it as a plain-language explanation with the evidence
panel underneath, not an error page.

## Verified (headless browser click-through, against a live backend)

Full flow tested end-to-end via Playwright + screenshots, with `uvicorn`
actually running (not a stub): sign-in, overview reading live scenario/fleet
counts, decision desk running a real lane to a `NO_FEASIBLE_STRATEGY` result
(Mozambique/Beira) and a real `OPTIMAL` result with the live explanation
engine's reasoning (Australia/Dalrymple Bay), Engine Room accordion
expand/collapse, port intelligence and market intelligence rendering live
reference data, and What-If sliders → run comparison → delta summary. No
console/page errors in any of these paths (aside from a Google Fonts CDN
block in the sandboxed dev environment, which the system-font fallback
covers).

## Known limitations (stated, not hidden)

- CORS on the backend defaults to `localhost:5173`/`4173` for local dev; set
  `FRONTEND_URL` (comma-separated for multiple origins) for a real deployment.
- The What-If panel's changes (freight/congestion/deadline/risk/vessel
  availability) don't include changing the destination port — so it can't
  help escape a `NO_FEASIBLE_PORT` result. This is a stated scope limit of
  the current `WhatIfChanges` contract (see the backend's `whatif_schemas.py`),
  not a frontend bug.
- No automated frontend test suite (unit or e2e) — verified manually via a
  headless-browser click-through (screenshots) during development; a
  Playwright test suite would be the natural next addition.
- Port and vessel particulars behind `/reference/*` are MOCK/illustrative
  figures (see the backend README) — draft, berth count, handling rate and
  so on are in the class-typical range for each terminal, not published
  port-authority data.

## Demo UX additions

- Local demo sign-in screen with persistent session in `localStorage`.
  Credentials are not sent to a server — a production deployment should
  replace this with backend authentication (OIDC/OAuth2/session or JWT),
  secure cookies, RBAC and audit logging.
- Application shell with Overview, Decision Desk, Market Intelligence, Port
  Intelligence, What-if Analysis and Decision Register sections.
- Market Intelligence shows the scenario bank's actual size and forecast
  horizon alongside an illustrative freight outlook chart.
- Port Intelligence shows the live draft/berth/handling/congestion figures
  the feasibility checks themselves use, clearly labelled as indicative.
