export interface CargoRequirement {
  cargo_requirement_id: string
  commodity: string
  quantity_tonnes: number
  origin_country: string
  origin_port_id: string
  destination_port_id: string
  delivery_deadline: string
  earliest_departure: string
  risk_preference: 'LOW' | 'BALANCED' | 'HIGH'
}

export interface VesselCheckResult {
  vessel_id: string
  vessel_class: string
  feasible: boolean
  split_candidate: boolean
  failed: string[]
  reason_text: string | null
  reliability_score: number | null
  reliability_flag: string | null
}

export interface PortCheckResult {
  port_id: string
  feasible: boolean
  base_turnaround_days: number
  current_congestion_days: number
  failed: string[]
  reason_text: string | null
}

export interface CandidateSetSummary {
  status: string
  candidates: { candidate_id: string; is_null: boolean }[]
  generation_notes: string[]
}

export interface RankedAlternative {
  candidate_id: string
  expected_cost: number
  cvar: number
  rank: number
}

export interface OptimizationResult {
  solve_method: string
  status: string
  selected: { candidate_id: string; tonnage: number }[]
  expected_cost: number
  cvar_80: number
  cvar_status: string
  objective_value: number
  risk_aversion_lambda: number
  vessel_reliability_score: number | null
  reliability_flag: string | null
  ranked_alternatives: RankedAlternative[]
  rejected_summary: { reason: string }[]
  notes: string[]
}

export interface DecisionLeg {
  candidate_id: string
  vessel_id: string
  vessel_class: string
  strategy: string
  pricing_basis: string
  charter_epoch: string
  tonnage: number
}

export interface DecisionSummary {
  strategy_label: string
  origin_port_id: string
  destination_port_id: string
  total_tonnage: number
  legs: DecisionLeg[]
  expected_cost: number
  cvar_80: number
  cvar_status: string
  risk_label: string
  risk_preference: string
  risk_aversion_lambda: number
}

export interface CostContribution {
  freight_or_hire_cost: number
  port_cost: number
  waiting_cost: number
  idle_cost: number
  deadhead_cost: number
  demurrage: number
  despatch_credit: number
  carbon_cost: number
}

export interface Explanation {
  headline: string
  decision: DecisionSummary
  cost_contribution: CostContribution
  reasons: string[]
  warnings: string[]
  alternatives_compared: {
    candidate_id: string
    rank: number
    expected_cost: number
    cost_delta_vs_winner_usd: number
    cost_delta_vs_winner_pct: number
    cvar: number
  }[]
  rejected_vessels: { vessel_id: string; vessel_class: string; reason_text: string }[]
}

export interface DecisionEngineResponse {
  request_id: string
  status: string
  stage_reached: string
  vessel_feasibility: { vessels: VesselCheckResult[] } | null
  port_feasibility: { ports: PortCheckResult[] } | null
  candidate_set: CandidateSetSummary | null
  cost_matrix_summary: { row_count: number; cost_param_version: string } | null
  optimization_result: OptimizationResult | null
  explanation: Explanation | null
}

export interface WhatIfChanges {
  freight_shock_pct: number
  congestion_shock_days: number
  deadline_shift_days: number
  risk_preference: 'LOW' | 'BALANCED' | 'HIGH' | null
  vessel_availability_shock_days: number
}

export interface WhatIfDelta {
  decision_changed: boolean
  baseline_status: string
  modified_status: string
  baseline_winning_vessel_ids: string[]
  modified_winning_vessel_ids: string[]
  expected_cost_change_usd: number | null
  expected_cost_change_pct: number | null
  summary: string
}

export interface WhatIfResponse {
  baseline: DecisionEngineResponse
  modified: DecisionEngineResponse
  delta: WhatIfDelta
}
