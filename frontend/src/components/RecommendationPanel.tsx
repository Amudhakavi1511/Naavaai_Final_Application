import { useState } from 'react'
import type { Explanation } from '../types'
import { usd, riskColor } from '../format'

export default function RecommendationPanel({ explanation }: { explanation: Explanation }) {
  const d = explanation.decision
  const [open, setOpen] = useState<string | null>(null)
  const [showRationale, setShowRationale] = useState(false)

  const primaryVessel = d.legs[0]
  const cards = [
    {
      id: 'cost',
      label: 'Expected cost',
      value: usd(d.expected_cost),
      hint: 'Scenario-weighted procurement cost',
      tone: 'gold',
      detail: `Expected delivered cost across the evaluated market scenarios. This includes the selected strategy's applicable freight or hire, port, waiting, deadhead and demurrage/despatch economics.`,
    },
    {
      id: 'risk',
      label: 'Tail risk · CVaR 80',
      value: usd(d.cvar_80),
      hint: d.cvar_status === 'NOT_MEANINGFUL_SAMPLE_SIZE' ? 'Sample size too small for CVaR' : `${d.risk_label} risk profile`,
      tone: d.risk_label === 'HIGH' ? 'risk-high' : d.risk_label === 'LOW' ? 'risk-low' : 'risk',
      detail: `CVaR 80 focuses on the expensive tail of the scenario distribution. Current risk preference is ${d.risk_preference.replaceAll('_', ' ').toLowerCase()}.`,
    },
    {
      id: 'strategy',
      label: 'Recommended strategy',
      value: d.strategy_label,
      hint: 'Selected procurement approach',
      tone: 'sea',
      detail: `The selected strategy is evaluated against the feasible alternatives before the final risk-aware ranking.`,
    },
    {
      id: 'vessel',
      label: 'Recommended vessel',
      value: primaryVessel?.vessel_id ?? 'Multiple vessels',
      hint: primaryVessel ? `${primaryVessel.vessel_class} · ${d.total_tonnage.toLocaleString()} t` : `${d.total_tonnage.toLocaleString()} t`,
      tone: 'blue',
      detail: primaryVessel
        ? `Selected ${primaryVessel.vessel_id} (${primaryVessel.vessel_class}) for ${primaryVessel.tonnage.toLocaleString()} t under ${primaryVessel.strategy}.`
        : 'The recommendation uses a multi-vessel allocation.',
    },
  ]

  return (
    <section className="recommendation-panel panel">
      <div className="recommendation-topline">
        <div>
          <div className="panel-kicker">Procurement recommendation</div>
          <h2>{explanation.headline}</h2>
          <div className="recommendation-route">
            <span>{d.origin_port_id}</span><span className="route-arrow">→</span><span>{d.destination_port_id}</span>
            <span className="route-separator">•</span><span>{d.total_tonnage.toLocaleString()} t</span>
          </div>
        </div>
        <span className={`decision-badge ${riskColor(d.risk_label)}`}>{d.risk_label} RISK</span>
      </div>

      <div className="decision-metric-grid">
        {cards.map((card) => {
          const isOpen = open === card.id
          return (
            <button
              key={card.id}
              type="button"
              className={`decision-metric-card ${card.tone} ${isOpen ? 'expanded' : ''}`}
              onClick={() => setOpen(isOpen ? null : card.id)}
              aria-expanded={isOpen}
            >
              <span className="metric-label">{card.label}</span>
              <strong>{card.value}</strong>
              <span className="metric-hint">{card.hint}</span>
              <span className="metric-action">{isOpen ? 'Hide details' : 'View details'} <span>{isOpen ? '↑' : '↓'}</span></span>
              {isOpen && <span className="metric-detail">{card.detail}</span>}
            </button>
          )
        })}
      </div>

      <button
        type="button"
        className={`rationale-toggle ${showRationale ? 'open' : ''}`}
        onClick={() => setShowRationale(!showRationale)}
        aria-expanded={showRationale}
      >
        <span><span className="rationale-dot" /> Decision rationale</span>
        <span>{showRationale ? 'Hide explanation ↑' : 'Show explanation ↓'}</span>
      </button>

      {showRationale && (
        <div className="rationale-body">
          <div className="rationale-columns">
            <div>
              <div className="rationale-title">Why this decision</div>
              <ol>
                {explanation.reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ol>
            </div>
            <div>
              <div className="rationale-title">Selected allocation</div>
              <div className="leg-list">
                {d.legs.map((leg) => (
                  <div key={leg.candidate_id} className="leg-row">
                    <div><strong>{leg.vessel_id}</strong><span>{leg.vessel_class}</span></div>
                    <div><strong>{leg.tonnage.toLocaleString()} t</strong><span>{leg.strategy} · {leg.charter_epoch}</span></div>
                  </div>
                ))}
              </div>
              {explanation.warnings.length > 0 && (
                <div className="warning-box">
                  <strong>Worth reviewing</strong>
                  {explanation.warnings.map((w, i) => <span key={i}>{w}</span>)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
