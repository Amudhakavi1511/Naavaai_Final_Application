import { useState } from 'react'
import type { CandidateSetSummary, PortCheckResult, VesselCheckResult } from '../types'
import { portLabel } from '../labels'

interface Props {
  vessels: VesselCheckResult[]
  ports: PortCheckResult[]
  candidateSet: CandidateSetSummary | null
  costMatrixRowCount: number | null
}

export default function EngineRoom({ vessels, ports, candidateSet, costMatrixRowCount }: Props) {
  const feasible = vessels.filter((v) => v.feasible).length
  const split = vessels.filter((v) => v.split_candidate).length
  const rejected = vessels.length - feasible - split
  const candidates = candidateSet ? candidateSet.candidates.filter((c) => !c.is_null).length : 0

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Working shown</h2>
          <p>Every check the engine ran before it ranked anything.</p>
        </div>
      </div>

      <Group title="Vessel checks" summary={`${feasible} usable, ${split} split-only, ${rejected} ruled out`}>
        {vessels.map((v) => (
          <div className="ev-row" key={v.vessel_id}>
            <span className={v.feasible ? 'flag flag--ok' : v.split_candidate ? 'flag flag--warn' : 'flag flag--bad'}>
              {v.feasible ? 'Usable' : v.split_candidate ? 'Split' : 'Ruled out'}
            </span>
            <strong>{v.vessel_id}</strong>
            <span>{v.vessel_class}</span>
            <em>{v.reason_text ?? (v.split_candidate ? 'Fits only as part of a split cargo.' : 'Clears every physical check.')}</em>
          </div>
        ))}
      </Group>

      <Group title="Port checks" summary={`${ports.filter((p) => p.feasible).length} of ${ports.length} usable`}>
        {ports.map((p) => (
          <div className="ev-row" key={p.port_id}>
            <span className={p.feasible ? 'flag flag--ok' : 'flag flag--bad'}>{p.feasible ? 'Usable' : 'Ruled out'}</span>
            <strong>{portLabel(p.port_id)}</strong>
            <span>{p.port_id}</span>
            <em>
              {p.feasible
                ? `Turnaround ${p.base_turnaround_days} days, plus ${p.current_congestion_days} days of congestion.`
                : p.reason_text}
            </em>
          </div>
        ))}
      </Group>

      <Group title="Pricing" summary={`${candidates} options priced over ${costMatrixRowCount ?? 0} scenario rows`}>
        <p>Each surviving vessel-and-strategy combination is priced against every market scenario, then ranked on expected cost and tail risk together.</p>
        {candidateSet?.generation_notes.length ? (
          <ul>{candidateSet.generation_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        ) : null}
      </Group>
    </section>
  )
}

function Group({ title, summary, children }: { title: string; summary: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="acc-item">
      <button className="acc-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        <strong>{title}</strong>
        <span>{summary}<i aria-hidden="true">{open ? '−' : '+'}</i></span>
      </button>
      {open && <div className="acc-body">{children}</div>}
    </div>
  )
}
