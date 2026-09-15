import type { CargoRequirement } from '../types'

interface Props {
  cargo: CargoRequirement
  onChange: (cargo: CargoRequirement) => void
  onRun: () => void
  running: boolean
}

const PORTS = ['IN-PARADIP', 'IN-VIZAG', 'IN-GANGAVARAM', 'IN-GOPALPUR', 'IN-DHAMRA', 'IN-HALDIA']
const ORIGIN_COUNTRIES = ['AUSTRALIA', 'UNITED STATES', 'RUSSIA', 'MOZAMBIQUE', 'INDONESIA', 'SOUTH AFRICA']

export default function CargoForm({ cargo, onChange, onRun, running }: Props) {
  const set = <K extends keyof CargoRequirement>(key: K, value: CargoRequirement[K]) =>
    onChange({ ...cargo, [key]: value })

  return (
    <div className="cargo-panel px-5 py-4">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <div><h2 className="text-sm font-semibold tracking-tight">Procurement requirements</h2><p className="text-xs text-ink-dim">Define cargo, route, delivery deadline and risk appetite.</p></div>
        <span className="form-context">Analysis inputs</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Commodity"><input className="field" value={cargo.commodity} onChange={(e) => set('commodity', e.target.value)} /></Field>
        <Field label="Quantity (t)"><input type="number" min="1" className="field font-data" value={cargo.quantity_tonnes} onChange={(e) => set('quantity_tonnes', Number(e.target.value))} /></Field>
        <Field label="Procurement country"><select className="field" value={cargo.origin_country} onChange={(e) => set('origin_country', e.target.value)}>{ORIGIN_COUNTRIES.map((country) => <option key={country} value={country}>{country}</option>)}</select></Field>
        <Field label="Destination"><select className="field" value={cargo.destination_port_id} onChange={(e) => set('destination_port_id', e.target.value)}>{PORTS.map((p) => <option key={p} value={p}>{p.replace('IN-', '')}</option>)}</select></Field>
        <Field label="Delivery deadline"><input type="date" className="field font-data" value={cargo.delivery_deadline} onChange={(e) => set('delivery_deadline', e.target.value)} /></Field>
        <Field label="Risk appetite"><select className="field" value={cargo.risk_preference} onChange={(e) => set('risk_preference', e.target.value as CargoRequirement['risk_preference'])}><option value="LOW">Risk averse</option><option value="BALANCED">Balanced</option><option value="HIGH">Cost focused</option></select></Field>
        <div className="flex items-end"><button onClick={onRun} disabled={running} className="w-full bg-brass px-4 py-2 font-semibold text-hull transition-colors hover:bg-brass-dim disabled:opacity-50">{running ? 'Analyzing…' : 'Analyze options'}</button></div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="flex flex-col gap-1"><span className="text-xs text-ink-dim">{label}</span>{children}</label>
}

