import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Link } from 'react-router-dom'
import { getAdminMetrics } from './api.js'
import { formatWeightKg } from '../../shared/formatters.js'

const IMPACT_COLORS = ['#166534', '#2563eb', '#0f766e', '#7c3aed', '#d97706', '#b91c1c']

export default function ImpactPage() {
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getAdminMetrics()
      .then((data) => {
        setMetrics(data)
        setError(null)
      })
      .catch((err) => setError(err.message))
  }, [])

  const fabricImpact = useMemo(() => metrics?.fabric_impact || [], [metrics])
  if (error) return <div className="error">{error}</div>
  if (!metrics) return <div className="dash-loading"><div className="dash-spinner" />Loading impact report...</div>

  return (
    <div className="admin-impact-page">
      <section className="admin-impact-hero">
        <div>
          <span className="admin-eyebrow">Impact report</span>
          <h1>Positive outcomes from every scanned scrap.</h1>
          <p>
            These numbers come from the same lots powering the admin dashboard, so water,
            carbon, energy, and diversion totals stay aligned with inventory.
          </p>
        </div>
      </section>

      {!metrics.has_data && (
        <section className="admin-empty-state">
          <div>
            <strong>No scan data yet.</strong>
            <span>Run one table scan and this report will populate from the created lots.</span>
          </div>
          <Link to="/factory">Start scan</Link>
        </section>
      )}

      <section className="admin-impact-total-grid">
        <ImpactCard label="CO2 prevented" value={formatWeightKg(metrics.total_carbon_saved_kg)} detail={`${metrics.carbon_equiv_car_miles} driving miles avoided`} tone="green" />
        <ImpactCard label="Water conserved" value={formatWater(metrics.total_water_saved_l)} detail={`${metrics.water_equiv_showers} showers saved`} tone="blue" />
        <ImpactCard label="Fabric diverted" value={formatWeightKg(metrics.total_weight_kg)} detail={`${metrics.total_pieces} pieces kept in circulation`} tone="violet" />
        <ImpactCard label="Energy avoided" value={`${formatCompact(metrics.energy_saved_kwh)} kWh`} detail={`${metrics.carbon_equiv_phones.toLocaleString()} phone charges equivalent`} tone="orange" />
      </section>

      <section className="admin-impact-story">
        <div className="admin-impact-progress">
          <div className="admin-impact-progress-head">
            <div>
              <span className="admin-eyebrow">Pilot diversion</span>
              <h2>{metrics.diversion_pct}% of target reached</h2>
            </div>
            <strong>{formatWeightKg(metrics.total_weight_kg)} / {formatWeightKg(metrics.diversion_target_kg)}</strong>
          </div>
          <div className="admin-impact-progress-track">
            <span style={{ width: `${Math.min(100, metrics.diversion_pct)}%` }} />
          </div>
        </div>

        <div className="admin-impact-equivalents">
          <Equivalent value={metrics.water_equiv_bottles.toLocaleString()} label="500 mL bottles of water conserved" />
          <Equivalent value={metrics.carbon_equiv_phones.toLocaleString()} label="phone charges worth of CO2 avoided" />
          <Equivalent value={`${metrics.available_lots}`} label="lots still available for circular reuse" />
        </div>
      </section>

      <section className="admin-section">
        <div className="admin-section-title">
          <div>
            <span className="admin-eyebrow">Material-level impact</span>
            <h2>Impact by Fabric Type</h2>
          </div>
          <Link className="admin-impact-link admin-impact-link--light" to="/admin/lots">Manage inventory</Link>
        </div>
        <div className="admin-impact-chart-layout">
          <div className="admin-impact-chart-card">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={fabricImpact} margin={{ top: 10, right: 12, left: -12, bottom: 0 }}>
                <CartesianGrid stroke="#eeeeee" vertical={false} />
                <XAxis dataKey="fabric" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `${v * 1000}g`} />
                <Tooltip formatter={(value, name) => [name === 'weight_kg' ? formatWeightKg(value) : formatWeightKg(value), name === 'weight_kg' ? 'Weight' : 'CO2']} />
                <Bar dataKey="weight_kg" radius={[4, 4, 0, 0]}>
                  {fabricImpact.map((_, i) => <Cell key={i} fill={IMPACT_COLORS[i % IMPACT_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="admin-impact-fabric-list">
            {fabricImpact.map((row, i) => (
              <article key={row.fabric}>
                <i style={{ background: IMPACT_COLORS[i % IMPACT_COLORS.length] }} />
                <div>
                  <strong>{row.fabric}</strong>
                  <span>{formatWeightKg(row.weight_kg)} diverted · {formatWeightKg(row.carbon_kg)} CO2 · {formatWater(row.water_l)} water</span>
                </div>
              </article>
            ))}
            {fabricImpact.length === 0 && <div className="admin-empty-panel">Fabric impact appears after the first scan.</div>}
          </div>
        </div>
      </section>
    </div>
  )
}

function ImpactCard({ label, value, detail, tone }) {
  return (
    <article className={`admin-impact-card admin-impact-card--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

function Equivalent({ value, label }) {
  return (
    <article>
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
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
