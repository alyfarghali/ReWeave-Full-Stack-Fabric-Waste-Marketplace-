import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { deleteLot, delistLot, getAdminMetrics, relistLot } from './api.js'
import { formatMoney, formatUnitPrice, formatWeightKg } from '../../shared/formatters.js'

const STATUS_COLORS = {
  Available: '#166534',
  Claimed: '#111111',
  Unlisted: '#b91c1c',
}

const FABRIC_COLORS = ['#166534', '#2563eb', '#7c3aed', '#d97706', '#0f766e', '#b91c1c']

export default function DashboardPage() {
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState(null)
  const [acting, setActing] = useState({})

  function refresh() {
    getAdminMetrics()
      .then((data) => {
        setMetrics(data)
        setError(null)
      })
      .catch((err) => setError(err.message))
  }

  useEffect(refresh, [])

  async function runLotAction(lot, action) {
    const key = `${action}-${lot.id}`
    if (action === 'delete' && !window.confirm(`Delete ${lot.name}? This removes it from inventory and analytics.`)) return
    setActing((prev) => ({ ...prev, [key]: true }))
    try {
      if (action === 'delist') await delistLot(lot.id)
      if (action === 'relist') await relistLot(lot.id)
      if (action === 'delete') await deleteLot(lot.id)
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setActing((prev) => ({ ...prev, [key]: false }))
    }
  }

  if (error && !metrics) return <div className="error">{error}</div>
  if (!metrics) return <div className="dash-loading"><div className="dash-spinner" />Loading admin dashboard...</div>

  const latestRun = metrics.recent_runs?.[0]
  const runHistory = metrics.run_history || []
  const fabricRows = metrics.fabric_stats || []
  const statusMix = (metrics.status_mix || []).filter((item) => item.value > 0)
  const hasData = metrics.has_data
  const topActionLots = [...(metrics.quick_action_lots || [])]
    .sort((a, b) => (b.current_price_usd || 0) - (a.current_price_usd || 0))
    .slice(0, 5)
  const hiddenActionCount = Math.max(0, (metrics.quick_action_lots || []).length - topActionLots.length)

  return (
    <div className="admin-command">
      {error && <div className="error">{error}</div>}

      <section className="admin-hero">
        <div className="admin-hero-copy">
          <span className="admin-eyebrow">Reweave admin command center</span>
          <h1>Turn factory scans into inventory, impact, and action.</h1>
          <p>
            Every factory scan publishes lots automatically. Track revenue, inventory
            value, and environmental impact the moment scraps hit the table.
          </p>
          <Link className="admin-net-cta" to="/admin/network">
            See the network at full scale
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14" />
              <path d="m13 6 6 6-6 6" />
            </svg>
          </Link>
        </div>
        <div className="admin-hero-panel">
          <div className="admin-live-row">
            Live database
          </div>
          <div className="admin-hero-number">{metrics.total_lots}</div>
          <div className="admin-hero-label">lots in the system</div>
          <div className="admin-mini-grid">
            <span>{metrics.total_pieces} pieces</span>
            <span>{formatWeightKg(metrics.total_weight_kg)}</span>
            <span>{formatMoney(metrics.inventory_value)} live value</span>
          </div>
        </div>
      </section>

      {!hasData && <EmptyDemoState />}

      <section className="admin-kpi-grid" aria-label="Operational summary">
        <Kpi label="Live Inventory Value" value={formatMoney(metrics.inventory_value)} note={`${metrics.available_lots} available lots`} />
        <Kpi label="Material Diverted" value={formatWeightKg(metrics.total_weight_kg)} note={`${metrics.total_pieces} detected pieces`} />
        <Kpi label="CO2 Prevented" value={formatWeightKg(metrics.total_carbon_saved_kg)} note={`${metrics.carbon_equiv_car_miles} driving miles avoided`} />
        <Kpi label="Revenue Claimed" value={formatMoney(metrics.revenue)} note={`${metrics.claim_rate_pct}% sell-through`} />
      </section>

      <section className="admin-section admin-runs-section">
        <SectionTitle eyebrow="Latest scan" title="Run Summary" action={<Link to="/admin/lots">Open inventory</Link>} />
        <div className="admin-run-layout">
          <RunPreview run={latestRun} />
          <div className="admin-run-list">
            {(metrics.recent_runs || []).slice(0, 5).map((run) => (
              <article className="admin-run-card" key={run.id || run.created_at}>
                <div>
                  <div className="admin-run-card-title">{run.label}</div>
                  <div className="admin-run-card-meta">
                    {run.group_count} lots · {run.piece_count} pieces · {formatWeightKg(run.total_weight_kg)}
                  </div>
                </div>
                <div className="admin-run-card-value">{formatMoney(run.inventory_value)}</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="admin-section">
        <SectionTitle eyebrow="Admin controls" title="Highest-Value Inventory Actions" action={<Link to="/factory">Run new scan</Link>} />
        <div className="admin-action-grid">
          <div className="admin-action-panel">
            <div className="admin-action-summary">
              <strong>{topActionLots.length} priority lots</strong>
              <span>Sorted by current value so the highest-impact decisions come first.</span>
            </div>
            {(metrics.recommended_actions || []).map((item) => (
              <div className={`admin-action-note admin-action-note--${item.tone}`} key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.detail}</span>
              </div>
            ))}
          </div>
          <div className="admin-lot-actions">
            {topActionLots.map((lot) => (
              <LotActionRow
                key={lot.id}
                lot={lot}
                acting={acting}
                onAction={runLotAction}
              />
            ))}
            {topActionLots.length === 0 && (
              <div className="admin-empty-panel">Scan a table to create actionable lots here.</div>
            )}
            {hiddenActionCount > 0 && (
              <Link className="admin-more-actions" to="/admin/lots">
                Review {hiddenActionCount} more lots in full inventory
              </Link>
            )}
          </div>
        </div>
      </section>

      <section className="admin-impact-band">
        <div>
          <span className="admin-eyebrow">Impact preview</span>
          <h2>Environmental gains from the current inventory</h2>
          <p>Scaled for scrap-level operations, so small batches and larger runs stay easy to compare.</p>
          <Link className="admin-impact-link" to="/admin/impact">Open impact report</Link>
        </div>
        <div className="admin-impact-metrics">
          <ImpactMetric label="Water saved" value={formatWater(metrics.total_water_saved_l)} detail={`${metrics.water_equiv_showers} showers`} />
          <ImpactMetric label="Energy avoided" value={`${formatCompact(metrics.energy_saved_kwh)} kWh`} detail={`${metrics.water_equiv_bottles.toLocaleString()} bottles of water`} />
          <ImpactMetric label="Diversion target" value={`${metrics.diversion_pct}%`} detail={`${formatWeightKg(metrics.diversion_target_kg)} pilot goal`} />
        </div>
      </section>

      <section className="admin-section admin-analytics">
        <SectionTitle eyebrow="Operational analytics" title="Inventory Movement Signals" />
        <div className="admin-chart-grid">
          <ChartCard title="Fabric mix by weight">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={fabricRows} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#eeeeee" vertical={false} />
                <XAxis dataKey="fabric_type" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `${v * 1000}g`} />
                <Tooltip formatter={(value) => formatWeightKg(Number(value))} labelStyle={{ color: '#111' }} />
                <Bar dataKey="weight_kg" radius={[4, 4, 0, 0]}>
                  {fabricRows.map((_, i) => <Cell key={i} fill={FABRIC_COLORS[i % FABRIC_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Run ramp">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={runHistory} margin={{ top: 10, right: 6, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="runWeight" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#166534" stopOpacity={0.28} />
                    <stop offset="95%" stopColor="#166534" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#eeeeee" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `${v}g`} />
                <Tooltip formatter={(value, name) => [name === 'weight_g' ? `${value} g` : value, name === 'weight_g' ? 'Weight' : name]} />
                <Area type="monotone" dataKey="weight_g" stroke="#166534" fill="url(#runWeight)" strokeWidth={2} dot={{ r: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Inventory status">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={statusMix} dataKey="value" nameKey="name" innerRadius={58} outerRadius={82} paddingAngle={3}>
                  {statusMix.map((entry) => <Cell key={entry.name} fill={STATUS_COLORS[entry.name]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="admin-status-legend">
              {statusMix.map((entry) => (
                <span key={entry.name}><i style={{ background: STATUS_COLORS[entry.name] }} />{entry.name}: {entry.value}</span>
              ))}
            </div>
          </ChartCard>
        </div>
      </section>
    </div>
  )
}

function Kpi({ label, value, note }) {
  return (
    <article className="admin-kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function SectionTitle({ eyebrow, title, action }) {
  return (
    <div className="admin-section-title">
      <div>
        <span className="admin-eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {action && <div className="admin-section-action">{action}</div>}
    </div>
  )
}

function RunPreview({ run }) {
  const lots = run?.lots || []
  const groups = run?.summary_groups || []
  return (
    <article className="admin-run-preview">
      <div className="admin-run-image">
        {run?.annotated_image_data_url ? (
          <img src={run.annotated_image_data_url} alt="Latest segmented scan" />
        ) : (
          <div className="admin-run-placeholder">
            <IconScan />
            <span>Segmented scan image appears after the next factory photo.</span>
          </div>
        )}
      </div>
      <div className="admin-run-detail">
        <div className="admin-run-detail-head">
          <div>
            <span className="admin-eyebrow">{run?.label || 'No scan yet'}</span>
            <h3>{run ? `${run.group_count} sorted lots created` : 'Waiting for first run'}</h3>
          </div>
          <span className="admin-confidence">{run?.scale_confidence || 'ready'}</span>
        </div>
        <div className="admin-run-stats">
          <span><strong>{run?.piece_count || 0}</strong> pieces</span>
          <span><strong>{formatWeightKg(run?.total_weight_kg || 0)}</strong> weight</span>
          <span><strong>{formatMoney(run?.inventory_value || 0)}</strong> value</span>
          <span><strong>{formatWater(run?.water_saved_l || 0)}</strong> water</span>
        </div>
        <div className="admin-run-lots">
          {lots.length > 0 ? lots.map((lot) => <LotPill lot={lot} key={lot.id} />) : groups.slice(0, 8).map((group) => (
            <span className="admin-lot-pill" key={group.key}>
              <i style={{ background: group.color_hex }} />
              {group.fabric_type} · {Math.round(group.weight_g || 0)}g
            </span>
          ))}
          {!lots.length && !groups.length && <span className="admin-muted">No run data yet.</span>}
        </div>
      </div>
    </article>
  )
}

function LotPill({ lot }) {
  return (
    <span className="admin-lot-pill">
      <i style={{ background: lot.color_hex }} />
      {lot.fabric_type} · {formatWeightKg(lot.weight_kg)}
    </span>
  )
}

function LotActionRow({ lot, acting, onAction }) {
  const publishKey = `${lot.status === 'unlisted' ? 'relist' : 'delist'}-${lot.id}`
  const deleteKey = `delete-${lot.id}`
  return (
    <article className="admin-lot-action-row">
      <div className="admin-lot-thumb" style={{ background: lot.color_hex }}>
        {lot.thumbnail && <img src={lot.thumbnail} alt="" />}
      </div>
      <div className="admin-lot-action-main">
        <strong>{lot.name}</strong>
        <span>{lot.fabric_type} · {formatWeightKg(lot.weight_kg)} · {formatUnitPrice(lot.weight_kg > 0 ? lot.current_price_usd / lot.weight_kg : 0)}</span>
      </div>
      <span className={`admin-status admin-status--${lot.status}`}>{lot.status}</span>
      <div className="admin-row-buttons">
        {lot.status === 'unlisted' ? (
          <button type="button" onClick={() => onAction(lot, 'relist')} disabled={acting[publishKey]}>
            Publish
          </button>
        ) : lot.status === 'available' ? (
          <button type="button" className="btn-ghost" onClick={() => onAction(lot, 'delist')} disabled={acting[publishKey]}>
            Delist
          </button>
        ) : null}
        <button type="button" className="btn-ghost admin-danger-btn" onClick={() => onAction(lot, 'delete')} disabled={acting[deleteKey]}>
          Delete
        </button>
      </div>
    </article>
  )
}

function ImpactMetric({ label, value, detail }) {
  return (
    <div className="admin-impact-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <article className="admin-chart-card">
      <h3>{title}</h3>
      {children}
    </article>
  )
}

function EmptyDemoState() {
  return (
    <section className="admin-empty-state">
      <div>
        <strong>Ready for a clean demo restart.</strong>
        <span>After the first table photo, this page will fill with scan evidence, lot controls, impact metrics, and charts.</span>
      </div>
      <Link to="/factory">Start scan</Link>
    </section>
  )
}

function IconScan() {
  return (
    <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7V5.5A1.5 1.5 0 0 1 5.5 4H7" />
      <path d="M17 4h1.5A1.5 1.5 0 0 1 20 5.5V7" />
      <path d="M20 17v1.5a1.5 1.5 0 0 1-1.5 1.5H17" />
      <path d="M7 20H5.5A1.5 1.5 0 0 1 4 18.5V17" />
      <path d="M7 12h10" />
      <path d="M8 9h3" />
      <path d="M13 15h3" />
    </svg>
  )
}

function formatWater(value) {
  const liters = Number(value) || 0
  if (liters <= 0) return '0 L'
  if (liters < 10) return `${liters.toFixed(1)} L`
  if (liters < 1000) return `${Math.round(liters).toLocaleString()} L`
  return `${(liters / 1000).toFixed(liters >= 10000 ? 0 : 1)} kL`
}

function formatCompact(value) {
  const number = Number(value) || 0
  if (number < 10) return number.toFixed(2).replace(/\.?0+$/, '')
  return Math.round(number).toLocaleString()
}
