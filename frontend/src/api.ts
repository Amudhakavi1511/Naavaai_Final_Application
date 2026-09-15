import type { CargoRequirement, DecisionEngineResponse, WhatIfChanges, WhatIfResponse } from './types'
import scenarioSet from './demo/scenario_set.json'

const API_BASE = '/api'

async function post<T>(path: string, body: unknown): Promise<{ ok: true; data: T } | { ok: false; status: number; detail: string }> {
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const json = await resp.json()
    if (!resp.ok) {
      return { ok: false, status: resp.status, detail: json.detail ?? 'Unknown error' }
    }
    return { ok: true, data: json as T }
  } catch (e) {
    return { ok: false, status: 0, detail: e instanceof Error ? e.message : 'Network error — is the backend running on :8000?' }
  }
}

export function runOptimization(cargo: CargoRequirement) {
  return post<DecisionEngineResponse>('/optimization/run', { cargo, scenario_set: scenarioSet })
}

export function runWhatIf(cargo: CargoRequirement, changes: WhatIfChanges) {
  return post<WhatIfResponse>('/optimization/what-if', { cargo, scenario_set: scenarioSet, changes })
}

export const demoCargo = (): CargoRequirement => ({
  cargo_requirement_id: 'CARGO-DEMO-001',
  commodity: 'coking_coal',
  quantity_tonnes: 80000,
  origin_country: 'Australia',
  origin_port_id: 'AU-HAY',
  destination_port_id: 'IN-PARADIP',
  delivery_deadline: '2026-10-15',
  earliest_departure: '2026-09-01',
  risk_preference: 'BALANCED',
})
