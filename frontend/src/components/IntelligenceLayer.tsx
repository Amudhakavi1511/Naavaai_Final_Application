import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const forecast = [
  { month: 'Sep 26', p10: 27, p50: 34, p90: 44 }, { month: 'Oct 26', p10: 28, p50: 35, p90: 47 },
  { month: 'Nov 26', p10: 29, p50: 37, p90: 51 }, { month: 'Dec 26', p10: 30, p50: 39, p90: 54 },
  { month: 'Jan 27', p10: 31, p50: 41, p90: 57 }, { month: 'Feb 27', p10: 30, p50: 40, p90: 55 },
]
const sources = [
  ['Baltic / freight', 'Freight indices & route signals', 'Available'],
  ['Port operations', 'Turnaround & congestion observations', 'Available'],
  ['Vessel master', 'Capacity, dimensions & availability', 'Available'],
  ['Commodity market', 'Commodity & bunker indicators', 'Available'],
]

export default function IntelligenceLayer() {
  return <div className="page-stack">
    <div className="page-heading"><div><div className="eyebrow">MARKET INTELLIGENCE</div><h1>Market intelligence</h1><p>Understand freight conditions, uncertainty and the signals influencing procurement decisions.</p></div><span className="live-badge"><span className="status-dot" /> Updated</span></div>

    <div className="dashboard-grid intelligence-grid">
      <section className="panel chart-panel">
        <div className="panel-head"><div><div className="panel-kicker">FREIGHT OUTLOOK</div><h2>Australia → East Coast India</h2></div><span className="tag">USD / TONNE</span></div>
        <div className="chart-legend"><span><i className="legend p50" /> P50 forecast</span><span><i className="legend band" /> P10–P90 range</span></div>
        <ResponsiveContainer width="100%" height={280}><AreaChart data={forecast} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}><CartesianGrid strokeDasharray="2 4" stroke="#2A3B52" vertical={false} /><XAxis dataKey="month" tick={{ fill: '#9FB0C4', fontSize: 11 }} axisLine={{ stroke: '#2A3B52' }} tickLine={false} /><YAxis tick={{ fill: '#9FB0C4', fontSize: 11 }} axisLine={{ stroke: '#2A3B52' }} tickLine={false} unit=" $" /><Tooltip contentStyle={{ background: '#16273D', border: '1px solid #2A3B52', color: '#EDE8DD' }} formatter={(v) => [`$${v}/t`, '']} /><Area type="monotone" dataKey="p90" stroke="#6D829B" fill="#3E536B" fillOpacity={0.3} strokeWidth={1} /><Area type="monotone" dataKey="p10" stroke="#6D829B" fill="#16273D" fillOpacity={1} strokeWidth={1} /><Area type="monotone" dataKey="p50" stroke="#C98A3B" fill="none" strokeWidth={3} /></AreaChart></ResponsiveContainer>
        <div className="chart-foot"><span>Forecast range widens as the horizon extends</span><span className="font-data">P10 · P50 · P90</span></div>
      </section>

      <section className="panel scenario-panel">
        <div className="panel-head"><div><div className="panel-kicker">SCENARIO OUTLOOK</div><h2>Market scenarios</h2></div><span className="tag green">READY</span></div>
        <div className="metric-big"><strong>≈40</strong><span>representative market scenarios</span></div>
        <div className="mini-stats"><div><strong>200–500</strong><span>simulated paths</span></div><div><strong>3</strong><span>forecast quantiles</span></div><div><strong>4</strong><span>linked market signals</span></div></div>
        <div className="scenario-bars"><ScenarioBar label="Freight" value={82} /><ScenarioBar label="Bunker" value={64} /><ScenarioBar label="Commodity" value={57} /><ScenarioBar label="Congestion" value={41} /></div>
        <div className="info-callout">Scenario paths preserve relationships between freight, bunker, commodity and port conditions so downstream decisions can be tested against more than one future.</div>
      </section>
    </div>

    <div className="dashboard-grid three-col">
      <section className="panel"><div className="panel-kicker">DATA SOURCES</div><h2>Source health</h2><div className="source-list">{sources.map(([name, detail, state]) => <div className="source-row" key={name}><span className="source-icon">◌</span><div><strong>{name}</strong><span>{detail}</span></div><em>{state}</em></div>)}</div></section>
      <section className="panel"><div className="panel-kicker">MARKET SIGNALS</div><h2>Driver signals</h2><div className="driver"><span>Freight trend</span><strong>↑ Moderate</strong><small>seasonality + route movement</small></div><div className="driver"><span>Bunker pressure</span><strong>→ Stable</strong><small>scenario-dependent</small></div><div className="driver"><span>Port congestion</span><strong>↑ Elevated</strong><small>turnaround uncertainty retained</small></div></section>
      <section className="panel"><div className="panel-kicker">QUALITY & GOVERNANCE</div><h2>Model controls</h2><div className="control-list"><div><span>Forecast refresh</span><strong>Daily</strong></div><div><span>Scenario generation</span><strong>Per analysis</strong></div><div><span>Feature drift</span><strong className="ok">Monitored</strong></div><div><span>Forecast drift</span><strong className="ok">Monitored</strong></div></div><div className="info-callout">Forecasts and scenarios can be versioned and traced to their source inputs before they influence a procurement decision.</div></section>
    </div>
  </div>
}
function ScenarioBar({ label, value }: { label: string; value: number }) { return <div className="scenario-bar"><span>{label}</span><div><i style={{ width: `${value}%` }} /></div><strong>{value}%</strong></div> }
