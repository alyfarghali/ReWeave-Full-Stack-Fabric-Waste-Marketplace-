import { useEffect, useMemo, useState } from 'react'
import { getLots } from './api.js'
import { itemPrice, useCart } from './cart/CartContext.jsx'
import { groupLots, quantityInput, useLotQuantities } from './lots.js'
import SupplierMap from './SupplierMap.jsx'
import LotDetailModal from './LotDetailModal.jsx'
import { capitalize, formatMoney, formatUnitPrice, formatWeightKg } from '../../shared/formatters.js'

export default function MarketplacePage() {
  const { cart, addToCart, removeFromCart } = useCart()
  const { selectedQty, setQty } = useLotQuantities()

  const [lots, setLots] = useState([])
  const [filters, setFilters] = useState({ fabric_type: '', color_name: '', query: '', sort: 'newest' })
  const [debouncedQ, setDebouncedQ] = useState('')
  const [imageIndex, setImageIndex] = useState({})
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('grid')
  const [detailLot, setDetailLot] = useState(null)

  // Debounce the search query 300ms before hitting Supabase FTS
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(filters.query), 300)
    return () => clearTimeout(t)
  }, [filters.query])

  function refresh(q = debouncedQ) {
    setLoading(true)
    getLots({ status: 'available', ...(q.trim() ? { q: q.trim() } : {}) })
      .then((data) => {
        setLots(data)
        setError(null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh(debouncedQ)
  }, [debouncedQ])

  // Checkout fires lots:changed; refetch so claimed lots disappear.
  useEffect(() => {
    const onChanged = () => refresh(debouncedQ)
    window.addEventListener('lots:changed', onChanged)
    return () => window.removeEventListener('lots:changed', onChanged)
  }, [debouncedQ])

  const groupedLots = useMemo(() => groupLots(lots), [lots])
  const fabricTypes = useMemo(() => [...new Set(groupedLots.map(l => l.fabric_type))].sort(), [groupedLots])
  const colors = useMemo(() => [...new Set(groupedLots.map(l => l.color_name))].sort(), [groupedLots])

  const visibleLots = useMemo(() => {
    return groupedLots
      .filter((lot) => !filters.fabric_type || lot.fabric_type === filters.fabric_type)
      .filter((lot) => !filters.color_name || lot.color_name === filters.color_name)
      .sort((a, b) => {
        if (filters.sort === 'price-low') return a.current_price_usd - b.current_price_usd
        if (filters.sort === 'price-high') return b.current_price_usd - a.current_price_usd
        if (filters.sort === 'weight-high') return b.weight_kg - a.weight_kg
        return new Date(b.created_at) - new Date(a.created_at)
      })
  }, [filters, groupedLots])

  function addSelected(lot) {
    const qty = selectedQty(lot)
    if (qty <= 0) return
    addToCart(lot, null, qty)
  }

  function cycleImage(lotId, count, direction) {
    if (count <= 1) return
    setImageIndex((prev) => {
      const current = prev[lotId] || 0
      return { ...prev, [lotId]: (current + direction + count) % count }
    })
  }

  const hasFilters = filters.fabric_type || filters.color_name || filters.query

  return (
    <div className="buyer-page">
      <div className="buyer-hero">
        <div>
          <h1>Available Lots</h1>
          <p className="subtitle">Grouped textile scrap inventory from factory scans, ready for quantity-based orders.</p>
        </div>
        <div className="buyer-hero-aside">
          <div className="buyer-view-toggle">
            <button
              className={view === 'grid' ? 'is-active' : ''}
              onClick={() => setView('grid')}
            >
              Grid
            </button>
            <button
              className={view === 'map' ? 'is-active' : ''}
              onClick={() => setView('map')}
            >
              Map
            </button>
          </div>
          <div className="buyer-hero-stats">
            <strong>{visibleLots.length}</strong>
            <span>{visibleLots.length === 1 ? 'listing' : 'listings'}</span>
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {view === 'map' && (
        <div className="buyer-map-wrap">
          <SupplierMap lots={lots} />
        </div>
      )}

      {view === 'grid' && (
      <>
      <div className="buyer-toolbar">
        <label className="buyer-search">
          <IconSearch />
          <input
            value={filters.query}
            onChange={e => setFilters(f => ({ ...f, query: e.target.value }))}
            placeholder="Search fabric, color, composition"
          />
        </label>

        <select
          value={filters.fabric_type}
          onChange={e => setFilters(f => ({ ...f, fabric_type: e.target.value }))}
        >
          <option value="">All fabrics</option>
          {fabricTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <select
          value={filters.color_name}
          onChange={e => setFilters(f => ({ ...f, color_name: e.target.value }))}
        >
          <option value="">All colors</option>
          {colors.map(c => <option key={c} value={c}>{capitalize(c)}</option>)}
        </select>

        <select
          value={filters.sort}
          onChange={e => setFilters(f => ({ ...f, sort: e.target.value }))}
        >
          <option value="newest">Newest first</option>
          <option value="weight-high">Most material</option>
          <option value="price-low">Price: low to high</option>
          <option value="price-high">Price: high to low</option>
        </select>

        {hasFilters && (
          <button
            className="btn-ghost"
            onClick={() => setFilters({ fabric_type: '', color_name: '', query: '', sort: 'newest' })}
          >
            Clear
          </button>
        )}
      </div>

      <div className="buyer-lot-grid">
        {visibleLots.map(lot => {
          const cartItem = cart[lot.id]
          const inCart = !!cartItem
          const qty = selectedQty(lot)
          const selectedPrice = itemPrice({ lot, qty })
          const images = lot.piece_images
          const activeImage = imageIndex[lot.id] || 0
          const hasDecay = lot.price_decay_pct > 0
          const perKg = lot.weight_kg > 0 ? lot.current_price_usd / lot.weight_kg : 0
          const input = quantityInput(lot, qty)

          return (
            <article className="buyer-lot-card" key={lot.id}>
              <div
                className="buyer-lot-media buyer-lot-media--clickable"
                onClick={() => setDetailLot(lot)}
                title="View lot details"
              >
                {images.length ? (
                  <>
                    <img src={images[activeImage]?.src} alt={`${lot.name} fabric piece ${activeImage + 1}`} />
                    {images.length > 1 && (
                      <div className="buyer-media-controls" onClick={e => e.stopPropagation()}>
                        <button type="button" onClick={() => cycleImage(lot.id, images.length, -1)} aria-label="Previous image">
                          <IconChevronLeft />
                        </button>
                        <span>{activeImage + 1} / {images.length}</span>
                        <button type="button" onClick={() => cycleImage(lot.id, images.length, 1)} aria-label="Next image">
                          <IconChevronRight />
                        </button>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="buyer-lot-fallback" style={{ background: lot.color_hex }}>
                    <span>{capitalize(lot.color_name)}</span>
                  </div>
                )}
              </div>

              <div className="buyer-lot-body">
                <div className="buyer-card-topline">
                  <span className="buyer-lot-type">{lot.fabric_type}</span>
                  {lot.source_count > 1 && <span className="buyer-merged-badge">{lot.source_count} scans merged</span>}
                </div>

                <div className="buyer-lot-name buyer-lot-name--clickable" onClick={() => setDetailLot(lot)}>{lot.name}</div>

                <div className="buyer-lot-meta-row">
                  <span className="buyer-swatch-dot" style={{ background: lot.color_hex }} />
                  <span>{capitalize(lot.color_name)}</span>
                  <span>{formatWeightKg(lot.weight_kg)}</span>
                  <span>{lot.piece_count} pcs</span>
                </div>

                <div className="buyer-price-row">
                  <div>
                    <div className="buyer-lot-price">{formatMoney(selectedPrice)}</div>
                    <div className="buyer-lot-perlb">
                      {formatUnitPrice(perKg)}
                      {hasDecay && <span> · {lot.price_decay_pct}% below list</span>}
                    </div>
                  </div>
                  <div className="buyer-weight-total">
                    <strong>{formatWeightKg(qty)}</strong>
                    <span>selected</span>
                  </div>
                </div>

                <div className="buyer-qty-row">
                  <input
                    type="range"
                    min={0}
                    max={lot.weight_kg}
                    step={input.step}
                    value={qty}
                    onChange={e => setQty(lot, e.target.value)}
                    className="buyer-slider"
                  />
                  <input
                    type="number"
                    min={0}
                    max={input.inputMax}
                    step={input.inputStep}
                    value={input.inputValue}
                    onChange={e => setQty(lot, input.fromInput(e.target.value))}
                    className="buyer-qty-input"
                    aria-label={`Quantity in ${input.unit === 'g' ? 'grams' : 'kilograms'} for ${lot.name}`}
                  />
                  <span className="buyer-qty-unit">{input.unit}</span>
                </div>

                <button
                  className={`buyer-lot-cta${inCart ? ' btn-added' : ''}`}
                  onClick={() => inCart ? removeFromCart(lot.id) : addSelected(lot)}
                  disabled={!inCart && qty <= 0}
                >
                  {inCart ? 'Remove from order' : 'Add selected'}
                </button>
              </div>
            </article>
          )
        })}
        {!loading && visibleLots.length === 0 && (
          <div className="buyer-empty">
            <h2>No matching lots</h2>
            <p className="muted">Try clearing the search or filters.</p>
          </div>
        )}
        {loading && (
          <div className="buyer-empty">
            <h2>Loading lots</h2>
            <p className="muted">Checking current factory inventory.</p>
          </div>
        )}
      </div>
      </>
      )}

      {detailLot && <LotDetailModal lot={detailLot} onClose={() => setDetailLot(null)} />}
    </div>
  )
}

function IconSearch() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.5-4.5" />
    </svg>
  )
}

function IconChevronLeft() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  )
}

function IconChevronRight() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18l6-6-6-6" />
    </svg>
  )
}
