import type { DecisionEngineResponse } from '../types'
import { usd } from '../format'
import { portLabel } from '../labels'

export default function DecisionRegister({ decisions }: { decisions: DecisionEngineResponse[] }) {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Decision register</h1>
          <p className="lede">Every analysis run during this session, kept so a recommendation can be traced back to the request that produced it.</p>
        </div>
        <span className="chip">{decisions.length} {decisions.length === 1 ? 'record' : 'records'}</span>
      </div>

      <section className="card">
        {decisions.length === 0 ? (
          <div className="empty">
            <strong>Nothing recorded yet</strong>
            <p>Completed analyses appear here with their request reference, route, chosen strategy and cost figures.</p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Request</th>
                <th scope="col">Route</th>
                <th scope="col">Strategy</th>
                <th scope="col">Expected cost</th>
                <th scope="col">CVaR 80</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((r) => {
                const d = r.explanation?.decision
                return (
                  <tr key={r.request_id}>
                    <td className="t-num">{r.request_id}</td>
                    <td>{d ? `${portLabel(d.origin_port_id)} → ${portLabel(d.destination_port_id)}` : '—'}</td>
                    <td><strong>{d?.strategy_label ?? r.status.replaceAll('_', ' ').toLowerCase()}</strong></td>
                    <td className="t-num">{d ? usd(d.expected_cost) : '—'}</td>
                    <td className="t-num">{d ? usd(d.cvar_80) : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
