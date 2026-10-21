import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

/*
 * Full-network outlook. Every figure on this page is derived from a single,
 * transparent set of assumptions (see SCALE below) so the math can be checked
 * by hand: 50 facilities x 5,000 kg/facility/month x 12 months.
 * Nothing here reads from or writes to the database.
 */

const SCALE = {
  facilities: 50,
  kgPerFacilityPerMonth: 5000,
  months: 12,
}

// Coefficients shared with the live impact engine (backend/app/impact/calculator.py),
// except CO2 which uses a full-lifecycle factor (avoided virgin production)
// rather than landfill-only diversion.
const CO2_KG_PER_KG = 5.0          // kg CO2-equivalent prevented per kg diverted (lifecycle)
const WATER_L_PER_KG = 2700.0      // liters saved per kg diverted (cotton-heavy)
const PRICE_PER_KG = 3.0           // average recovered value per kg ($/kg)

// Everyday equivalences
const CO2_KG_PER_CAR_YEAR = 4600.0 // avg passenger car emits ~4.6 t CO2 / year (EPA)
const CO2_KG_PER_CAR_MILE = 0.39
const WATER_L_PER_HOUSEHOLD_YEAR = 300000.0
const WATER_L_PER_POOL = 2500000.0 // Olympic-size pool

const TOTAL_KG = SCALE.facilities * SCALE.kgPerFacilityPerMonth * SCALE.months // 3,000,000
const MONTHLY_KG = SCALE.facilities * SCALE.kgPerFacilityPerMonth               // 250,000
const TOTAL_TONNES = TOTAL_KG / 1000
const CO2_TONNES = (TOTAL_KG * CO2_KG_PER_KG) / 1000
const WATER_L = TOTAL_KG * WATER_L_PER_KG
const VALUE_USD = TOTAL_KG * PRICE_PER_KG

// A single representative scan — the humble baseline the network grows from.
const TODAY = {
  scans: 1,
  facilities: 1,
  kg: 3.2,
}
const TODAY_CO2 = TODAY.kg * CO2_KG_PER_KG
const TODAY_VALUE = TODAY.kg * PRICE_PER_KG

const FABRIC_MIX = [
  { name: 'Cotton jersey', tonnes: 1260, color: '#166534' },
  { name: 'Cotton / poly blend', tonnes: 720, color: '#2563eb' },
  { name: 'French terry', tonnes: 450, color: '#7c3aed' },
  { name: 'Rib knit', tonnes: 330, color: '#d97706' },
  { name: 'Fleece', tonnes: 240, color: '#0f766e' },
]

const REGIONS = [
  { region: 'Southeast US', hub: 'Atlanta hub', facilities: 12, fabric: 'Cotton jersey' },
  { region: 'Midwest US', hub: 'Columbus', facilities: 10, fabric: 'Cotton / poly blend' },
  { region: 'Northeast US', hub: 'Boston', facilities: 8, fabric: 'French terry' },
  { region: 'Central America', hub: 'San Pedro Sula', facilities: 8, fabric: 'Rib knit' },
  { region: 'West Coast US', hub: 'Los Angeles', facilities: 7, fabric: 'Fleece' },
  { region: 'South Asia', hub: 'Dhaka', facilities: 5, fabric: 'Cotton jersey' },
]

// 12-month linear ramp at steady state (50 facilities live every month).
const RAMP = Array.from({ length: SCALE.months }, (_, i) => {
  const month = i + 1
  return {
    label: `M${month}`,
    tonnes: (MONTHLY_KG * month) / 1000,
    valueM: (MONTHLY_KG * month * PRICE_PER_KG) / 1e6,
  }
})

