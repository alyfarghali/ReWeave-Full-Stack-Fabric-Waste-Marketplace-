import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatImpactMass, formatMoney, formatWater, formatWeightKg } from '../../../shared/formatters.js'

// Shown right after a buyer checks out. Summarizes what they claimed and the
// impact it carried, then points them at their orders.
export default function OrderConfirmation({ order, onClose }) {
  const navigate = useNavigate()

  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!order) return null

  const { count, totalPrice, totalWeight, totalCarbon, totalWater, lots } = order
  const showers = Math.round(totalWater / 65)

  return (
    <>
      <div className="order-confirm-overlay" onClick={onClose} />
      <div className="order-confirm" role="dialog" aria-modal="true">
        <div className="order-confirm-top">
          <div className="order-confirm-check">✓</div>
          <div className="order-confirm-eyebrow">Order confirmed</div>
          <div className="order-confirm-title">
            {count} lot{count !== 1 ? 's' : ''} on the way
          </div>
          <div className="order-confirm-sub">
            {formatWeightKg(totalWeight)} of fabric reserved for you. The supplier has been notified.
          </div>
        </div>

        <div className="order-confirm-totals">
          <div className="order-confirm-total">
            <div className="order-confirm-total-val">{formatMoney(totalPrice)}</div>
            <div className="order-confirm-total-lbl">Total</div>
          </div>
          <div className="order-confirm-total-divider" />
          <div className="order-confirm-total">
            <div className="order-confirm-total-val">{formatImpactMass(totalCarbon)}</div>
            <div className="order-confirm-total-lbl">CO₂ saved</div>
          </div>
          <div className="order-confirm-total-divider" />
          <div className="order-confirm-total">
            <div className="order-confirm-total-val">{formatWater(totalWater)}</div>
            <div className="order-confirm-total-lbl">Water saved</div>
          </div>
        </div>

        <div className="order-confirm-impact-note">
          {showers >= 1
            ? `That is enough water for about ${showers.toLocaleString()} shower${showers !== 1 ? 's' : ''}.`
            : 'A small lot, but every bit of fabric reused keeps waste out of landfill.'}
        </div>

        <div className="order-confirm-list">
          {lots.map((l, i) => (
            <div className="order-confirm-row" key={i}>
              <span className="order-confirm-row-swatch" style={{ background: l.color_hex }} />
              <div className="order-confirm-row-info">
                <div className="order-confirm-row-name">{l.name}</div>
                <div className="order-confirm-row-meta">{l.fabric_type} · {formatWeightKg(l.weight)}</div>
              </div>
              <div className="order-confirm-row-price">{formatMoney(l.price)}</div>
            </div>
          ))}
        </div>

        <div className="order-confirm-actions">
          <button className="order-confirm-secondary" onClick={onClose}>Keep browsing</button>
          <button
            className="order-confirm-primary"
            onClick={() => { onClose(); navigate('/buyer/orders') }}
          >
            View my orders →
          </button>
        </div>
      </div>
    </>
  )
}
