import { useState } from 'react'
import type { CandidateSetSummary, PortCheckResult, VesselCheckResult } from '../types'

interface Props { vessels: VesselCheckResult[]; ports: PortCheckResult[]; candidateSet: CandidateSetSummary | null; costMatrixRowCount: number | null }

export default function EngineRoom({ vessels, ports, candidateSet, costMatrixRowCount }: Props) {
  const feasibleCount = vessels.filter((v) => v.feasible).length
  const splitCount = vessels.filter((v) => v.split_candidate).length
  const rejectedCount = vessels.length - feasibleCount - splitCount
  const candidateCount = candidateSet ? candidateSet.candidates.filter((c) => !c.is_null).length : 0

  return <div className="border border-hairline bg-panel">
    <div className="border-b border-hairline px-5 py-3"><div className="panel-kicker">Decision analysis</div><h2 className="text-sm font-semibold mt-1">Feasibility & candidate review</h2></div>
    <Section title="Vessel feasibility" summary={`${feasibleCount} feasible · ${splitCount} split-ready · ${rejectedCount} rejected`}>
      <div className="divide-y divide-hairline">{vessels.map((v) => <div key={v.vessel_id} className="flex flex-wrap items-baseline justify-between gap-2 py-1.5 font-data text-xs"><span className={v.feasible ? 'text-sea' : v.split_candidate ? 'text-brass' : 'text-rust'}>{v.feasible ? '✓' : v.split_candidate ? '△' : '✗'} {v.vessel_id} <span className="text-ink-dim">({v.vessel_class})</span></span><span className="text-ink-dim">{v.reason_text ?? (v.split_candidate ? 'split-ready' : 'feasible')}</span></div>)}</div>
    </Section>
    <Section title="Port feasibility" summary={`${ports.filter((p) => p.feasible).length}/${ports.length} feasible`}>
      <div className="divide-y divide-hairline">{ports.map((p) => <div key={p.port_id} className="flex flex-wrap items-baseline justify-between gap-2 py-1.5 font-data text-xs"><span className={p.feasible ? 'text-sea' : 'text-rust'}>{p.feasible ? '✓' : '✗'} {p.port_id}</span><span className="text-ink-dim">{p.feasible ? `turnaround ${p.base_turnaround_days}d + congestion ${p.current_congestion_days}d` : p.reason_text}</span></div>)}</div>
    </Section>
    <Section title="Candidate economics" summary={`${candidateCount} candidates · ${costMatrixRowCount ?? 0} scenario rows`} last>
      <p className="text-xs text-ink-dim">Feasible vessel and strategy combinations are priced across the available market scenarios before risk-adjusted ranking.</p>
      {candidateSet?.generation_notes.length ? <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-ink-dim">{candidateSet.generation_notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : null}
    </Section>
  </div>
}

function Section({ title, summary, children, last }: { title: string; summary: string; children: React.ReactNode; last?: boolean }) {
  const [open, setOpen] = useState(false)
  return <div className={last ? '' : 'border-b border-hairline'}><button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-3 text-left transition-colors hover:bg-panel-raised"><span className="text-sm">{title}</span><span className="font-data text-xs text-ink-dim">{summary} {open ? '▾' : '▸'}</span></button>{open && <div className="px-5 pb-4">{children}</div>}</div>
}
