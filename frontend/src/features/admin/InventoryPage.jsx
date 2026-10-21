import { useEffect, useMemo, useState } from 'react'
import { deleteLot, delistLot, getLots, relistLot } from './api.js'
import { formatMoney, formatUnitPrice, formatWeightKg } from '../../shared/formatters.js'

export default function InventoryPage() {
  const [lots, setLots] = useState([])
  const [filters, setFilters] = useState({ fabric_type: '', color_name: '', status: '' })
  const [error, setError] = useState(null)
  const [acting, setActing] = useState({})

  function refresh() {
    const params = {}
    if (filters.fabric_type) params.fabric_type = filters.fabric_type
    if (filters.color_name) params.color_name = filters.color_name
    if (filters.status) params.status = filters.status
    getLots(params)
      .then((data) => {
        setLots(data)
        setError(null)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(refresh, [filters])

  const allFabricTypes = useMemo(() => [...new Set(lots.map((l) => l.fabric_type))].sort(), [lots])
  const allColors = useMemo(() => [...new Set(lots.map((l) => l.color_name))].sort(), [lots])
  const summary = useMemo(() => {
    const available = lots.filter((l) => l.status === 'available')
    const unlisted = lots.filter((l) => l.status === 'unlisted')
    const claimed = lots.filter((l) => l.status === 'claimed')
    const liveValue = available.reduce((sum, lot) => sum + (Number(lot.current_price_usd) || 0), 0)
    const hiddenValue = unlisted.reduce((sum, lot) => sum + (Number(lot.current_price_usd) || 0), 0)
    const weight = lots.reduce((sum, lot) => sum + (Number(lot.weight_kg) || 0), 0)
    return { available: available.length, unlisted: unlisted.length, claimed: claimed.length, liveValue, hiddenValue, weight }
  }, [lots])

  async function handleAction(lot, action) {
    const key = `${action}-${lot.id}`
    if (action === 'delete' && !window.confirm(`Delete ${lot.name}? This removes it from inventory and analytics.`)) return
    setActing((a) => ({ ...a, [key]: true }))
    try {
      if (action === 'delist') {
        const updated = await delistLot(lot.id)
        setLots((prev) => prev.map((l) => (l.id === lot.id ? updated : l)))
      }
      if (action === 'relist') {
        const updated = await relistLot(lot.id)
        setLots((prev) => prev.map((l) => (l.id === lot.id ? updated : l)))
      }
      if (action === 'delete') {
        await deleteLot(lot.id)
        setLots((prev) => prev.filter((l) => l.id !== lot.id))
      }
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setActing((a) => ({ ...a, [key]: false }))
    }
  }

  return (
    <div className="admin-inventory-page">
      <section className="admin-inventory-hero">
        <div>
          <span className="admin-eyebrow">Admin inventory</span>
          <h1>Manage every scanned lot with room for detail.</h1>
          <p>Review value, material, scan thumbnails, impact, and market state before publishing or removing lots.</p>
        </div>
        <div className="admin-inventory-total">
          <span>Live inventory value</span>
          <strong>{formatMoney(summary.liveValue)}</strong>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="admin-inventory-kpis">
        <InventoryKpi label="Available" value={summary.available} detail={formatMoney(summary.liveValue)} />
        <InventoryKpi label="Hidden" value={summary.unlisted} detail={`${formatMoney(summary.hiddenValue)} off market`} />
        <InventoryKpi label="Claimed" value={summary.claimed} detail="sold or reserved" />
        <InventoryKpi label="Total Weight" value={formatWeightKg(summary.weight)} detail={`${lots.length} total lots`} />
      </section>

      <section className="admin-inventory-workbench">
        <div className="admin-inventory-toolbar">
          <div>
            <span className="admin-eyebrow">Action queue</span>
            <h2>All Lots</h2>
          </div>
          <div className="admin-inventory-filters">
            <select value={filters.fabric_type} onChange={(e) => setFilters((f) => ({ ...f, fabric_type: e.target.value }))}>
              <option value="">All fabrics</option>
              {allFabricTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            <select value={filters.color_name} onChange={(e) => setFilters((f) => ({ ...f, color_name: e.target.value }))}>
              <option value="">All colors</option>
              {allColors.map((color) => <option key={color} value={color}>{color}</option>)}
            </select>
            <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
              <option value="">All statuses</option>
              <option value="available">Available</option>
              <option value="unlisted">Unlisted</option>
              <option value="claimed">Claimed</option>
            </select>
            {(filters.fabric_type || filters.color_name || filters.status) && (
              <button type="button" className="btn-ghost" onClick={() => setFilters({ fabric_type: '', color_name: '', status: '' })}>
                Clear
              </button>
            )}
          </div>
        </div>

        <div className="admin-inventory-list">
          {lots.map((lot) => (
            <InventoryRow
              key={lot.id}
              lot={lot}
              busy={acting[`delist-${lot.id}`] || acting[`relist-${lot.id}`] || acting[`delete-${lot.id}`]}
              onAction={handleAction}
            />
          ))}
          {lots.length === 0 && (
            <div className="admin-empty-panel">No lots match these filters.</div>
          )}
        </div>
      </section>
    </div>
  )
}

function InventoryKpi({ label, value, detail }) {
  return (
    <article className="admin-inventory-kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  )
}

function InventoryRow({ lot, busy, onAction }) {
  const pricePerKg = lot.weight_kg > 0 ? lot.current_price_usd / lot.weight_kg : 0
  const thumbnail = imageSrc(lot.piece_images)
  return (
    <article className={`admin-inventory-row admin-inventory-row--${lot.status}`}>
      <div className="admin-inventory-thumb" style={{ background: lot.color_hex }}>
        {thumbnail && <img src={thumbnail} alt="" />}
      </div>
      <div className="admin-inventory-main">
        <div className="admin-inventory-title-row">
          <div>
            <h3>{lot.name}</h3>
            <p>{lot.fabric_type} · {lot.composition}</p>
          </div>
          <span className={`admin-status admin-status--${lot.status}`}>{lot.status}</span>
        </div>
        <div className="admin-inventory-meta">
          <span><strong>{formatWeightKg(lot.weight_kg)}</strong> weight</span>
          <span><strong>{lot.piece_count}</strong> pieces</span>
          <span><strong>{lot.color_name}</strong> color</span>
          <span><strong>{lot.days_listed}d</strong> listed</span>
        </div>
      </div>
      <div className="admin-inventory-value">
        <strong>{formatMoney(lot.current_price_usd)}</strong>
        <span>{formatUnitPrice(pricePerKg)}</span>
        {lot.price_decay_pct > 0 && <small>{lot.price_decay_pct}% price decay</small>}
      </div>
      <div className="admin-inventory-impact">
        <span>{formatWeightKg(lot.carbon_saved_kg)} CO2</span>
        <span>{formatWater(lot.water_saved_l)} water</span>
      </div>
      <div className="admin-inventory-actions">
        {lot.status === 'claimed' ? (
          <span className="admin-claimed-by">Claimed by {lot.claimed_by}</span>
        ) : lot.status === 'unlisted' ? (
          <button type="button" onClick={() => onAction(lot, 'relist')} disabled={busy}>Publish</button>
        ) : (
          <button type="button" className="btn-ghost" onClick={() => onAction(lot, 'delist')} disabled={busy}>Delist</button>
        )}
        <button type="button" className="btn-ghost admin-danger-btn" onClick={() => onAction(lot, 'delete')} disabled={busy}>
          Delete
        </button>
      </div>
    </article>
  )
}

function imageSrc(images) {
  if (!Array.isArray(images) || images.length === 0) return null
  const first = images[0]
  if (typeof first === 'string') return first
  return first?.src || first?.url || first?.crop_data_url || first?.data_url || null
}

function formatWater(value) {
  const liters = Number(value) || 0
  if (liters <= 0) return '0 L'
  if (liters < 10) return `${liters.toFixed(1)} L`
  if (liters < 1000) return `${Math.round(liters).toLocaleString()} L`
  return `${(liters / 1000).toFixed(liters >= 10000 ? 0 : 1)} kL`
}
