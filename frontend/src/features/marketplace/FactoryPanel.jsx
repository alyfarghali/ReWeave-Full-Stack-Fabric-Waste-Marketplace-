// Supplier map sidebar: the factory list, or one factory's lots with
// distance, freight estimate, and quantity pickers.
import { formatImpactMass, formatMoney, formatWater, formatWeightKg } from '../../shared/formatters.js'
import { itemPrice, useCart } from './cart/CartContext.jsx'
import { haversineKm, kmToMiles, shippingEst } from './geo.js'
import { firstImage, quantityInput, useLotQuantities } from './lots.js'

export default function FactoryPanel({ factories, selected, onSelect, buyerPos }) {
  // Held here, not per row, so dialed-in quantities survive switching factories.
  const quantities = useLotQuantities()
  const distanceKm = (factory) => haversineKm(buyerPos.lat, buyerPos.lng, factory.lat, factory.lng)

  if (!selected) {
    return (
      <div className="map-sidebar-hint">
        <div className="map-sidebar-hint-title">
          {factories.length === 0 ? 'Waiting on a factory scan' : 'Pick a factory'}
        </div>
        <div className="map-sidebar-hint-sub">
          {factories.length === 0
            ? 'Factory locations appear here once a worker shares their location while scanning a table.'
            : 'Tap a pin on the map to see the lots it has available and what shipping to you would run.'}
        </div>

        <div className="map-factory-list">
          {factories.map((f, i) => (
            <button key={f.id} className="map-factory-row" onClick={() => onSelect(i)}>
              <span className="map-factory-dot" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="map-factory-row-name">{f.name}</div>
                <div className="map-factory-row-meta">
                  {kmToMiles(distanceKm(f)).toFixed(0)} mi away · {formatWeightKg(f.totalKg)}
                </div>
              </div>
              <span className="map-factory-row-count">{f.lots.length} lots</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  const km = distanceKm(selected)
  return (
    <>
      <div className="map-sidebar-factory-header">
        <button className="map-back-btn" onClick={() => onSelect(null)}>
          ← All factories
        </button>
        <div className="map-sidebar-factory-name">{selected.name}</div>
        <div className="map-sidebar-factory-city">Shared from the factory floor</div>

        <div className="map-sidebar-factory-stats">
          <div className="map-stat">
            <div className="map-stat-val">{kmToMiles(km).toFixed(0)} mi</div>
            <div className="map-stat-label">Distance</div>
          </div>
          <div className="map-stat-divider" />
          <div className="map-stat">
            <div className="map-stat-val">{selected.lots.length}</div>
            <div className="map-stat-label">Lots</div>
          </div>
          <div className="map-stat-divider" />
          <div className="map-stat">
            <div className="map-stat-val">${shippingEst(km, selected.totalKg).toFixed(0)}</div>
            <div className="map-stat-label">Est. shipping</div>
          </div>
        </div>
      </div>

      <div className="map-sidebar-lots">
        {selected.lots.length === 0 ? (
          <p style={{ color: 'var(--c-muted)', fontSize: 13, padding: '20px 0' }}>
            Nothing available from this factory right now.
          </p>
        ) : (
          selected.lots.map(lot => <FactoryLot key={lot.id} lot={lot} quantities={quantities} />)
        )}
      </div>
    </>
  )
}

function FactoryLot({ lot, quantities: { selectedQty, setQty } }) {
  const { cart, addToCart, removeFromCart } = useCart()
  const inCart = !!cart[lot.id]
  const img = firstImage(lot)
  const qty = selectedQty(lot)
  const input = quantityInput(lot, qty)

  return (
    <div className={`map-lot-card${inCart ? ' map-lot-card--incart' : ''}`}>
      {img ? (
        <img className="map-lot-thumb" src={img} alt={`${lot.name} fabric`} />
      ) : (
        <div className="map-lot-thumb map-lot-thumb--swatch" style={{ background: lot.color_hex }} />
      )}
      <div className="map-lot-info">
        <div className="map-lot-type">{lot.fabric_type}</div>
        <div className="map-lot-name">{lot.name}</div>
        <div className="map-lot-price-row">
          <span className="map-lot-price">{formatMoney(itemPrice({ lot, qty }))}</span>
          {lot.price_decay_pct > 0 && <span className="map-lot-badge">−{lot.price_decay_pct}%</span>}
          <span className="map-lot-weight">{formatWeightKg(lot.weight_kg)}</span>
        </div>
        <div className="map-lot-impact">
          {formatImpactMass(lot.carbon_saved_kg)} CO₂ · {formatWater(lot.water_saved_l)} water
        </div>
        <div className="map-lot-qty">
          <input
            type="range"
            min={0}
            max={lot.weight_kg}
            step={input.step}
            value={qty}
            onChange={e => setQty(lot, e.target.value)}
            aria-label={`Quantity for ${lot.name}`}
          />
          <div className="map-lot-qty-field">
            <input
              type="number"
              min={0}
              max={input.inputMax}
              step={input.inputStep}
              value={input.inputValue}
              onChange={e => setQty(lot, input.fromInput(e.target.value))}
              aria-label={`Quantity in ${input.unit === 'g' ? 'grams' : 'kilograms'} for ${lot.name}`}
            />
            <span>{input.unit}</span>
          </div>
        </div>
      </div>
      <button
        className={`map-lot-btn${inCart ? ' map-lot-btn--added' : ''}`}
        onClick={() => (inCart ? removeFromCart(lot.id) : addToCart(lot, null, qty))}
        disabled={!inCart && qty <= 0}
        title={inCart ? 'Remove from order' : 'Add to order'}
      >
        {inCart ? 'Remove' : 'Add'}
      </button>
    </div>
  )
}
