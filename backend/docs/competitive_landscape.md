# SIH 26006 — Competitive Landscape Documentation
## Kpler Chartering · Klaveness Digital · Seven Oceans Commercials (SOC/SOPF)
*Prepared wearing two hats: an East Coast India dry-bulk chartering official's commercial eye, and a backend architect's eye for what's actually buildable and worth building.*

---

## 1. EXECUTIVE SUMMARY

None of these three platforms do what SIH 26006's candidate contribution claims to do: **couple forecast uncertainty directly into a charter-timing/vessel-selection decision, gated by deterministic feasibility, optimized under a risk-adjusted objective, with a reason-coded explanation**. That's the good news — the research-gap statement in Phase-0 survives contact with the real market.

What they *do* have, and do well, is everything **around** that decision: clean market data ingestion, TCE/voyage-economics calculators, laytime/demurrage administration, fleet and cargo book management, and (in Klaveness's case) narrow point-solutions on vessel vetting and port-congestion prediction. These are mature, commercially validated workflows — reinventing them badly would hurt the prototype; borrowing their *shape* (not their code, which we can't see) strengthens it considerably, especially on the "practicability" and "user experience" SIH criteria.

**Bottom line for scoping:** SIH 26006 should stay a **decision-support engine**, not become a Transport Management System (TMS)/ERP like Seven Oceans SOC. The commercial value we add is the optimization+explanation layer these platforms don't have. But several of their *specific features* are worth deliberately incorporating into our existing module boundaries, listed concretely in Section 5.

---

## 2. PLATFORM-BY-PLATFORM BREAKDOWN

### 2.1 Kpler — Chartering (Decision Tools)
**What it is:** A market-intelligence-first platform. Kpler's core asset is data (36,500+ vessels tracked, 40+ commodity markets, 10+ years historical freight, AIS-based ship tracking) — chartering is one "Decision Tool" built on top of that data layer, not a standalone optimization product.

**Feature set relevant to us:**
- **Tonnage List** — deduplicated, AIS-enriched, real-time list of open vessels, auto-parsed from broker email circulars (99% claimed parsing accuracy). Filterable by zone/route/charterer/open date.
- **Cargo List & Flows** — deduplicated cargo circulars + commodity flow intelligence (import/export volumes across crude/products/LNG/LPG/dry bulk) for spotting demand before it moves rates. Includes **destination forecasting** (predicting where a cargo will discharge before it arrives).
- **Voyage Calculator & Fixtures List** — centralizes market-reported + private fixtures; computes TCE, gross freight, P&L, voyage days instantly; live Baltic benchmark rates; route optimization around ECA zones and piracy corridors.
- **Freight Analytics** — port-level congestion tracked *by vessel, region, owner, and duration* (not just a single number); ballast-vs-laden ratios; idle vessel tracking; fleet development (orders/deliveries/demolitions) as a supply-side leading indicator.
- **Email Management/Inbox** — AI-parses broker circulars into structured position lists, recaps, counters, confirmations; auto-links to tonnage/cargo/fixtures records.

**What Kpler does NOT do:** optimize a charter *decision* under uncertainty. It gives a human charterer better inputs (data, TCE numbers, congestion stats) faster; the actual strategy selection, timing, and risk trade-off is still entirely manual. There is no forecast-uncertainty-to-decision pipeline, no feasibility-gated candidate generation, no stochastic optimization, no reason-coded recommendation.

### 2.2 Klaveness Digital — Chartering Decision Support
**What it is:** A narrower, more focused suite than Kpler — three specific point-tools grown out of Klaveness Dry Bulk's own internal chartering desk needs, explicitly positioned as *decision support*, not a full data terminal or TMS.

