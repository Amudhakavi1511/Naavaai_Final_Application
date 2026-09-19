import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RankedAlternative } from '../types'

export default function DecisionChart({ alternatives }: { alternatives: RankedAlternative[] }) {
  if (alternatives.length < 2) {
    return (
      <section className="card">
        <div className="card-head"><h2>Alternatives considered</h2></div>
        <div className="card-body">
          <p className="card-note">Only one option cleared the feasibility checks, so there is nothing to compare it against.</p>
        </div>
      </section>
    )
  }

  const data = alternatives.map((a) => ({
    name: a.candidate_id,
    expected: Math.round(a.expected_cost),
    winner: a.rank === 1,
  }))

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Alternatives considered</h2>
          <p>Expected delivered cost for each option the engine priced. The recommended one is highlighted.</p>
        </div>
        <span className="card-note">US dollars</span>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dde4ea" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: '#4b5865', fontSize: 13 }} axisLine={{ stroke: '#c5cfd8' }} tickLine={false} />
            <YAxis
              tick={{ fill: '#4b5865', fontSize: 13 }} axisLine={{ stroke: '#c5cfd8' }} tickLine={false}
              tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} width={62}
            />
            <Tooltip
              cursor={{ fill: 'rgba(26,95,168,.06)' }}
              contentStyle={{ background: '#fff', border: '1px solid #c5cfd8', borderRadius: 3, fontSize: 14 }}
              formatter={(value) => [`$${Number(value).toLocaleString('en-US')}`, 'Expected cost']}
            />
            <Bar dataKey="expected" radius={[3, 3, 0, 0]} maxBarSize={72}>
              {data.map((d) => <Cell key={d.name} fill={d.winner ? '#1a5fa8' : '#9fb1c2'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
