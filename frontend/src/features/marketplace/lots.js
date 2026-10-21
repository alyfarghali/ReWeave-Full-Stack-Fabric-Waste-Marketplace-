// Lot logic shared by the marketplace grid and the supplier map.
import { useState } from 'react'
import { formatInputKg, lotQuantityStep } from '../../shared/formatters.js'
import { useCart } from './cart/CartContext.jsx'

export function firstImage(lot) {
  return lot?.piece_images?.[0]?.src || null
}

// Matching lots from different scans (same lot_key) are shown to buyers as one
// listing; component_lots keeps the originals so checkout can claim each one.
export function groupLots(lots) {
  const groups = new Map()
  for (const lot of lots) {
    const key = lot.lot_key
    const existing = groups.get(key)
    const images = lot.piece_images || []
    if (!existing) {
      groups.set(key, {
        ...lot,
        id: `group:${key}`,
        lot_key: key,
        component_lots: [lot],
        source_count: 1,
        piece_images: images,
      })
      continue
    }

    existing.component_lots.push(lot)
    existing.source_count += 1
    existing.weight_kg = Number((existing.weight_kg + lot.weight_kg).toFixed(3))
    existing.piece_count += lot.piece_count
    existing.price_usd = Number((existing.price_usd + lot.price_usd).toFixed(2))
    existing.current_price_usd = Number((existing.current_price_usd + lot.current_price_usd).toFixed(2))
    existing.piece_images = [...existing.piece_images, ...images].slice(0, 24)
    if (new Date(lot.created_at) > new Date(existing.created_at)) existing.created_at = lot.created_at
    existing.days_listed = Math.min(existing.days_listed, lot.days_listed)
  }

  return [...groups.values()].map((lot) => ({
    ...lot,
    component_lots: lot.component_lots.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)),
  }))
}

// The quantity a buyer has dialed in for each lot: the cart's quantity once the
// lot is added, otherwise a local draft (half the lot by default).
export function useLotQuantities() {
  const { cart, updateQty, removeFromCart } = useCart()
  const [draftQty, setDraftQty] = useState({})

  function selectedQty(lot) {
    return cart[lot.id]?.qty ?? draftQty[lot.id] ?? defaultQty(lot.weight_kg)
  }

  function setQty(lot, value) {
    const next = clampQty(Number(value), lot.weight_kg)
    setDraftQty((prev) => ({ ...prev, [lot.id]: next }))
    if (cart[lot.id]) {
      if (next > 0) updateQty(lot.id, next)
      else removeFromCart(lot.id)
    }
  }

  return { selectedQty, setQty }
}

// Slider and number-field settings for a lot. Lots under 1 kg are entered in grams.
export function quantityInput(lot, qty) {
  const step = lotQuantityStep(lot.weight_kg)
  const grams = lot.weight_kg < 1
  return {
    step,
    unit: grams ? 'g' : 'kg',
    inputStep: grams ? step * 1000 : step,
    inputMax: grams ? lot.weight_kg * 1000 : lot.weight_kg,
    inputValue: grams ? formatInputGrams(qty) : formatInputKg(qty),
    fromInput: (value) => (grams ? Number(value) / 1000 : value),
  }
}

function defaultQty(weightKg) {
  const weight = Number(weightKg) || 0
  if (weight <= 0) return 0
  if (weight <= 0.25) return weight
  return Number(Math.min(weight, Math.max(0.1, weight * 0.5)).toFixed(3))
}

function clampQty(value, max) {
  const maximum = Number(max) || 0
  if (!Number.isFinite(value)) return 0
  return Number(Math.min(Math.max(value, 0), maximum).toFixed(3))
}

function formatInputGrams(kg) {
  const grams = (Number(kg) || 0) * 1000
  return grams < 10 ? grams.toFixed(1).replace(/\.?0+$/, '') : String(Math.round(grams))
}
