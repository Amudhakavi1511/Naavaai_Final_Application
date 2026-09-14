# SIH 26006 — Decision Engine (3.1-3.6) + Orchestration API + Output Layer (4.1, 4.2) — COMPLETE

Implements the full v2 (revised) Decision Engine spec, wired together behind
a FastAPI backend plus a minimal React demo dashboard:
**3.1-3.4, 3.6** — feasibility gates, candidate generation, cost engine, risk engine,
**3.5** — enumeration (single-vessel) + MIP (split-cargo) optimization,
**`POST /optimization/run`** — orchestration endpoint with typed statuses,
**4.1** — deterministic reason-coded Recommendation & Explanation Engine,
**4.2** — What-If Simulator (`POST /optimization/what-if`, no separate code path),
**4.3** — minimal React dashboard (`../frontend`).

## Run it

```bash
pip install -r requirements.txt
python -m pytest tests/ -v          # 118/118 tests
uvicorn app.api.main:app --reload   # http://localhost:8000/docs for interactive Swagger UI
```

Try it: `POST /optimization/run` with body `{"cargo": <CargoRequirement>, "scenario_set": <ScenarioSet>}`
— see `tests/fixtures/cargo_requirement.json` and `mock_forecast_scenario.json`
for ready-to-use examples (this is exactly what `test_api_orchestration.py` sends).
Or run the frontend (`../frontend`) for the full interactive demo.

118/118 tests passing at time of writing.

## What's here

```
app/
  config.py                   # Every prototype cap/threshold, named and documented in one place
  schemas/
    common.py                  # CargoRequirement, Vessel, Port, ScenarioSet, feasibility results
    candidates.py               # CandidateOption / CandidateSet — 3.3's output contract
  feasibility/
    rules.py / vessel_engine.py       # 3.1
    congestion.py / port_engine.py    # 3.2
  optimization/
    pruning.py                  # 3.3 — named, independently-toggleable pruning filters
    strategy_generator.py        # 3.3 — orchestrator
  cost/
    params_loader.py             # 3.4 — versioned, typed config/cost_parameters.yaml loader
    despatch_demurrage.py         # 3.4 — isolated, most likely to need real charter-party tuning
    delivered_cost.py              # 3.4 — orchestrator, computes the full cost matrix
  risk/
    preference_mapping.py         # 3.6 — risk_preference -> lambda, the single place to look
    metrics.py                     # 3.6 — orchestrator: expected/variance/CVaR/downside, risk_adjusted_objective(), compute_combined_risk()
  optimization/  (continued)
    expected_cost.py               # 3.5 — MIP linear-objective coefficient extraction
    enumerate.py                    # 3.5 — single-vessel closed-form argmin path
    mip_model.py                     # 3.5 — split-cargo MIP (OR-Tools MPSolver/CBC), berth-overlap big-M
    solver_runner.py                  # 3.5 — orchestrator: routes enumeration vs. MIP by problem shape
  api/
    reference_data.py               # STAND-IN for the DB layer — loads the demo fixture as "master data"
    schemas.py                       # Request/response contracts for the API
    orchestration.py                  # Implements spec Section 8's exact 3.1->3.6 sequencing
    main.py                            # FastAPI app: POST /optimization/run, GET /health

config/
  cost_parameters.yaml           # Every cost figure, versioned, MOCK/illustrative until sourced

scripts/
  generate_mock_scenarios.py    # Builds the >=20-scenario Monte Carlo Intelligence
                                 # Layer fixture (dual voyage $/tonne + TC $/day paths)

tests/
  conftest.py                    # Loads all fixtures into typed schema objects
  test_vessel_feasibility.py     # 3.1
  test_port_feasibility.py       # 3.2
  test_strategy_generator.py     # 3.3
  test_delivered_cost.py         # 3.4
  test_risk_engine.py            # 3.6
  test_optimization_engine.py    # 3.5
  test_api_orchestration.py      # POST /optimization/run — end-to-end integration
  fixtures/
    mock_vessels.json            # 9-vessel fleet spanning every edge case
    mock_ports.json              # 10-port network incl. a congestion-fail case
    mock_distances.json          # Illustrative nm distances
    cargo_requirement.json       # SIH demo scenario
    mock_forecast_scenario.json  # 40-scenario Monte Carlo bank (generated, not hand-written)
```