**Feature set relevant to us:**
- **Pre-Vetting** — a vessel-scoring tool: consolidates historical operational performance, commercial risk, and claims history into a single "should I fix this vessel" signal, replacing manual spreadsheet-based vetting. Directly analogous in spirit to our 3.1 Vessel Feasibility Engine, but scored/probabilistic rather than hard-constraint deterministic, and focused on **counterparty/performance risk** (a dimension our system doesn't currently model at all — see Section 5).
- **Port Predictor** — real-time port congestion + ETA prediction specifically to de-risk laycan planning; explicitly framed around "will my vessel actually make this laycan window." Conceptually the closest commercial analogue to our 3.2 Port Feasibility Engine's turnaround/congestion estimator, though theirs is presumably ML-driven off AIS data rather than our current static congestion figure.
- **Freight Optimizer** — forward freight curve tracking + fixing-timing guidance ("should I fix now or wait"), i.e. a commercial point-solution aimed at exactly our system's "charter now vs. wait" decision — but as a market-view dashboard for a human to read, not an optimizer that computes the answer.

**What Klaveness does NOT do:** integrate these three tools into one pipeline. Pre-Vetting, Port Predictor, and Freight Optimizer are marketed as separate solutions a charterer consults independently — there's no evidence of a single request ("here's my cargo, give me the best decision") flowing through all three plus an optimizer. This is precisely the integration gap our research-gap statement (Phase-0 Section C) already targets.

### 2.3 Seven Oceans Commercials (SOC) + Seven Oceans PreFix (SOPF)
**What it is:** The most comprehensive of the three — a full chartering-through-post-fixture ERP/TMS (30 years of shipping-industry heritage, 6,000+ users claimed, 2+ billion tonnes of cargo handled). Covers dashboards, fleet/cargo books, chartering, demurrage, operations/post-fixture, finance & accounting, and contracts of affreightment (COA) management end-to-end.

**Feature set relevant to us (mainly via the SOPF pre-fixture module):**
- **Voyage/Freight Estimate Calculator** — the deepest TCE calculator of the three: automated vessel-specifics/commercial-parameters data feed, **ML/AI-driven bunker consumption estimation**, automatic passage planning (zonal restrictions, canals, ECA zones, piracy corridors, both ECA and normal distance calculation), **EU ETS/FuelEU carbon-cost calculation per voyage**, and **multi-voyage comparison with sensitivity analysis on TCE**.
- **Decision Charts** — explicitly named UI concept: visual comparison tools "to select the most profitable fixtures" — the closest commercial analogue to our own strategy-comparison table/optimization-result ranking, though theirs appears to be a human-driven comparison view, not a solved/ranked optimizer output.
- **Cargo Tonnage Book** — present + future cargo positions linked directly to voyage/freight estimates, which then connect to confirmed cargoes — i.e., the full cargo-requirement-to-fixture lifecycle we're only modeling the *decision* slice of.
- **Demurrage/Laytime module** — genuinely sophisticated: agency-integrated Statement-of-Facts entry (avoiding double entry between ops desk and port agents), full laytime/demurrage/despatch calculation, live voyage cash flow. This is a much richer version of our 3.4 cost engine's despatch/demurrage piece — worth studying for what a "real" implementation eventually needs (our current model uses a single flat allowance + rate; SOC's implies port-by-port, activity-by-activity SOF tracking).
- **COA management** — nominating voyage charters/relets to a specific COA, matching our `MEDIUM_TERM`/`COA` strategy types in 3.3, but as contract administration, not a strategy the system recommends.

**What Seven Oceans does NOT do:** any forecasting, any uncertainty modeling, any optimization. SOC is fundamentally a system of record and workflow tool — it calculates the economics of a fixture *you already decided on* (or are actively comparing by hand via Decision Charts) extremely well, but it does not generate or rank candidate strategies itself, and has no concept of scenario-based freight uncertainty at all.

---

## 3. CROSS-PLATFORM FEATURE MATRIX

