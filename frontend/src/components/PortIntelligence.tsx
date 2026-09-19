import type { Bootstrap } from '../types'

export default function PortIntelligence({ reference }: { reference: Bootstrap }) {
  const ports = reference.discharge_ports

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Port intelligence</h1>
          <p className="lede">
            The gateway you discharge at changes which vessels can call, how long they wait, and how
            much the voyage ends up costing. These are the same figures the feasibility checks use.
          </p>
        </div>
        <span className="chip">{ports.length} East Coast gateways</span>
      </div>

      <div className="notice notice--info">
        <strong>Read these as indicative</strong>
        <span>
          Draft, berth availability and handling rates depend on tide, weather, vessel dimensions and
          terminal agreements. The figures here are the reference values the engine solves against,
          not a berth guarantee or a regulatory certification.
        </span>
      </div>

      <section className="card">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Gateway</th>
              <th scope="col">Maximum draft</th>
              <th scope="col">Berths</th>
              <th scope="col">Handling rate</th>
              <th scope="col">Turnaround</th>
              <th scope="col">Congestion now</th>
            </tr>
          </thead>
          <tbody>
            {ports.map((p) => (
              <tr key={p.port_id}>
                <td><strong>{p.name}</strong><small>{p.state} · {p.port_id}</small></td>
                <td className="t-num">{p.max_draft_m.toFixed(1)} m</td>
                <td className="t-num">{p.berth_count}</td>
                <td className="t-num">{p.cargo_handling_rate_tonnes_per_day.toLocaleString('en-IN')} t/day</td>
                <td className="t-num">{p.base_turnaround_days.toFixed(1)} days</td>
                <td className={p.current_congestion_days >= 4 ? 't-warn' : 't-ok'}>
                  {p.current_congestion_days.toFixed(1)} days
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <p className="card-note">
        Turnaround is the inherent handling and berthing time. Congestion is added on top of it, and
        is what the what-if analysis shocks when you test a worse port situation.
      </p>
    </div>
  )
}