## Design notes / bugs found and fixed along the way

- **`origin_ok` timing bug** (found via test failure): was checking arrival-at-origin
  against `earliest_departure` (too strict). Fixed to check against the latest
  useful departure (`deadline − laden_days`), consistent with `avail_ok`.
- **Stale reason text**: `origin_ok`'s explanation string still described the old,
  wrong rule after the logic was fixed — caught on a code-review re-read, not by
  a test (the tests only checked booleans, not message wording).
- **Tautological port draft check** (found on code review, not by a test): `run_port_feasibility`
  originally derived `required_draft_m` from vessels already filtered by 3.1 — which,
  by construction, could never fail the port draft check. Fixed to derive it
  independently from the full candidate fleet, with a regression test proving a
  too-shallow port is now actually caught.
- **Congestion NOT pre-summed into turnaround** (`base_turnaround_days` and
  `current_congestion_days` stay separate) — carries forward the spec-review
  issue #9 fix so 3.4 can compose them correctly with a scenario's congestion shock.
- **3.3's `split_eligible` filter** (spec-review issue #11): a vessel below
  `MIN_ECONOMIC_LOT_TONNES` (15,000t) is excluded even if 3.1 flagged it
  `split_candidate=True` — verified with a dedicated regression test (`V-MICRO`, 8,000t).
