import { useState } from 'react'
import type { Explanation } from '../types'
import { usd } from '../format'
import { portLabel } from '../labels'

const RISK_TONE: Record<string, string> = { LOW: 'is-ok', HIGH: 'is-bad' }

export default function RecommendationPanel({ explanation }: { explanation: Explanation }) {
  const [open, setOpen] = useState(false)
  const d = explanation.decision

  return (
    <section className="card rec">
      <div className="rec-band">
        <div>
          <h2>{explanation.headline}</h2>
          <p>Ranked first on risk-adjusted delivered cost across every feasible vessel and charter strategy.</p>
        </div>
        <span className="rec-badge">Recommended</span>
      </div>

      <div className="route">
        <span><b>{d.total_tonnage.toLocaleString('en-IN')}</b> tonnes</span>
        <span>{portLabel(d.origin_port_id)} → {portLabel(d.destination_port_id)}</span>
        <span>Risk stance: {d.risk_label.toLowerCase()}</span>
      </div>

      <div className="stats stats--4">
        <Stat label="Expected delivered cost" value={usd(d.expected_cost)} />
        <Stat label="Worst-case average (CVaR 80)" value={usd(d.cvar_80)} tone={RISK_TONE[d.risk_label] ?? 'is-warn'} />
        <Stat label="Charter strategy" value={d.strategy_label} />
        <Stat label="Vessels" value={d.legs.map((l) => l.vessel_id).join(', ') || '—'} />
      </div>

      <div className="rec-actions">
        <button className="btn btn--ghost" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? 'Hide the reasoning' : 'Show the reasoning'}
        </button>
      </div>

      {open && (
        <div className="rec-details">
          <div>
            <h3>How the cargo is allocated</h3>
            {d.legs.map((leg) => (
              <div className="leg" key={leg.candidate_id}>
                <strong>{leg.vessel_id}</strong>
                <span>{leg.vessel_class} · {leg.strategy.toLowerCase().replaceAll('_', ' ')} · laycan {leg.charter_epoch}</span>
                <b>{leg.tonnage.toLocaleString('en-IN')} t</b>
              </div>
            ))}
          </div>

          <div>
            <h3>Why this option won</h3>
            <ul className="reasons">
              {explanation.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>

          {explanation.warnings.length > 0 && (
            <div className="notice notice--warn">
              <strong>Check these before you fix the charter</strong>
              <ul>{explanation.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return <div className="stat"><span>{label}</span><strong className={tone}>{value}</strong></div>
}
