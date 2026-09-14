import { useEffect, useState } from 'react'
import CargoForm from './components/CargoForm'
import RecommendationPanel from './components/RecommendationPanel'
import DecisionChart from './components/DecisionChart'
import EngineRoom from './components/EngineRoom'
import WhatIfPanel from './components/WhatIfPanel'
import Login from './components/Login'
import AppShell from './components/AppShell'
import IntelligenceLayer from './components/IntelligenceLayer'
import PortIntelligence from './components/PortIntelligence'
import { runOptimization, runWhatIf, demoCargo } from './api'
import type { CargoRequirement, DecisionEngineResponse, WhatIfChanges, WhatIfResponse } from './types'

const STATUS_MESSAGES: Record<string, string> = {
  NO_FEASIBLE_VESSEL: 'No vessel in the fleet clears the physical feasibility checks for this cargo.',
  NO_FEASIBLE_PORT: 'The origin or destination port fails a feasibility check for this cargo.',
  NO_FEASIBLE_STRATEGY: 'Feasible vessels and ports exist, but no charter strategy could be assembled — see the reason below.',
  TIME_LIMIT_REACHED: 'The solver hit its time limit before proving optimality; showing the best solution found.',
}

type Page = 'decision' | 'intelligence' | 'ports'

export default function App() {
  const [user, setUser] = useState<string | null>(() => localStorage.getItem('naavaai_user'))
  const [page, setPage] = useState<Page>('decision')
  const [cargo, setCargo] = useState<CargoRequirement>(demoCargo())
  const [result, setResult] = useState<DecisionEngineResponse | null>(null)
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [whatIfRunning, setWhatIfRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (user) localStorage.setItem('naavaai_user', user) }, [user])

  function logout() { localStorage.removeItem('naavaai_user'); setUser(null) }
  if (!user) return <Login onLogin={setUser} />

  async function handleRun() {
    setRunning(true); setError(null); setWhatIfResult(null)
    const resp = await runOptimization(cargo)
    if (resp.ok) setResult(resp.data); else { setError(resp.detail); setResult(null) }
    setRunning(false)
  }
  async function handleWhatIf(changes: WhatIfChanges) {
    setWhatIfRunning(true); setError(null)
    const resp = await runWhatIf(cargo, changes)
    if (resp.ok) setWhatIfResult(resp.data); else setError(resp.detail)
    setWhatIfRunning(false)
  }

  return <AppShell page={page} onPage={setPage} user={user} onLogout={logout}>
    {page === 'intelligence' ? <IntelligenceLayer /> : page === 'ports' ? <PortIntelligence /> : <DecisionDesk cargo={cargo} setCargo={setCargo} onRun={handleRun} running={running} error={error} result={result} onWhatIf={handleWhatIf} whatIfRunning={whatIfRunning} whatIfResult={whatIfResult} />}
  </AppShell>
}

interface DeskProps { cargo: CargoRequirement; setCargo: (c: CargoRequirement) => void; onRun: () => void; running: boolean; error: string | null; result: DecisionEngineResponse | null; onWhatIf: (c: WhatIfChanges) => void; whatIfRunning: boolean; whatIfResult: WhatIfResponse | null }
function DecisionDesk({ cargo, setCargo, onRun, running, error, result, onWhatIf, whatIfRunning, whatIfResult }: DeskProps) {
  return <div className="page-stack">
    <div className="page-heading"><div><div className="eyebrow">PROCUREMENT</div><h1>Chartering decision desk</h1><p>Turn a cargo requirement into a feasible, risk-aware procurement recommendation.</p></div><div className="run-status"><span className="status-dot" /> Ready to optimize</div></div>
    <CargoForm cargo={cargo} onChange={setCargo} onRun={onRun} running={running} />
    {error && <div className="error-banner"><strong>Analysis response</strong><span>{error}</span></div>}
    {!result && !error && <div className="empty-state"><div className="empty-icon">◈</div><strong>Ready for a procurement run</strong><span>Set the cargo requirement and run the Decision Engine to compare feasible chartering strategies.</span><button onClick={onRun}>Run procurement analysis →</button></div>}
    {result && result.status !== 'OPTIMAL' && result.status !== 'TIME_LIMIT_REACHED' && <div className="error-banner"><strong>{result.status.replaceAll('_', ' ')}</strong><span>{STATUS_MESSAGES[result.status] ?? 'No recommendation could be produced for this cargo.'}</span></div>}
    {result?.explanation && <div className="decision-grid"><div className="main-column"><RecommendationPanel explanation={result.explanation} /><DecisionChart alternatives={result.optimization_result?.ranked_alternatives ?? []} /></div><div><EngineRoom vessels={result.vessel_feasibility?.vessels ?? []} ports={result.port_feasibility?.ports ?? []} candidateSet={result.candidate_set} costMatrixRowCount={result.cost_matrix_summary?.row_count ?? null} /></div></div>}
    {result && <WhatIfPanel onRun={onWhatIf} running={whatIfRunning} result={whatIfResult} />}
  </div>
}
