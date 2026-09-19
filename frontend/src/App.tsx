import { useCallback, useEffect, useState } from 'react'
import CargoForm from './components/CargoForm'
import RecommendationPanel from './components/RecommendationPanel'
import DecisionChart from './components/DecisionChart'
import EngineRoom from './components/EngineRoom'
import WhatIfPanel from './components/WhatIfPanel'
import Login from './components/Login'
import AppShell, { Masthead } from './components/AppShell'
import type { Page } from './components/AppShell'
import IntelligenceLayer from './components/IntelligenceLayer'
import PortIntelligence from './components/PortIntelligence'
import PortalOverview from './components/PortalOverview'
import DecisionRegister from './components/DecisionRegister'
import { defaultCargo, fetchBootstrap, runOptimization, runWhatIf } from './api'
import { registerReference } from './labels'
import type {
  Bootstrap,
  CargoRequirement,
  DecisionEngineResponse,
  WhatIfChanges,
  WhatIfResponse,
} from './types'

const STATUS_TEXT: Record<string, { title: string; body: string }> = {
  NO_FEASIBLE_VESSEL: {
    title: 'No vessel can carry this cargo',
    body: 'Nothing in the fleet clears the physical checks for this parcel on this timetable. Try a smaller quantity, a later deadline, or a discharge port with more draft.',
  },
  NO_FEASIBLE_PORT: {
    title: 'A port on this route will not work',
    body: 'Either the loading or the discharge port fails a feasibility check for this cargo. The port checks below say which, and why.',
  },
  NO_FEASIBLE_STRATEGY: {
    title: 'No charter strategy fits',
    body: 'Vessels and ports are workable on their own, but no combination of them meets the tonnage and timing requirements together.',
  },
  TIME_LIMIT_REACHED: {
    title: 'The solver ran out of time',
    body: 'Optimality was not proven within the time limit. The best solution found is shown below and is usually very close.',
  },
}

export default function App() {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem('naavaai_user'))
  const [page, setPage] = useState<Page>('home')

  const [reference, setReference] = useState<Bootstrap | null>(null)
  const [referenceError, setReferenceError] = useState<string | null>(null)
  const [cargo, setCargo] = useState<CargoRequirement | null>(null)

  const [result, setResult] = useState<DecisionEngineResponse | null>(null)
  const [decisions, setDecisions] = useState<DecisionEngineResponse[]>([])
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [whatIfRunning, setWhatIfRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The form is built from the engine's own reference data, so there is
  // nothing to render until it arrives. Failing loudly here is deliberate:
  // a form populated from a stale hardcoded fallback would offer lanes the
  // engine cannot service, which is the exact failure this removes.
  const loadReference = useCallback(async () => {
    const resp = await fetchBootstrap()
    if (resp.ok) {
      registerReference(resp.data)
      setReference(resp.data)
      setCargo(defaultCargo(resp.data))
      setReferenceError(null)
    } else {
      setReferenceError(resp.detail)
    }
  }, [])

  // Fetching on mount is exactly the "synchronise with an external system"
  // case the rule carves out; the state it sets lands after an await, not
  // synchronously in the effect body.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => { if (user) void loadReference() }, [user, loadReference])
  useEffect(() => { if (user) localStorage.setItem('naavaai_user', user) }, [user])

  function logout() {
    localStorage.removeItem('naavaai_user')
    setUser(null)
  }

  async function handleRun() {
    if (!cargo) return
    setRunning(true); setError(null); setWhatIfResult(null)
    const resp = await runOptimization(cargo)
    if (resp.ok) {
      setResult(resp.data)
      setDecisions((old) => [resp.data, ...old].slice(0, 10))
    } else {
      setError(resp.detail); setResult(null)
    }
    setRunning(false)
  }

  async function handleWhatIf(changes: WhatIfChanges) {
    if (!cargo) return
    setWhatIfRunning(true); setError(null)
    const resp = await runWhatIf(cargo, changes)
    if (resp.ok) setWhatIfResult(resp.data)
    else setError(resp.detail)
    setWhatIfRunning(false)
  }

  if (!user) return <Login onLogin={setUser} />
  if (referenceError) return <ConnectionProblem detail={referenceError} onRetry={loadReference} />
  if (!reference || !cargo) return <Connecting />

  const whatIfPage = (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>What-if analysis</h1>
          <p className="lede">
            A recommendation is only useful if it survives a market that does not cooperate.
            Change the assumptions here and see whether the answer still holds.
          </p>
        </div>
      </div>
      {result?.explanation ? (
        <WhatIfPanel onRun={handleWhatIf} running={whatIfRunning} result={whatIfResult} />
      ) : (
        <section className="card">
          <div className="empty">
            <strong>Run an analysis first</strong>
            <p>There needs to be a baseline recommendation before it can be compared against a changed market.</p>
            <button className="btn btn--primary" onClick={() => setPage('decision')}>Go to the decision desk</button>
          </div>
        </section>
      )}
    </div>
  )

  return (
    <AppShell page={page} onPage={setPage} user={user} onLogout={logout}>
      {page === 'home' ? <PortalOverview result={result} reference={reference} onGo={setPage} />
        : page === 'intelligence' ? <IntelligenceLayer reference={reference} />
        : page === 'ports' ? <PortIntelligence reference={reference} />
        : page === 'whatif' ? whatIfPage
        : page === 'history' ? <DecisionRegister decisions={decisions} />
        : (
          <DecisionDesk
            cargo={cargo} reference={reference} setCargo={setCargo}
            onRun={handleRun} running={running} error={error} result={result}
          />
        )}
    </AppShell>
  )
}

