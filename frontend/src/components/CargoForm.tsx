import type { Bootstrap, CargoRequirement } from '../types'

interface Props {
  cargo: CargoRequirement
  reference: Bootstrap
  onChange: (cargo: CargoRequirement) => void
  onRun: () => void
  running: boolean
}

export default function CargoForm({ cargo, reference, onChange, onRun, running }: Props) {
  const set = <K extends keyof CargoRequirement>(key: K, value: CargoRequirement[K]) =>
    onChange({ ...cargo, [key]: value })

  const country = reference.origins.find((c) => c.country === cargo.origin_country)
  const originPorts = country?.ports ?? []
  const selectedOrigin = originPorts.find((p) => p.port_id === cargo.origin_port_id)
  const { horizon_start, horizon_end } = reference.scenario_bank

  function setCountry(name: string) {
    const next = reference.origins.find((c) => c.country === name)
    onChange({ ...cargo, origin_country: name, origin_port_id: next?.ports[0]?.port_id ?? '' })
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Cargo requirement</h2>
          <p>Describe the parcel you need delivered. The engine works out which vessels and charter strategies can carry it, and what each is likely to cost.</p>
        </div>
        <span className="card-note">All fields required</span>
      </div>

      <div className="field-grid">
        <label className="field">
          <span>Commodity</span>
          <select className="control" value={cargo.commodity} onChange={(e) => set('commodity', e.target.value)}>
            {reference.commodities.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        </label>

        <label className="field">
          <span>Quantity</span>
          <input
            type="number" min={1} step={1000} className="control num"
            value={cargo.quantity_tonnes}
            onChange={(e) => set('quantity_tonnes', Number(e.target.value))}
          />
          <span className="field-help">Tonnes to be delivered.</span>
        </label>

        <label className="field">
          <span>Loading country</span>
          <select className="control" value={cargo.origin_country} onChange={(e) => setCountry(e.target.value)}>
            {reference.origins.map((c) => <option key={c.country} value={c.country}>{c.country}</option>)}
          </select>
          {country?.note && <span className="field-help">{country.note}</span>}
        </label>

        <label className="field">
          <span>Loading port</span>
          <select className="control" value={cargo.origin_port_id} onChange={(e) => set('origin_port_id', e.target.value)}>
            {originPorts.map((p) => <option key={p.port_id} value={p.port_id}>{p.name} ({p.port_id})</option>)}
          </select>
          {selectedOrigin?.commodities && <span className="field-help">{selectedOrigin.commodities}</span>}
        </label>

        <label className="field">
          <span>Discharge port</span>
          <select className="control" value={cargo.destination_port_id} onChange={(e) => set('destination_port_id', e.target.value)}>
            {reference.discharge_ports.map((p) => (
              <option key={p.port_id} value={p.port_id}>{p.name}, {p.state}</option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Earliest departure</span>
          <input
            type="date" className="control num"
            min={horizon_start} max={horizon_end}
            value={cargo.earliest_departure}
            onChange={(e) => set('earliest_departure', e.target.value)}
          />
        </label>

        <label className="field">
          <span>Delivery deadline</span>
          <input
            type="date" className="control num"
            min={cargo.earliest_departure || horizon_start} max={horizon_end}
            value={cargo.delivery_deadline}
            onChange={(e) => set('delivery_deadline', e.target.value)}
          />
          <span className="field-help">
            The freight forecast currently runs to {formatDate(horizon_end)}. Dates beyond it have nothing to price against.
          </span>
        </label>

        <label className="field">
          <span>Risk preference</span>
          <select
            className="control" value={cargo.risk_preference}
            onChange={(e) => set('risk_preference', e.target.value as CargoRequirement['risk_preference'])}
          >
            <option value="LOW">Protect against bad outcomes</option>
            <option value="BALANCED">Balanced</option>
            <option value="HIGH">Chase the lowest expected cost</option>
          </select>
          <span className="field-help">Sets how heavily tail risk is weighted against expected cost.</span>
        </label>
      </div>

      <div className="form-foot">
        <p>
          Priced against {reference.scenario_bank.scenario_count} market scenarios, across a fleet of {reference.fleet_size} vessels.
        </p>
        <button className="btn btn--primary" onClick={onRun} disabled={running}>
          {running ? 'Analysing…' : 'Analyse procurement options'}
        </button>
      </div>
    </section>
  )
}

function formatDate(iso: string): string {
  if (!iso) return 'the end of the forecast horizon'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
}
