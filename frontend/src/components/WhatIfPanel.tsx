import { useState } from 'react'
import type { WhatIfChanges, WhatIfResponse } from '../types'
import { pct, usd } from '../format'

interface Props {
  onRun: (changes: WhatIfChanges) => void
  running: boolean
  result: WhatIfResponse | null
}

const DEFAULT_CHANGES: WhatIfChanges = {
  freight_shock_pct: 0,
  congestion_shock_days: 0,
  deadline_shift_days: 0,
  risk_preference: null,
  vessel_availability_shock_days: 0,
}

export default function WhatIfPanel({ onRun, running, result }: Props) {
  const [changes, setChanges] = useState<WhatIfChanges>(DEFAULT_CHANGES)

  return (
    <div className="border border-hairline bg-panel px-5 py-4">
      <div className="mb-1 text-xs uppercase tracking-wide text-ink-dim">Sensitivity analysis — what if…</div>
      <p className="mb-3 text-sm text-ink-dim">
        Adjust the market or fleet and re-run the same decision engine — no separate logic, just a different input.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <SliderField
          label="Freight shock"
          value={changes.freight_shock_pct}
          min={-30} max={50} step={5}
          format={(v) => pct(v)}
          onChange={(v) => setChanges({ ...changes, freight_shock_pct: v })}
        />
        <SliderField
          label="Congestion +days"
          value={changes.congestion_shock_days}
          min={0} max={10} step={1}
          format={(v) => `${v}d`}
          onChange={(v) => setChanges({ ...changes, congestion_shock_days: v })}
        />
        <SliderField
          label="Deadline shift"
          value={changes.deadline_shift_days}
          min={-10} max={10} step={1}
          format={(v) => `${v >= 0 ? '+' : ''}${v}d`}
          onChange={(v) => setChanges({ ...changes, deadline_shift_days: v })}
        />
        <SliderField
          label="Vessel availability shock"
          value={changes.vessel_availability_shock_days}
          min={0} max={30} step={2}
          format={(v) => `${v}d`}
          onChange={(v) => setChanges({ ...changes, vessel_availability_shock_days: v })}
        />
        <div className="flex flex-col gap-1">
          <span className="text-xs text-ink-dim">Risk preference override</span>
          <select
            className="field"
            value={changes.risk_preference ?? ''}
            onChange={(e) => setChanges({ ...changes, risk_preference: (e.target.value || null) as WhatIfChanges['risk_preference'] })}
          >
            <option value="">Unchanged</option>
            <option value="LOW">Low tolerance</option>
            <option value="BALANCED">Balanced</option>
            <option value="HIGH">High tolerance</option>
          </select>
        </div>
      </div>

      <button
        onClick={() => onRun(changes)}
        disabled={running}
        className="mt-4 bg-brass px-4 py-2 text-sm font-semibold text-hull transition-colors hover:bg-brass-dim disabled:opacity-50"
      >
        {running ? 'Running…' : 'Run what-if'}
      </button>

      {result && (
        <div className="mt-4 border-t border-hairline pt-4">
          <div className={`mb-2 text-sm font-semibold ${result.delta.decision_changed ? 'text-rust' : 'text-sea'}`}>
            {result.delta.decision_changed ? 'Decision would change' : 'Decision holds'}
          </div>
          <p className="mb-3 text-sm">{result.delta.summary}</p>
          <div className="grid grid-cols-2 gap-4 font-data text-sm sm:grid-cols-4">
            <MiniStat label="Baseline" value={result.baseline.optimization_result ? usd(result.baseline.optimization_result.expected_cost) : result.baseline.status} />
            <MiniStat label="Modified" value={result.modified.optimization_result ? usd(result.modified.optimization_result.expected_cost) : result.modified.status} />
            <MiniStat label="Baseline vessel(s)" value={result.delta.baseline_winning_vessel_ids.join(', ') || '—'} />
            <MiniStat label="Modified vessel(s)" value={result.delta.modified_winning_vessel_ids.join(', ') || '—'} />
          </div>
        </div>
      )}
    </div>
  )
}

function SliderField({
  label, value, min, max, step, format, onChange,
}: { label: string; value: number; min: number; max: number; step: number; format: (v: number) => string; onChange: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="flex justify-between text-xs text-ink-dim">
        <span>{label}</span>
        <span className="font-data text-ink">{format(value)}</span>
      </span>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="accent-brass"
      />
    </label>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-display text-xs text-ink-dim">{label}</div>
      <div>{value}</div>
    </div>
  )
}