// ---------------------------------------------------------------------------
// Reference-data states
// ---------------------------------------------------------------------------

function Connecting() {
  return (
    <div>
      <Masthead />
      <main className="content">
        <section className="card">
          <div className="empty">
            <strong>Connecting to the decision service</strong>
            <p>Loading the port network, fleet and market scenarios.</p>
          </div>
        </section>
      </main>
    </div>
  )
}

function ConnectionProblem({ detail, onRetry }: { detail: string; onRetry: () => void }) {
  return (
    <div>
      <Masthead />
      <main className="content">
        <div className="page">
          <div className="page-head">
            <div>
              <h1>The decision service is unavailable</h1>
              <p className="lede">
                The portal builds its port network, fleet and scenario data from the decision service,
                so there is nothing meaningful to show until it responds.
              </p>
            </div>
          </div>
          <div className="notice notice--error" role="alert">
            <strong>What the service reported</strong>
            <span>{detail}</span>
          </div>
          <section className="card">
            <div className="empty">
              <strong>Try again once the service is running</strong>
              <p>Nothing is cached locally, so a retry will pick up a healthy service immediately.</p>
              <button className="btn btn--primary" onClick={onRetry}>Retry connection</button>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Decision desk
// ---------------------------------------------------------------------------

interface DeskProps {
  cargo: CargoRequirement
  reference: Bootstrap
  setCargo: (c: CargoRequirement) => void
  onRun: () => void
  running: boolean
  error: string | null
  result: DecisionEngineResponse | null
}

function DecisionDesk({ cargo, reference, setCargo, onRun, running, error, result }: DeskProps) {
  const failed = result && result.status !== 'OPTIMAL' && result.status !== 'TIME_LIMIT_REACHED'
  const status = result ? STATUS_TEXT[result.status] : null

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Decision desk</h1>
          <p className="lede">
            Enter what you need delivered and where. The engine works out what is possible,
            what it costs, and what could go wrong.
          </p>
        </div>
        <span className="chip chip--ok"><span className="dot" aria-hidden="true" />Engine ready</span>
      </div>

      <CargoForm cargo={cargo} reference={reference} onChange={setCargo} onRun={onRun} running={running} />

      {error && (
        <div className="notice notice--error" role="alert">
          <strong>The analysis could not be completed</strong>
          <span>{error}</span>
        </div>
      )}

      {failed && (
        <div className="notice notice--error" role="alert">
          <strong>{status?.title ?? 'No recommendation could be produced'}</strong>
          <span>{status?.body ?? 'The engine found no workable option for this cargo.'}</span>
        </div>
      )}

      {!result && !error && (
        <section className="card">
          <div className="empty">
            <strong>Ready when you are</strong>
            <p>Fill in the cargo requirement above and choose “Analyse procurement options”. Results appear here.</p>
          </div>
        </section>
      )}

      {result && (
        <div className="two-col two-col--desk">
          <div className="stack">
            {result.explanation && <RecommendationPanel explanation={result.explanation} />}
            {result.explanation && <DecisionChart alternatives={result.optimization_result?.ranked_alternatives ?? []} />}
          </div>
          <EngineRoom
            vessels={result.vessel_feasibility?.vessels ?? []}
            ports={result.port_feasibility?.ports ?? []}
            candidateSet={result.candidate_set}
            costMatrixRowCount={result.cost_matrix_summary?.row_count ?? null}
          />
        </div>
      )}
    </div>
  )
}
