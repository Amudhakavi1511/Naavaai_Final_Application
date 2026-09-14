import type { Explanation } from '../types'
import { usd, riskColor } from '../format'

export default function RecommendationPanel({ explanation }: { explanation: Explanation }) {
  const d = explanation.decision
  return (
    <div className="border-l-4 border-brass bg-panel px-5 py-4">
      <div className="mb-1 text-xs uppercase tracking-wide text-ink-dim">Recommendation</div>
      <h2 className="mb-3 text-xl font-semibold leading-snug">{explanation.headline}</h2>

      <div className="mb-4 grid grid-cols-2 gap-x-6 gap-y-2 font-data text-sm sm:grid-cols-4">
        <Stat label="Strategy" value={d.strategy_label} />
        <Stat label="Route" value={`${d.origin_port_id} → ${d.destination_port_id}`} />
        <Stat label="Expected cost" value={usd(d.expected_cost)} />
        <Stat label="Risk (CVaR 80)" value={usd(d.cvar_80)} accent={riskColor(d.risk_label)} />
      </div>

      <div className="mb-4 divide-y divide-hairline border-y border-hairline">
        {d.legs.map((leg) => (
          <div key={leg.candidate_id} className="flex flex-wrap items-baseline justify-between gap-2 py-2 font-data text-sm">
            <span>{leg.vessel_id} <span className="text-ink-dim">({leg.vessel_class})</span></span>
            <span className="text-ink-dim">{leg.strategy} · {leg.charter_epoch}</span>
            <span>{leg.tonnage.toLocaleString()} t</span>
          </div>
        ))}
      </div>

      <div className="mb-3">
        <div className="mb-1 text-xs uppercase tracking-wide text-ink-dim">Why this decision</div>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm leading-relaxed">
          {explanation.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ol>
      </div>

      {explanation.warnings.length > 0 && (
        <div className="border border-rust/40 bg-rust/10 px-3 py-2">
          <div className="mb-1 text-xs uppercase tracking-wide text-rust">Worth reviewing</div>
          <ul className="space-y-1 text-sm">
            {explanation.warnings.map((w, i) => (
              <li key={i} className="text-ink">{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="font-display text-xs text-ink-dim">{label}</div>
      <div className={accent ?? ''}>{value}</div>
    </div>
  )
}
