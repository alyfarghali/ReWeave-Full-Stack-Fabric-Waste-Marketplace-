import { useEffect, useState } from 'react'
import { getLots } from './api.js'
import { firstImage } from './lots.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { formatDateEastern, formatImpactMass, formatMoney, formatWater, formatWeightKg } from '../../shared/formatters.js'

function ImpactCert({ orders }) {
  const totalCarbon = orders.reduce((s, o) => s + (o.carbon_saved_kg || 0), 0)
  const totalWater = orders.reduce((s, o) => s + (o.water_saved_l || 0), 0)
  const totalWeight = orders.reduce((s, o) => s + (o.weight_kg || 0), 0)
  const totalSpend = orders.reduce((s, o) => s + (o.price_usd || 0), 0)

  if (totalCarbon === 0) return null

  const showers = Math.round(totalWater / 65)

  return (
    <div className="orders-cert">
      <div className="orders-cert-header">
        <div className="orders-cert-eyebrow">Your impact so far</div>
        <div className="orders-cert-title">You have kept {formatWeightKg(totalWeight)} of fabric out of landfill</div>
      </div>
      <div className="orders-cert-stats">
        <div className="orders-cert-stat">
          <div className="orders-cert-value">{formatImpactMass(totalCarbon)}</div>
          <div className="orders-cert-label">CO₂ prevented</div>
          <div className="orders-cert-equiv">vs. making it new</div>
        </div>
        <div className="orders-cert-divider" />
        <div className="orders-cert-stat">
          <div className="orders-cert-value">{formatWater(totalWater)}</div>
          <div className="orders-cert-label">Water conserved</div>
          <div className="orders-cert-equiv">about {showers.toLocaleString()} showers</div>
        </div>
        <div className="orders-cert-divider" />
        <div className="orders-cert-stat">
          <div className="orders-cert-value">{formatWeightKg(totalWeight)}</div>
          <div className="orders-cert-label">Fabric diverted</div>
          <div className="orders-cert-equiv">kept out of landfill</div>
        </div>
        <div className="orders-cert-divider" />
        <div className="orders-cert-stat">
          <div className="orders-cert-value">{formatMoney(totalSpend)}</div>
          <div className="orders-cert-label">Total invested</div>
          <div className="orders-cert-equiv">in circular textiles</div>
        </div>
      </div>
    </div>
  )
}

export default function OrdersPage() {
  const { user } = useAuth()
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  function load() {
    if (!user?.name) return
    setLoading(true)
    getLots({ status: 'claimed', claimed_by: user.name })
      .then(data => { setOrders(data); setError(null) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    window.addEventListener('lots:changed', load)
    return () => window.removeEventListener('lots:changed', load)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.name])

  if (loading) return (
    <div className="buyer-page">
      <div className="buyer-empty"><h2>Loading orders</h2><p className="muted">Pulling up what you have claimed.</p></div>
    </div>
  )
  if (error) return (
    <div className="buyer-page"><div className="error">{error}</div></div>
  )

  const sorted = [...orders].sort((a, b) => new Date(b.claimed_at) - new Date(a.claimed_at))

  return (
    <div className="buyer-page">
      <div className="orders-header">
        <div>
          <h1 style={{ marginBottom: 2 }}>My Orders</h1>
          <p className="subtitle" style={{ margin: 0 }}>
            {orders.length} lot{orders.length !== 1 ? 's' : ''} claimed and headed for reuse
          </p>
        </div>
      </div>

      {orders.length === 0 ? (
        <div className="orders-empty">
          <div className="orders-empty-icon">○</div>
          <div className="orders-empty-title">No orders yet</div>
          <div className="orders-empty-sub">
            Browse the available lots and claim the material you need.
          </div>
        </div>
      ) : (
        <>
          <ImpactCert orders={sorted} />

          <div className="orders-list">
            {sorted.map(order => {
              const img = firstImage(order)
              return (
                <div className="order-card" key={order.id}>
                  {img ? (
                    <img className="order-card-thumb" src={img} alt={order.name} />
                  ) : (
                    <div className="order-card-thumb order-card-thumb--swatch" style={{ background: order.color_hex }} />
                  )}
                  <div className="order-card-body">
                    <div className="order-card-top">
                      <div>
                        <div className="order-card-name">{order.name}</div>
                        <div className="order-card-meta">
                          {order.fabric_type} · {order.color_name} · {order.composition}
                        </div>
                      </div>
                      <div className="order-card-price">{formatMoney(order.price_usd)}</div>
                    </div>

                    <div className="order-card-stats">
                      <div className="order-stat">
                        <span className="order-stat-val">{formatWeightKg(order.weight_kg)}</span>
                        <span className="order-stat-lbl">weight</span>
                      </div>
                      <div className="order-stat">
                        <span className="order-stat-val">{order.piece_count} pcs</span>
                        <span className="order-stat-lbl">pieces</span>
                      </div>
                      <div className="order-stat order-stat--green">
                        <span className="order-stat-val">{formatImpactMass(order.carbon_saved_kg)}</span>
                        <span className="order-stat-lbl">CO₂ saved</span>
                      </div>
                      <div className="order-stat order-stat--blue">
                        <span className="order-stat-val">{formatWater(order.water_saved_l)}</span>
                        <span className="order-stat-lbl">water saved</span>
                      </div>
                    </div>

                    <div className="order-card-footer">
                      <span className="order-card-date">Claimed {formatDateEastern(order.claimed_at)}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