- **TC rate availability contract rule** (spec-review issue #7): `SHORT_TERM`/`MEDIUM_TERM`/`COA`
  candidates are only generated if the scenario bank actually carries a TC hire
  path for that vessel class; otherwise the exclusion is logged (`TC_RATES_UNAVAILABLE`),
  never silently priced as a voyage charter.
- **3.4 built, cost-basis fixes verified**: `app/cost/delivered_cost.py` implements
  the per-tonne + fixed split (issue #1), TC vs. voyage branching (issue #7),
  duration-based deadhead (issue #8), additive congestion composition (issue #9),
  and despatch as demurrage's mirror (issue #10) — each with a dedicated regression test.
- **TC hire underpriced the on-hire leg** (found via a post-build sanity check, not
  a test): the cost engine initially charged TC hire only for the laden leg, but
  the mock scenario generator's $/day rate is calibrated off a full round-trip
  reference period — charging it against laden-only produced a TC total less
  than a third of the equivalent voyage-charter total for the *identical* vessel
  and voyage, which isn't economically plausible. Fixed to charge hire over the
  full on-hire duration (ballast leg to load port + laden leg), which closed most
  but not all of the gap; the residual gap is attributable to the mock generator's
  documented 65%-margin approximation, not a code bug, and is left as a stated
  limitation rather than chased further without real TC/voyage parity data.
- **3.6 built, all fixed as absolute USD**: `risk_adjusted_objective()` computes
  `expected_cost + risk_lambda*(cvar-expected_cost)`, verified to reduce EXACTLY
  to expected-cost-only ranking at lambda=0 (issue #3's central regression test).
  `weighted_cvar()` correctly handles the tail-boundary scenario (partial
  probability mass), verified against hand-computed reference values, not just
  round numbers. CVaR gates on `MIN_SCENARIOS_FOR_CVAR=20`; below that it
  reports `cvar_status=NOT_MEANINGFUL_SAMPLE_SIZE` and falls back to worst-case
  exactly (issue #4).
- **3.5 built — enumeration + MIP routing**: `solver_runner.py` routes to
  closed-form enumeration when any candidate can cover the full cargo alone,
  and to the MIP only when a split is genuinely required — verified on the
  real 9-vessel fixture (normal 80,000t cargo -> ENUMERATION) and a synthetic
  140,000t cargo that no single vessel can cover (-> MIP, correctly splits
  across 2 vessels, respects `MIN_ECONOMIC_LOT_TONNES` and `MAX_VESSELS_PER_CARGO`).
- **Same-vessel double-booking bug** (found during self-review of my own MIP
  formulation, before any test ran against it): nothing in the initial
  constraint set stopped two different candidate ROWS for the same physical
  vessel (different epochs) from both being selected. Added an explicit
  "at most one candidate per vessel" constraint, with a dedicated regression test.
- **Berth-overlap single-berth assumption** (found via a failing test, which
  turned out to reveal a real undocumented simplification rather than a bug):
  a test asserting that two vessels with identical arrival/departure windows
  could still both be scheduled failed with `INFEASIBLE`. On inspection, this
  is mathematically correct given the constraint as formulated — it enforces
  at most one candidate occupying a shared destination port at a time,
  regardless of that port's actual `berth_count` (e.g. Paradip's fixture value
  of 3). A multi-berth port could legitimately host several vessels at once;
  modeling that properly needs a cumulative-resource constraint, not the
  current pairwise big-M pair. Documented explicitly in `mip_model.py` as a
  stated (conservative — it can reject some jointly-feasible combinations a
  real multi-berth port would allow, but never accepts a genuinely infeasible
  one) simplification, with the test corrected to assert the right thing and
  a boundary-case test added proving the `>=` inequality accepts an exact
  back-to-back berth handoff rather than rejecting it off-by-one.

### Four more real bugs found writing the end-to-end API integration tests
Each module's own unit tests happened to construct scenarios where these
never triggered — end-to-end testing through the actual orchestration
sequence is what surfaced them:

1. **`VesselFeasibilityResult.status` too strict for split-only fleets.**
   It required at least one STRICTLY feasible vessel, so a cargo too big for
   any single vessel (but fine for a split) incorrectly short-circuited to
   `NO_FEASIBLE_VESSEL` at 3.1, before 3.3 ever got a chance to build split
   candidates. Fixed: `status` is now "OK" if there's a feasible vessel OR
   any split-eligible one — whether a split candidate clears the minimum
   economic lot is 3.3's job, not 3.1's.
2. **`PortFeasibilityResult.status` only required ONE of the two ports (origin
   or destination) to be feasible**, not both — a broken destination with a
   fine origin silently reported "OK" and proceeded, since the origin alone
   made the internal `feasible_ports` list non-empty. Fixed to require every
   evaluated port feasible.
3. **A missing distance-table entry crashed into a raw 500 traceback**
   instead of a clean error — added a `ValueError` handler at the API layer
   returning a typed `REFERENCE_DATA_INCOMPLETE` 500, per spec Section 40's
   "never crash, return a typed result" principle. Also filled in the
   missing distance entries in the fixture itself.
4. **3.2's `required_draft_m` broke for split-cargo scenarios** (a second-
   order effect of the earlier tautology fix): capacity-filtering to "vessels
   big enough to carry the cargo alone" meant a 140,000t cargo's required
   draft was computed from a Capesize (18m draft) — failing a port the
   *actual* plan (a Panamax split, 14.3m draft) would have used fine. Fixed:
   `required_draft_m` is now the shallowest draft across the WHOLE candidate
   fleet, with no capacity filter — draft is a per-vessel physical fact,
   independent of whether that vessel ends up carrying the cargo alone or as
   one leg of a split.

## Demo output (sanity check against the SIH cargo requirement)

```
=== 3.1 VESSEL FEASIBILITY ===  status: OK   (2/9 fully feasible, 4 split-eligible, 3 rejected)
=== 3.2 PORT FEASIBILITY ===    status: OK   (both Hay Point and Paradip feasible)
=== 3.3 CHARTER STRATEGIES ===  status: OK   170 candidates (+1 null) across 6 eligible vessels
=== 3.4 DELIVERED COST ===      6,800 rows (170 candidates x 40 scenarios)
=== 3.6 RISK (BALANCED -> lambda=0.35) ===   SPOT_NOW candidates, full 80,000t tonnage:

  V-PMX-014   expected=$1,612,354  cvar=$1,701,680 (COMPUTED)  worst=$1,735,680  downside_prob=0.10  MEDIUM
  V-PMX-022   expected=$1,432,924  cvar=$1,499,850 (COMPUTED)  worst=$1,539,450  downside_prob=0.08  MEDIUM
  V-PMX-045   expected=$1,782,880  cvar=$1,884,306 (COMPUTED)  worst=$1,925,606  downside_prob=0.12  MEDIUM
```
`worst_case >= cvar >= expected` holds for every candidate, as it must.

=== 3.5 OPTIMIZATION — normal 80,000t cargo (ENUMERATION path) ===
```
solve_method: ENUMERATION   status: OPTIMAL
WINNER: V-PMX-014  SHORT_TERM (TC)  epoch=2026-09-06
expected_cost=$895,437   cvar_80=$935,467 (COMPUTED)   objective=$909,448   lambda=0.35

ranked alternatives:
  #1 C-0015  expected=$895,437  cvar=$935,467
  #2 C-0016  expected=$910,333  cvar=$951,077
  #3 C-0017  expected=$921,868  cvar=$963,462
```
(The TC candidate wins because of the documented TC-pricing gap noted under 3.4 —
the optimizer is correctly picking the cheapest option among the inputs it's given.)

=== 3.5 OPTIMIZATION — synthetic 140,000t cargo, forces a split (MIP path) ===
```
solve_method: MIP   status: OPTIMAL
  C-0015  V-PMX-014  SHORT_TERM  epoch=2026-09-06   tonnage=82,000
  C-0045  V-PMX-022  SHORT_TERM  epoch=2026-09-01   tonnage=58,000
total tonnage covered: 140,000  (cargo requires 140,000)
expected_cost=$1,420,528   cvar_80=$1,483,852 (COMPUTED, realized post-hoc)
```


## Not yet built (next in the agreed build order)

1. Widen the Intelligence Layer (2.1–2.4) from a mock fixture into a real
   forecasting/scenario pipeline.
2. Real PostgreSQL persistence (`optimization_runs`, `optimization_decisions`,
   `decision_explanations` tables) — `app/api/reference_data.py` is a stated
   stand-in for this until the DB layer exists.
3. The remaining read-only reference endpoints from the master brief's
   Section 17 (`GET /vessels`, `/ports`, `/market`, etc.).
4. From the competitive-landscape review's backlog: real (non-mock) vessel
   reliability data sourcing, real carbon-price/emission-factor sourcing.

## Output & Interaction Layer (4.1, 4.2) — this session

- **4.1 Recommendation & Explanation Engine** (`app/explanation/`): deterministic,
  reason-coded — every string in `Explanation.reasons`/`warnings` is generated
  from an actual computed value (feasibility check results, cost breakdown,
  risk metrics, alternative comparisons), never LLM-generated or generic
  template filler. Wired into `POST /optimization/run`'s response as the
  `explanation` field, populated whenever `status` is `OPTIMAL` or
  `TIME_LIMIT_REACHED`. Covers: strategy/timing rationale, cost-vs-alternative
  comparison, risk profile (with an honest caveat when CVaR isn't
  sample-size-meaningful), probability-weighted cost composition, an explicit
  wait-vs-spot trade-off quantification for `WAIT_THEN_CHARTER` candidates,
  reliability flags surfaced as warnings (never as a positive justification),
  and rejected-vessel reasons drawn verbatim from 3.1's own `reason_text`.
- **4.2 What-If Simulator** (`app/api/whatif.py`, new endpoint
  `POST /optimization/what-if`): explicitly has **no separate code path** —
  it transforms the base `CargoRequirement`/`ScenarioSet`/reference-data
  according to the requested changes (freight shock %, congestion shock days,
  deadline shift, risk preference override, fleet-wide vessel availability
  shock), then calls the exact same `run_decision_engine()` twice (baseline +
  modified) and returns both plus a delta (whether the decision changed, cost
  movement in USD and %). An invalid change (e.g. a deadline shift that would
  move the deadline before `earliest_departure`) is a clean `422`, not a crash.
- **12 tests added** for 4.1 (`test_explanation_engine.py`) and 4.2
  (`test_whatif.py`), bringing the total to 118/118 passing.

### A real bug found while testing 4.2, not invented for this write-up
A fleet-wide 30-day vessel-availability what-if shock produced
`NO_FEASIBLE_STRATEGY` even though combined vessel capacity was clearly
sufficient — investigation (direct inspection of arrival/departure offsets)
confirmed this was the documented single-berth-per-port MIP limitation
(Section 8.4.5) genuinely triggering, not a bug. But it exposed a real
**explainability defect**: the MIP's infeasibility message was a single
hardcoded guess ("cargo quantity can't be covered within
MAX_VESSELS_PER_CARGO / MIN_ECONOMIC_LOT_TONNES") that was **actively wrong**
in this case — the real cause was a timing conflict, not capacity. Fixed by
adding `_diagnose_infeasibility()`, a cheap real check (combined top-N
vessel capacity vs. cargo quantity) that distinguishes
`INSUFFICIENT_COMBINED_CAPACITY` from `LIKELY_TIMING_OR_BERTH_CONFLICT`
instead of always guessing the same cause — with two dedicated regression
tests, one per branch.

## Frontend (4.3) — minimal demo dashboard

See `../frontend/README.md`. React + TypeScript + Vite + Tailwind v4 +
Recharts. Calls both `/optimization/run` and `/optimization/what-if`.
Verified end-to-end via a headless-browser click-through during development
(screenshots of: initial load, full recommendation + Engine Room render,
Engine Room accordion expansion showing the exact "Draft 18.1m exceeds ...
17.0m" worked example, the full What-If slider → delta comparison flow, and
the `NO_FEASIBLE_PORT` rejected-status empty state) — no console/page errors
in any of these paths.

## Competitive-landscape-driven additions (this session)
See `docs/competitive_landscape.md` for the full review of Kpler Chartering,
Klaveness Digital, and Seven Oceans Commercials/PreFix. Two backlog items
implemented directly against existing modules:

- **Vessel reliability score** (borrowed from Klaveness's Pre-Vetting concept):
  `Vessel.reliability_score` (0.0-1.0, MOCK, optional) is passed through 3.1
  as a **non-blocking** flag (`VesselCheckResult.reliability_flag` =
  `"LOW_RELIABILITY_RISK"` below `config.VESSEL_RELIABILITY_FLAG_THRESHOLD`)
  — it never affects `feasible`, preserving 3.1's "deterministic physical
  constraints only" design principle. Threaded through 3.6
  (`CandidateRiskMetrics.vessel_reliability_score`/`reliability_flag`,
  reported alongside but deliberately NOT mixed into the dollar-denominated
  `cvar`/`expected_cost` — different risk dimensions, no defensible USD
  conversion exists yet) and surfaced on the final `OptimizationResult`
  (tonnage-weighted average across legs for the MIP split-cargo case).
- **Carbon/ETS cost line** (borrowed from Seven Oceans SOPF's EU ETS/FuelEU
  calculation): `CostBreakdown.carbon_cost`, computed from total voyage bunker
  consumption (ballast + laden) × a standard IMO emission factor × a
  configurable carbon price — **disabled by default**
  (`carbon_cost_enabled: false` in `cost_parameters.yaml`), so existing costs
  are unaffected unless explicitly turned on. Directly quantifies the SIH
  "sustainability" evaluation criterion rather than leaving it as a claim.
