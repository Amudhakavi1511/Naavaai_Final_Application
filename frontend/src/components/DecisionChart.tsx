import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RankedAlternative } from '../types'

export default function DecisionChart({ alternatives }: { alternatives: RankedAlternative[] }) {
  if (alternatives.length < 2) {
    return (
      <div className="border border-hairline bg-panel px-5 py-4 text-sm text-ink-dim">
        Only one viable candidate — no alternatives to compare.
      </div>
    )
  }
  const data = alternatives.map((a) => ({
    name: a.candidate_id,
    expected: Math.round(a.expected_cost),
    cvar: Math.round(a.cvar),
    isWinner: a.rank === 1,
  }))

  return (
    <div className="border border-hairline bg-panel px-5 py-4">
      <div className="mb-3 text-xs uppercase tracking-wide text-ink-dim">Decision Chart — expected cost by candidate</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 4" stroke="#2A3B52" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#9FB0C4', fontSize: 11 }} axisLine={{ stroke: '#2A3B52' }} tickLine={false} />
          <YAxis tick={{ fill: '#9FB0C4', fontSize: 11 }} axisLine={{ stroke: '#2A3B52' }} tickLine={false}
                 tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            contentStyle={{ background: '#16273D', border: '1px solid #2A3B52', color: '#EDE8DD', fontSize: 12 }}
            formatter={(value) => `$${Number(value).toLocaleString()}`}
          />
          <Bar dataKey="expected" radius={[2, 2, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.name} fill={d.isWinner ? '#C98A3B' : '#3A4E68'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
