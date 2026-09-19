import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Bootstrap } from '../types'

const forecast = [
  { month: 'Sep 26', p10: 27, p50: 34, p90: 44 },
  { month: 'Oct 26', p10: 28, p50: 35, p90: 47 },
  { month: 'Nov 26', p10: 29, p50: 37, p90: 51 },
  { month: 'Dec 26', p10: 30, p50: 39, p90: 54 },
  { month: 'Jan 27', p10: 31, p50: 41, p90: 57 },
  { month: 'Feb 27', p10: 30, p50: 40, p90: 55 },
]

const sources: [string, string, string][] = [
  ['Freight indices', 'Route-level rates and index movements', 'Connected'],
  ['Port operations', 'Observed turnaround and queue times', 'Connected'],
  ['Fleet register', 'Capacity, dimensions and open positions', 'Connected'],
  ['Commodity and bunker', 'Cargo prices and fuel costs', 'Connected'],
]

export default function IntelligenceLayer({ reference }: { reference: Bootstrap }) {
  const bank = reference.scenario_bank
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Market intelligence</h1>
          <p className="lede">
            What the freight market is expected to do, how confident that expectation is, and which
            signals are pushing it. The decision engine consumes the full range, not the midpoint.
          </p>
        </div>
        <span className="chip chip--ok"><span className="dot" aria-hidden="true" />Refreshed today</span>
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Freight outlook, Australia to East Coast India</h2>
              <p>Shaded band shows the range the market could plausibly land in; the line is the central estimate.</p>
            </div>
            <span className="card-note">US dollars per tonne</span>
          </div>
          <div className="chart-body">
            <div className="legend">
              <span><i aria-hidden="true" />Central estimate</span>
              <span><i className="band" aria-hidden="true" />Plausible range</span>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={forecast} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#dde4ea" vertical={false} />
                <XAxis dataKey="month" tick={{ fill: '#4b5865', fontSize: 13 }} axisLine={{ stroke: '#c5cfd8' }} tickLine={false} />
                <YAxis tick={{ fill: '#4b5865', fontSize: 13 }} axisLine={{ stroke: '#c5cfd8' }} tickLine={false} width={54} domain={[20, 60]} tickFormatter={(v: number) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #c5cfd8', borderRadius: 3, fontSize: 14 }}
                  formatter={(v, name) => [`$${v}/t`, name === 'p50' ? 'Central' : name === 'p90' ? 'Upper' : 'Lower']}
                />
                <Area type="monotone" dataKey="p90" stroke="#9ab3c8" fill="#dbe8f2" fillOpacity={1} strokeWidth={1} />
                <Area type="monotone" dataKey="p10" stroke="#9ab3c8" fill="#ffffff" fillOpacity={1} strokeWidth={1} />
                <Area type="monotone" dataKey="p50" stroke="#1a5fa8" fill="none" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
            <div className="chart-foot">
              <span>The range widens further out, because it should.</span>
              <span>Forecast runs to {bank.horizon_end}</span>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <div><h2>Market scenarios</h2></div>
            <span className="chip chip--ok">Ready</span>
          </div>
          <div className="figure-lead">
            <strong>{bank.scenario_count}</strong>
            <span>representative futures the engine prices every option against</span>
          </div>
          <div className="stats stats--3">
            <div className="stat"><span>Paths simulated</span><strong>200–500</strong></div>
            <div className="stat"><span>Quantiles kept</span><strong>3</strong></div>
            <div className="stat"><span>Fleet size</span><strong>{reference.fleet_size}</strong></div>
          </div>
          <div className="bars">
            <Bar label="Freight" value={82} />
            <Bar label="Bunker fuel" value={64} />
            <Bar label="Commodity" value={57} />
            <Bar label="Congestion" value={41} />
          </div>
          <p className="callout">
            Scenarios keep the relationships between freight, fuel, cargo prices and port conditions
            intact, so a bad market shows up as a bad market everywhere at once rather than in one
            variable at a time.
          </p>
        </section>
      </div>

      <div className="grid-3">
        <section className="card">
          <div className="card-head"><h2>Data sources</h2></div>
          <div className="rowlist">
            {sources.map(([name, detail, state]) => (
              <div key={name}>
                <strong>{name}</strong>
                <em>{state}</em>
                <p>{detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-head"><h2>What is moving the market</h2></div>
          <div>
            <div className="driver"><span>Freight rates</span><strong>Rising, moderately</strong><small>Seasonal demand and route repositioning</small></div>
            <div className="driver"><span>Bunker prices</span><strong>Steady</strong><small>No sustained direction in the current scenarios</small></div>
            <div className="driver"><span>Port congestion</span><strong>Elevated</strong><small>Turnaround times remain uncertain at several gateways</small></div>
          </div>
        </section>

        <section className="card">
          <div className="card-head"><h2>Model controls</h2></div>
          <div className="rowlist">
            <div><strong>Forecast refresh</strong><em>Daily</em></div>
            <div><strong>Scenario generation</strong><em>Per analysis</em></div>
            <div><strong>Input drift</strong><em>Monitored</em></div>
            <div><strong>Forecast error drift</strong><em>Monitored</em></div>
          </div>
          <p className="callout">
            Forecasts and scenarios are versioned and traceable to their inputs, so a past
            recommendation can be reproduced exactly as it was made.
          </p>
        </section>
      </div>
    </div>
  )
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="bar">
      <span>{label}</span>
      <div className="bar-track"><i style={{ width: `${value}%` }} /></div>
      <strong>{value}%</strong>
    </div>
  )
}