export default function NetworkPage() {
  const [scaled, setScaled] = useState(true)

  const facilities = scaled ? SCALE.facilities : TODAY.facilities
  const divertedKg = scaled ? TOTAL_KG : TODAY.kg
  const co2Kg = scaled ? CO2_TONNES * 1000 : TODAY_CO2
  const valueUsd = scaled ? VALUE_USD : TODAY_VALUE

  return (
    <div className="admin-command admin-net">
      <section className="admin-hero">
        <div className="admin-hero-copy">
          <span className="admin-eyebrow">Network analytics</span>
          <h1>Reweave across a full apparel supply chain.</h1>
          <p>
            A single scan diverts a few kilograms today. Hold that next to
            what the same pipeline recovers once every facility in the network is online,
            built from one transparent set of assumptions, not a guess.
          </p>
          <div className="admin-net-toggle" role="group" aria-label="Scenario">
            <button
              type="button"
              className={!scaled ? 'is-active' : ''}
              onClick={() => setScaled(false)}
              aria-pressed={!scaled}
            >
              Today&apos;s scan
            </button>
            <button
              type="button"
              className={scaled ? 'is-active' : ''}
              onClick={() => setScaled(true)}
              aria-pressed={scaled}
            >
              Full network
            </button>
          </div>
        </div>

        <div className="admin-hero-panel admin-net-panel">
          <div className="admin-live-row">{scaled ? 'Full network · annual' : 'Today · single scan'}</div>
          <div>
            <div className="admin-hero-number">
              <CountUp value={divertedKg} format={fmtMassShort} />
            </div>
            <div className="admin-hero-label">fabric diverted from landfill</div>
          </div>
          <div className="admin-net-assumptions">
            {scaled ? (
              <>
                <span><strong>{SCALE.facilities}</strong> facilities</span>
                <span><strong>{SCALE.kgPerFacilityPerMonth.toLocaleString()} kg</strong> / facility / month</span>
                <span><strong>{SCALE.months}</strong> months</span>
              </>
            ) : (
              <>
                <span><strong>{TODAY.facilities}</strong> facility</span>
                <span><strong>{TODAY.scans}</strong> scan</span>
                <span><strong>real data</strong> from the floor</span>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="admin-kpi-grid" aria-label="Network headline metrics">
        <Kpi label="Fabric diverted" value={<CountUp value={divertedKg} format={fmtMass} />} note="kept out of landfill" />
        <Kpi label="CO2 prevented" value={<CountUp value={co2Kg} format={fmtMass} />} note={`lifecycle, ${CO2_KG_PER_KG} kg CO2 per kg`} />
        <Kpi label="Net value recovered" value={<CountUp value={valueUsd} format={fmtMoney} />} note={`$${PRICE_PER_KG.toFixed(0)} / kg average lot price`} />
        <Kpi label="Facilities online" value={<CountUp value={facilities} format={fmtInt} />} note={scaled ? 'across the network' : 'pilot floor'} />
      </section>

      <section className="admin-section admin-net-formula">
        <SectionTitle eyebrow="The math, in the open" title="Where every number comes from" />
        <div className="admin-net-formula-grid">
          <div className="admin-net-equation">
            <span className="admin-net-eq-term"><strong>{SCALE.facilities}</strong>facilities</span>
            <span className="admin-net-eq-op">×</span>
            <span className="admin-net-eq-term"><strong>{SCALE.kgPerFacilityPerMonth.toLocaleString()}</strong>kg / month</span>
            <span className="admin-net-eq-op">×</span>
            <span className="admin-net-eq-term"><strong>{SCALE.months}</strong>months</span>
            <span className="admin-net-eq-op">=</span>
            <span className="admin-net-eq-result"><strong>{TOTAL_TONNES.toLocaleString()}</strong>tonnes diverted</span>
          </div>
          <div className="admin-net-derivations">
            <Derivation
              label="CO2 prevented"
              expr={`${TOTAL_TONNES.toLocaleString()} t × ${CO2_KG_PER_KG} kg/kg`}
              result={`${CO2_TONNES.toLocaleString()} t`}
            />
            <Derivation
              label="Net value recovered"
              expr={`${(TOTAL_KG).toLocaleString()} kg × $${PRICE_PER_KG.toFixed(0)}/kg`}
              result={fmtMoney(VALUE_USD)}
            />
            <Derivation
              label="Water saved"
              expr={`${(TOTAL_KG).toLocaleString()} kg × ${WATER_L_PER_KG.toLocaleString()} L/kg`}
              result={`${(WATER_L / 1e9).toFixed(1)}B L`}
            />
          </div>
        </div>
      </section>

      <section className="admin-section admin-net-charts">
        <SectionTitle eyebrow="Twelve-month outlook" title="How the network compounds" />
        <div className="admin-chart-grid">
          <ChartCard title="Material diverted (cumulative)">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={RAMP} margin={{ top: 10, right: 6, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="netDiverted" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#166534" stopOpacity={0.28} />
                    <stop offset="95%" stopColor="#166534" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#eeeeee" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k t`} />
                <Tooltip formatter={(v) => [`${Number(v).toLocaleString()} t`, 'Diverted']} labelStyle={{ color: '#111' }} />
                <Area type="monotone" dataKey="tonnes" stroke="#166534" fill="url(#netDiverted)" strokeWidth={2} dot={{ r: 2.5 }} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Value recovered (cumulative)">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={RAMP} margin={{ top: 10, right: 6, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="netValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.26} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#eeeeee" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={11} />
                <YAxis tickLine={false} axisLine={false} fontSize={11} tickFormatter={(v) => `$${v.toFixed(0)}M`} />
                <Tooltip formatter={(v) => [`$${Number(v).toFixed(2)}M`, 'Value']} labelStyle={{ color: '#111' }} />
                <Area type="monotone" dataKey="valueM" stroke="#2563eb" fill="url(#netValue)" strokeWidth={2} dot={{ r: 2.5 }} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Fabric mix at scale">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={FABRIC_MIX} dataKey="tonnes" nameKey="name" innerRadius={56} outerRadius={82} paddingAngle={3}>
                  {FABRIC_MIX.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                </Pie>
                <Tooltip formatter={(v, n) => [`${Number(v).toLocaleString()} t`, n]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="admin-status-legend admin-net-legend">
              {FABRIC_MIX.map((entry) => (
                <span key={entry.name}><i style={{ background: entry.color }} />{entry.name}</span>
              ))}
            </div>
          </ChartCard>
        </div>
      </section>

      <section className="admin-impact-band admin-net-equiv">
        <div>
          <span className="admin-eyebrow">What it adds up to</span>
          <h2>{CO2_TONNES.toLocaleString()} tonnes of CO2, made tangible.</h2>
          <p>
            The annual footprint Reweave erases across the network, translated into
            things you can picture.
          </p>
        </div>
        <div className="admin-impact-metrics">
          <ImpactMetric
            label="Cars off the road"
            value={fmtInt(Math.round((CO2_TONNES * 1000) / CO2_KG_PER_CAR_YEAR))}
            detail={`${fmtMillions((CO2_TONNES * 1000) / CO2_KG_PER_CAR_MILE)} miles not driven`}
          />
          <ImpactMetric
            label="Households of water"
            value={fmtInt(Math.round(WATER_L / WATER_L_PER_HOUSEHOLD_YEAR))}
            detail={`${(WATER_L / 1e9).toFixed(1)} billion liters saved`}
          />
          <ImpactMetric
            label="Olympic pools"
            value={fmtInt(Math.round(WATER_L / WATER_L_PER_POOL))}
            detail="of water never withdrawn"
          />
        </div>
      </section>

      <section className="admin-section">
        <SectionTitle
          eyebrow="Network footprint"
          title="Where the material flows"
          action={<Link to="/admin">Back to operations</Link>}
        />
        <div className="admin-net-table-wrap">
          <table className="admin-table admin-net-table">
            <thead>
              <tr>
                <th>Region</th>
                <th className="admin-net-num">Facilities</th>
                <th className="admin-net-num">Diverted / month</th>
                <th className="admin-net-num">Annual value</th>
                <th>Lead fabric</th>
              </tr>
            </thead>
            <tbody>
              {REGIONS.map((r) => {
                const monthlyTonnes = (r.facilities * SCALE.kgPerFacilityPerMonth) / 1000
                const annualValue = r.facilities * SCALE.kgPerFacilityPerMonth * SCALE.months * PRICE_PER_KG
                return (
                  <tr key={r.region}>
                    <td>
                      <div className="admin-net-region">
                        <strong>{r.region}</strong>
                        <span>{r.hub}</span>
                      </div>
                    </td>
                    <td className="admin-net-num">{r.facilities}</td>
                    <td className="admin-net-num">{monthlyTonnes.toLocaleString()} t</td>
                    <td className="admin-net-num">{fmtMoney(annualValue)}</td>
                    <td>{r.fabric}</td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr>
                <td>Network total</td>
                <td className="admin-net-num">{SCALE.facilities}</td>
                <td className="admin-net-num">{(MONTHLY_KG / 1000).toLocaleString()} t</td>
                <td className="admin-net-num">{fmtMoney(VALUE_USD)}</td>
                <td>6 regions</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  )
}

function Derivation({ label, expr, result }) {
  return (
    <div className="admin-net-derivation">
      <span className="admin-net-deriv-label">{label}</span>
      <span className="admin-net-deriv-expr">{expr}</span>
      <strong className="admin-net-deriv-result">{result}</strong>
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

// Animates from the previously rendered value to the new target. Re-runs
// whenever `value` changes (e.g. when the Today / Full network toggle flips).
function CountUp({ value, format, duration = 900 }) {
  // Start at zero so the figures sweep up on mount as well as on toggle.
  const [display, setDisplay] = useState(0)
  const fromRef = useRef(0)
  const rafRef = useRef(0)

  useEffect(() => {
    const from = fromRef.current
    const to = value
    if (from === to) {
      setDisplay(to)
      return undefined
    }
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      setDisplay(from + (to - from) * eased)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
        setDisplay(to)
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [value, duration])

  return <>{format ? format(display) : Math.round(display).toLocaleString()}</>
}

// ── formatters ──────────────────────────────────────────────────────────
function fmtMass(kg) {
  const value = Number(kg) || 0
  if (value >= 1000) return `${Math.round(value / 1000).toLocaleString()} t`
  if (value >= 1) return `${value.toFixed(value >= 10 ? 0 : 1)} kg`
  return `${(value * 1000).toFixed(0)} g`
}

// Compact headline mass used in the dark panel ("3,000 t" / "3.2 kg").
function fmtMassShort(kg) {
  const value = Number(kg) || 0
  if (value >= 1000) return `${Math.round(value / 1000).toLocaleString()} t`
  if (value >= 1) return `${value.toFixed(value >= 10 ? 0 : 1)} kg`
  return `${(value * 1000).toFixed(0)} g`
}

function fmtMoney(usd) {
  const value = Number(usd) || 0
  if (value >= 1e6) return `$${(value / 1e6).toFixed(value % 1e6 === 0 ? 0 : 1)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(0)}K`
  if (value >= 1) return `$${value.toFixed(2)}`
  return `$${value.toFixed(2)}`
}

function fmtInt(value) {
  return Math.round(Number(value) || 0).toLocaleString()
}

function fmtMillions(value) {
  const v = Number(value) || 0
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${Math.round(v / 1e3)}K`
  return Math.round(v).toLocaleString()
}
