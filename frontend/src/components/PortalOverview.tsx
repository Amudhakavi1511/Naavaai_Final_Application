import type { Bootstrap, DecisionEngineResponse } from '../types'
import type { Page } from './AppShell'
import { usd } from '../format'
import { portLabel } from '../labels'

interface Props { result: DecisionEngineResponse | null; reference: Bootstrap; onGo: (page: Page) => void }

export default function PortalOverview({ result, reference, onGo }: Props) {
  const decision = result?.explanation?.decision
  const originPortCount = reference.origins.reduce((n, c) => n + c.ports.length, 0)

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p className="lede">
            Naavaai turns an overseas dry-bulk requirement into a chartering decision you can defend:
            which vessel, on what terms, through which East Coast gateway, and what it is likely to cost.
          </p>
        </div>
        <span className="chip chip--ok"><span className="dot" aria-hidden="true" />All services running</span>
      </div>

      <section className="card banner">
        <div>
          <h2>Freight markets move. Your procurement decision should account for that.</h2>
          <p>
            Start at the decision desk with a cargo requirement. The engine checks what is physically
            possible, prices every workable option across a bank of market scenarios, and explains the
            one it recommends.
          </p>
        </div>
        <button className="btn btn--primary" onClick={() => onGo('decision')}>Open the decision desk</button>
      </section>

      <div className="tiles">
        <Tile head="Decision engine" value={decision ? 'Recommendation ready' : 'Idle'} note="Feasibility, cost, risk and ranking" />
        <Tile head="Market scenarios" value={`${reference.scenario_bank.scenario_count} futures`} note="Every option priced against all of them" />
        <Tile head="Gateways covered" value={`${reference.discharge_ports.length} East Coast ports`} note={[...new Set(reference.discharge_ports.map((p) => p.state))].join(', ')} />
        <Tile head="Loading ports" value={`${originPortCount} across ${reference.origins.length} countries`} note={reference.origins.slice(0, 4).map((c) => c.country).join(', ')} />
      </div>

      <div className="two-col">
        <section className="card">
          <div className="card-head"><h2>Latest result</h2></div>
          {decision ? (
            <div className="headline-decision">
              <span className="chip chip--ok">Recommended</span>
              <strong>{decision.strategy_label}</strong>
              <p>{portLabel(decision.origin_port_id)} → {portLabel(decision.destination_port_id)}, {decision.total_tonnage.toLocaleString('en-IN')} tonnes</p>
              <div className="stats stats--2">
                <div className="stat"><span>Expected delivered cost</span><strong>{usd(decision.expected_cost)}</strong></div>
                <div className="stat"><span>Worst-case average (CVaR 80)</span><strong>{usd(decision.cvar_80)}</strong></div>
              </div>
            </div>
          ) : (
            <div className="empty">
              <strong>No analysis run yet</strong>
              <p>Enter a cargo requirement at the decision desk and the result will appear here.</p>
              <button className="btn btn--ghost" onClick={() => onGo('decision')}>Go to the decision desk</button>
            </div>
          )}
        </section>

        <section className="card">
          <div className="card-head"><h2>Where to go next</h2></div>
          <div className="linklist">
            <button onClick={() => onGo('decision')}>
              <strong>Decision desk</strong>
              <span>Turn a cargo requirement into a ranked, explained recommendation.</span>
            </button>
            <button onClick={() => onGo('intelligence')}>
              <strong>Market intelligence</strong>
              <span>See the freight outlook and the scenarios feeding the engine.</span>
            </button>
            <button onClick={() => onGo('ports')}>
              <strong>Port intelligence</strong>
              <span>Compare draft, handling and congestion at each East Coast gateway.</span>
            </button>
            <button onClick={() => onGo('whatif')}>
              <strong>What-if analysis</strong>
              <span>Check whether the recommendation survives a worse market.</span>
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}

function Tile({ head, value, note }: { head: string; value: string; note: string }) {
  return (
    <div className="card tile">
      <span>{head}</span>
      <strong>{value}</strong>
      <span>{note}</span>
    </div>
  )
}
