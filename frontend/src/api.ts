import type {
  Bootstrap,
  CargoRequirement,
  DecisionEngineResponse,
  Health,
  WhatIfChanges,
  WhatIfResponse,
} from './types'

/**
 * In development the Vite dev server proxies /api to http://localhost:8000
 * (see vite.config.ts), so the default base URL is correct with no env file.
 *
 * In production set VITE_API_BASE_URL to the deployed API origin, e.g.
 *   VITE_API_BASE_URL=https://naavaai-backend.onrender.com
 * A trailing slash is tolerated.
 */
const RAW_BASE = import.meta.env.VITE_API_BASE_URL
  ?? (import.meta.env.DEV ? '/api' : 'https://naavaai-backend.onrender.com')

const API_BASE = RAW_BASE.replace(/\/+$/, '')

export type Result<T> = { ok: true; data: T } | { ok: false; status: number; detail: string }

const NETWORK_HINT =
  'Could not reach the decision service. If you are running locally, start the backend with ' +
  '`uvicorn app.api.main:app --reload` from the backend directory.'

async function request<T>(path: string, init?: RequestInit): Promise<Result<T>> {
  try {
    const resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })

    // A non-JSON body here usually means a proxy or gateway answered instead
    // of the API, so say that rather than letting a parse error surface.
    let json: unknown
    try {
      json = await resp.json()
    } catch {
      return { ok: false, status: resp.status, detail: `The service returned a ${resp.status} response that was not valid JSON.` }
    }

    if (!resp.ok) {
      const detail = (json as { detail?: string })?.detail ?? `Request failed with status ${resp.status}.`
      return { ok: false, status: resp.status, detail }
    }
    return { ok: true, data: json as T }
  } catch (e) {
    return { ok: false, status: 0, detail: e instanceof Error ? `${NETWORK_HINT} (${e.message})` : NETWORK_HINT }
  }
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

// ---------------------------------------------------------------------------
// Reference data — the form is built from whatever the engine can service
// ---------------------------------------------------------------------------

export const fetchBootstrap = () => request<Bootstrap>('/reference/bootstrap')
export const fetchHealth = () => request<Health>('/health')

// ---------------------------------------------------------------------------
// Decision engine
// ---------------------------------------------------------------------------

/**
 * `scenario_set` is deliberately not sent. The server holds the scenario bank
 * and uses its own when the field is omitted; the frontend used to bundle an
 * 800 KB copy into the JS bundle and post it back on every request, which was
 * ~800 KB of data travelling in the wrong direction for something the client
 * could neither produce nor validate.
 */
export const runOptimization = (cargo: CargoRequirement) =>
  post<DecisionEngineResponse>('/optimization/run', { cargo })

export const runWhatIf = (cargo: CargoRequirement, changes: WhatIfChanges) =>
  post<WhatIfResponse>('/optimization/what-if', { cargo, changes })

// ---------------------------------------------------------------------------
// Default requirement
// ---------------------------------------------------------------------------

/**
 * The server supplies the default, including the dates. It has to: a voyage
 * falling outside the scenario bank's forecast horizon fails with
 * INSUFFICIENT_FORECAST_HORIZON, and only the server knows where that horizon
 * sits. Guessing here (today + 7 days, say) would open the form on a
 * requirement that cannot run.
 */
export function defaultCargo(bootstrap: Bootstrap): CargoRequirement {
  return {
    cargo_requirement_id: `CARGO-${new Date().toISOString().slice(0, 10)}-001`,
    ...bootstrap.default_cargo,
  }
}