| Capability | Kpler | Klaveness Digital | Seven Oceans (SOC/SOPF) | SIH 26006 (current) |
|---|---|---|---|---|
| Real-time tonnage/cargo list aggregation (email-parsed) | ✅ Strong | — | Partial (Cargo Tonnage Book, manual entry) | ❌ Not in scope |
| AIS-based live vessel tracking | ✅ Strong | ✅ (Port Predictor) | — | ❌ Not in scope (MOCK availability only) |
| Port congestion analytics | ✅ (by vessel/owner/region) | ✅ (Port Predictor, ETA-focused) | — | ⚠️ Basic (single current_congestion_days figure) |
| TCE / voyage economics calculator | ✅ | — | ✅✅ Deepest (ETS, bunkers ML, sensitivity) | ⚠️ Basic (3.4's delivered cost, no ETS/carbon) |
| Freight forecasting (any form) | Historical index only | ✅ (Freight Optimizer, trend-based) | — | ✅ (2.1, once built) |
| **Forecast uncertainty (quantiles/scenarios)** | ❌ | ❌ | ❌ | ✅ (2.2 — our candidate differentiator) |
| **Deterministic vessel/port feasibility gating** | ❌ (data only, no gating) | ⚠️ Pre-Vetting is scoring, not hard-gating | ❌ | ✅ (3.1/3.2) |
| **Mathematical optimization of charter decision** | ❌ | ❌ | ❌ | ✅ (3.5 — our candidate differentiator) |
| **Risk-adjusted objective (CVaR etc.)** | ❌ | ❌ | ❌ | ✅ (3.6 — our candidate differentiator) |
| **Reason-coded explainable recommendation** | ❌ | ❌ | ❌ (Decision Charts are comparison, not explanation) | ✅ (planned, 4.1) |
| Vessel performance/counterparty risk scoring | — | ✅ (Pre-Vetting) | — | ❌ Not modeled at all |
| Laytime/demurrage/despatch administration | — | — | ✅✅ (SOF-integrated) | ⚠️ Basic (flat allowance model) |
| Carbon/ETS cost accounting | — | ✅ (Emissions Monitoring, separate product) | ✅ | ❌ Not modeled |
| Contract/COA lifecycle management | — | — | ✅✅ | ⚠️ COA is a candidate strategy type only, no lifecycle |
| Full-desk workflow (dashboards, finance, invoicing) | Partial | — | ✅✅ | ❌ Explicitly out of scope |

The pattern is consistent: **rich data and administration on one side, zero decision-optimization on the other** — with a gap in the middle that's exactly where SIH 26006 sits.

---

## 4. WHAT THIS CONFIRMS ABOUT OUR POSITIONING

- **The Phase-0 research-gap statement holds up.** Nothing in these three platforms couples forecast uncertainty to a feasibility-gated, risk-adjusted charter-timing optimization. Klaveness's "Freight Optimizer" is the closest *conceptually* (same "fix now vs. wait" question) but is a market-dashboard, not a solver.
- **We should NOT try to out-build Kpler's data layer.** Their tonnage/cargo list aggregation is backed by 15 years of proprietary AIS/email-parsing infrastructure — replicating that for a SIH prototype would be a scope trap, would use up all our time on non-differentiating plumbing, and we'd lose badly on "feasibility"/"practicability" if we tried and produced something worse. Our MOCK vessel-availability data approach (Phase-0 Section E) is the right call — a real deployment would integrate a Kpler-like feed, not rebuild one.
- **We should NOT try to become Seven Oceans' TMS.** Their demurrage/SOF/finance/COA-lifecycle depth took 30 years of a real chartering-tech company to build. Attempting that would actively hurt "feasibility" and "practicability" scoring by overreaching what a student team can credibly deliver.
- **The right move is targeted feature borrowing** into our *existing* module boundaries — not new modules, not scope expansion. Section 5 makes this concrete.

---

## 5. WHAT TO INCORPORATE — MAPPED TO EXISTING MODULES

### 5.1 Into 2.1/2.2 (Forecasting / Uncertainty Engine) — *Intelligence Layer, not yet built*
- **Destination forecasting concept (from Kpler)**: worth a lightweight nod — for split-cargo or multi-port candidate generation later, predicting *which* East Coast port a cargo is likely to actually route to (given congestion/handling-rate differentials) could sharpen 3.2's port set before 3.3 enumerates candidates. Not core to the MVP; note as a future-work line in Phase-0 Section 41.
- **Forward-curve framing (from Klaveness's Freight Optimizer)**: strengthens the UI narrative for 2.1's forecast output — presenting the P10/P50/P90 band explicitly as a "should I fix now or wait" curve (which is literally what our WAIT_THEN_CHARTER candidates already test) gives judges an immediately recognizable, industry-validated framing rather than an abstract quantile chart.

### 5.2 Into 3.1 (Vessel Feasibility Engine) — genuinely new capability worth adding
- **Vessel performance/counterparty risk scoring (from Klaveness's Pre-Vetting)** is the single most valuable idea to borrow, and it's currently a real gap: our 3.1 only checks *physical* feasibility (capacity/draft/LOA/beam/availability). A vessel can be physically feasible and still be a poor commercial choice (age, flag, claims history, off-hire frequency, CII rating — which Kpler explicitly surfaces too). Recommend adding a **non-blocking risk flag** (not a hard gate — that would conflict with 3.1's "deterministic physical constraints only" design principle) surfaced alongside feasibility results and folded into 3.6's risk metrics as an optional additional term. This is a **legitimately new, defensible extension** to propose as future work in the SIH write-up, and cheap to stub with a mock `vessel_reliability_score` field on the `Vessel` schema without touching 3.1's core rule chain.

### 5.3 Into 3.2 (Port Feasibility Engine) — strengthens an already-flagged limitation
- **Port Predictor's ETA/congestion-prediction framing (from Klaveness)** validates that our current `current_congestion_days` (a single static observed figure) is the correct *simplification to name explicitly* as a limitation (Phase-0 Section 41) rather than something to silently leave underspecified — a real deployment's natural upgrade path is exactly a Klaveness-Port-Predictor-style ML congestion forecast feeding `base_congestion_shock_days` in our ScenarioSet contract, which our architecture already has a slot for.
- **Kpler's congestion-by-owner/region breakdown** is a good future-work idea for the dashboard (4.3) — congestion segmented by vessel type/owner at a given port, not just a port-level average — but not a Decision Engine change.

### 5.4 Into 3.4 (Delivered Cost Engine) — two concrete, buildable additions
- **Carbon/ETS cost line item (from Seven Oceans SOPF)**: EU ETS and FuelEU-style bunker penalties are increasingly relevant even for India-bound dry-bulk voyages touching ECA-adjacent routes, and — more importantly for the SIH "sustainability" evaluation criterion — an explicit carbon-cost term in delivered cost is a direct, credible way to make "sustainability" a *quantified* part of the recommendation, not just a claimed value. Recommend adding an optional `carbon_cost` line to `CostBreakdown`, config-driven like every other cost parameter, defaulting to zero/disabled until real emission-factor data is sourced — stated limitation, not silently omitted.
- **Sensitivity analysis on TCE/freight (from Seven Oceans SOPF & Kpler's voyage calculator)**: this is *already effectively what our what-if simulator (4.2) is designed to do*, but it's worth explicitly framing 4.2 in the UI using the "sensitivity" vocabulary the industry already recognizes (freight ±X%, congestion ±N days) rather than inventing new terminology — a direct, low-cost UX win.

### 5.5 Into 3.5/3.6 (Optimization/Risk) — validates rather than changes the design
- None of the three platforms do anything resembling our MIP/enumeration split or risk-adjusted objective — there's nothing to borrow here structurally. The one adjacent idea is Seven Oceans' "Decision Charts" *terminology* — worth reusing that exact phrase in our own UI (Section 5.6) since it's an established term charterers already recognize, rather than inventing a new label for the same concept.

### 5.6 Into 4.1/4.2/4.3 (Output & Interaction Layer) — the most direct UX borrowing
- **"Decision Charts" (Seven Oceans)**: adopt this term for our strategy-comparison visualization in 4.1/9.2 of the Decision Engine spec — it's industry-recognized vocabulary, costs nothing, and signals domain fluency to SIH evaluators.
- **TCE-per-minute framing (Seven Oceans: "Achieve TCE calculations in under a minute")**: reinforces that our demo's runtime target (Phase-0 Section M: "a few seconds") is not just a nice-to-have but matches an established industry expectation for a chartering tool — worth stating explicitly in the SIH submission as a benchmarked, not arbitrary, performance target.
- **Tonnage-list-style filtering UX (Kpler)**: the "engine room" panel's 3.1 vessel table (Decision Engine spec Section 9.2) should support the same filter vocabulary charterers already expect (zone, vessel class, open date) even though our candidate set is already pre-filtered — purely a UX/labeling improvement, not a new capability.
- **Email/inbox parsing (Kpler)**: explicitly OUT of scope — flagged here only to rule it out deliberately. It's the single largest engineering investment of any feature reviewed (99% parsing accuracy across broker circulars is a serious ML/NLP undertaking on its own) and has zero relationship to our forecast-to-optimization contribution. Worth one sentence in the SIH write-up's "what we deliberately did not build" list, to preempt the question rather than look like an oversight.

### 5.7 Explicitly NOT recommended (scope guardrails)
- Full email/circular parsing pipeline (Kpler) — out of scope, as above.
- Full demurrage/SOF/agency workflow (Seven Oceans) — our flat despatch/demurrage model (Phase-0 Section 5.3, already flagged as a stated simplification) is the correct scope for a prototype; SOC's depth here took a real company years.
- Finance/invoicing/accounting modules (Seven Oceans) — irrelevant to the decision-support research question.
- Standalone vessel-vetting product, contract lifecycle management, brokerage workflow — all real, all valuable commercially, all outside what a forecast-driven decision-support prototype needs to prove its research question.

---

## 6. UPDATED DIFFERENTIATION STATEMENT (for the SIH submission)

> Commercial platforms in this space split into two categories: **market-intelligence/workflow tools** (Kpler, Seven Oceans) that give a human charterer better data and administration but leave the actual strategy decision entirely manual, and **narrow point-solutions** (Klaveness Digital's Pre-Vetting/Port Predictor/Freight Optimizer) that each address one input to that decision without integrating them. None couples forecast uncertainty to a feasibility-gated, mathematically optimized, risk-adjusted, explainable charter-timing recommendation — which remains SIH 26006's candidate contribution, now validated against the current commercial landscape rather than assumed.

---

## 7. CONCRETE BACKLOG ITEMS FROM THIS REVIEW

| Priority | Item | Target module | Effort |
|---|---|---|---|
| Should-do | Add optional `vessel_reliability_score` field (mock) to `Vessel` schema + surface as a non-blocking flag in 3.1's output, folded into 3.6 as an optional risk term | 3.1, 3.6 | Small |
| Should-do | Add optional `carbon_cost` line to `CostBreakdown`, config-driven, default disabled | 3.4 | Small |
| Should-do | Rename UI concepts to match industry vocabulary: "Decision Charts" (4.1), "sensitivity analysis" (4.2) | 4.1, 4.2 | Trivial (naming only) |
| Nice-to-have | Document destination-forecasting and ML-driven congestion prediction as named future-work items (not vague "future work") | Phase-0 Section 41 | Trivial (docs only) |
| Explicitly deferred | Email/circular parsing, full demurrage/SOF workflow, finance/invoicing, contract lifecycle management | — | Out of scope, stated |

---

## NEXT STEP
Ready to implement the two "should-do" schema/module additions (vessel reliability score, carbon cost line) against the existing 3.1/3.4/3.6 code, or to continue with the previously agreed build order (Intelligence Layer / Output Layer) first — your call on sequencing.
