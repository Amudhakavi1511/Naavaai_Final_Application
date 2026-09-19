import { useState } from 'react'
import type { WhatIfChanges, WhatIfResponse } from '../types'
import { usd } from '../format'

interface Props {
  onRun: (changes: WhatIfChanges) => void
  running: boolean
  result: WhatIfResponse | null
}

const DEFAULTS: WhatIfChanges = {
  freight_shock_pct: 0,
  congestion_shock_days: 0,
  deadline_shift_days: 0,
  risk_preference: null,
  vessel_availability_shock_days: 0,
}

export default function WhatIfPanel({ onRun, running, result }: Props) {
  const [changes, setChanges] = useState<WhatIfChanges>(DEFAULTS)
  const touched = JSON.stringify(changes) !== JSON.stringify(DEFAULTS)

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Test the recommendation against a different market</h2>
          <p>Move an assumption and the same engine runs again on the changed inputs. Nothing separate, nothing approximated.</p>
        </div>
        {touched && (
          <button className="btn btn--ghost" onClick={() => setChanges(DEFAULTS)}>Reset assumptions</button>
        )}
      </div>

      <div className="slider-grid">
        <Slider
          label="Freight rates move by" value={changes.freight_shock_pct}
          min={-30} max={50} step={5} format={(v) => `${v > 0 ? '+' : ''}${v}%`}
          onChange={(v) => setChanges({ ...changes, freight_shock_pct: v })}
        />
        <Slider
          label="Extra port congestion" value={changes.congestion_shock_days}
          min={0} max={10} step={1} format={(v) => `${v} days`}
          onChange={(v) => setChanges({ ...changes, congestion_shock_days: v })}
        />
        <Slider
          label="Deadline moves by" value={changes.deadline_shift_days}
          min={-10} max={10} step={1} format={(v) => `${v > 0 ? '+' : ''}${v} days`}
          onChange={(v) => setChanges({ ...changes, deadline_shift_days: v })}
        />
        <Slider
          label="Vessels delayed by" value={changes.vessel_availability_shock_days}
          min={0} max={30} step={2} format={(v) => `${v} days`}
          onChange={(v) => setChanges({ ...changes, vessel_availability_shock_days: v })}
        />
        <label className="field">
          <span>Risk preference</span>
          <select
            className="control"
            value={changes.risk_preference ?? ''}
            onChange={(e) => setChanges({ ...changes, risk_preference: (e.target.value || null) as WhatIfChanges['risk_preference'] })}
          >
            <option value="">Leave as requested</option>
            <option value="LOW">Protect against bad outcomes</option>
            <option value="BALANCED">Balanced</option>
            <option value="HIGH">Chase the lowest expected cost</option>
          </select>
        </label>
      </div>

      <div className="form-foot">
        <p>The engine solves the baseline and the changed case, then compares them.</p>
        <button className="btn btn--primary" onClick={() => onRun(changes)} disabled={running}>
          {running ? 'Running…' : 'Run the comparison'}
        </button>
      </div>

      {result && (
        <div className={`delta ${result.delta.decision_changed ? 'changed' : 'held'}`}>
          <strong>{result.delta.decision_changed ? 'The recommendation would change' : 'The recommendation holds'}</strong>
          <p>{result.delta.summary}</p>
          <div className="stats stats--4">
            <Stat label="Cost as requested" value={result.baseline.optimization_result ? usd(result.baseline.optimization_result.expected_cost) : result.baseline.status} />
            <Stat label="Cost under these changes" value={result.modified.optimization_result ? usd(result.modified.optimization_result.expected_cost) : result.modified.status} />
            <Stat label="Vessels as requested" value={result.delta.baseline_winning_vessel_ids.join(', ') || '—'} />
            <Stat label="Vessels under these changes" value={result.delta.modified_winning_vessel_ids.join(', ') || '—'} />
          </div>
        </div>
      )}
    </section>
  )
}

function Slider({
  label, value, min, max, step, format, onChange,
}: { label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onChange: (v: number) => void }) {
  return (
    <label className="slider">
      <span><span>{label}</span><b>{format(value)}</b></span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong></div>
}
