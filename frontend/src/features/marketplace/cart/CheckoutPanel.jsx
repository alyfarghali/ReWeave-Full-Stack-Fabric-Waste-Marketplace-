import { useAuth } from '../../auth/AuthContext.jsx'
import { formatMoney, formatWeightKg } from '../../../shared/formatters.js'
import { itemPrice, useCart } from './CartContext.jsx'

export function CartButton() {
  const { items, total, isOpen, setIsOpen } = useCart()
  if (items.length === 0) return null
  return (
    <button
      className="nav-cart-btn"
      onClick={() => setIsOpen(o => !o)}
      aria-label="Open cart"
    >
      <span className="nav-cart-badge">{items.length}</span>
      <span style={{ fontSize: 12 }}>Order &nbsp;·&nbsp; {formatMoney(total)}</span>
    </button>
  )
}

export function CheckoutPanel() {
  const { user } = useAuth()
  const { items, total, removeFromCart, checkout, isOpen, setIsOpen, placing } = useCart()
  if (!isOpen) return null

  return (
    <>
      <div className="checkout-overlay" onClick={() => setIsOpen(false)} />
      <div className="checkout-panel">
        <div className="checkout-header">
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--c-muted)', marginBottom: 2 }}>
              Order Summary
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--c-text)' }}>
              Cart · {items.length} lot{items.length !== 1 ? 's' : ''}
            </div>
          </div>
          <button className="chat-close" onClick={() => setIsOpen(false)}>✕</button>
        </div>

        <div className="checkout-items">
          {items.map(({ lot, buyerName, qty }) => (
            <div className="checkout-item" key={lot.id}>
              <div className="checkout-swatch" style={{ background: lot.color_hex }} />
              <div className="checkout-item-info">
                <div className="checkout-item-name">{lot.name}</div>
                {buyerName
                  ? <div className="checkout-item-buyer">→ {buyerName}</div>
                  : <div className="checkout-item-buyer">→ {user?.name}</div>
                }
                <div className="checkout-item-meta">
                  {lot.fabric_type} · {formatWeightKg(qty || lot.weight_kg)}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div className="checkout-item-price">{formatMoney(itemPrice({ lot, qty }))}</div>
                <button className="cart-remove" style={{ marginTop: 4 }} onClick={() => removeFromCart(lot.id)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="checkout-footer">
          <div className="checkout-total-row">
            <span style={{ fontSize: 13, color: 'var(--c-muted)' }}>
              {items.length} lot{items.length !== 1 ? 's' : ''}
            </span>
            <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--c-text)', letterSpacing: '-0.5px' }}>
              {formatMoney(total)}
            </span>
          </div>
          <button
            className="checkout-btn"
            onClick={() => checkout(user?.name)}
            disabled={placing}
          >
            {placing ? 'Processing…' : 'Confirm & Claim All →'}
          </button>
          <p style={{ fontSize: 11, color: 'var(--c-muted)', margin: '8px 0 0', textAlign: 'center' }}>
            Lots will be marked as claimed immediately.
          </p>
        </div>
      </div>
    </>
  )
}
