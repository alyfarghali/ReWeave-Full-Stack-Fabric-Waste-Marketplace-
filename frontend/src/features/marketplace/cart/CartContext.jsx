import { createContext, useContext, useState } from 'react'
import { claimLot } from '../api.js'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  // Items: { [lotId]: { lot, buyerName, qty? } }
  // buyerName is only meaningful for admin assignment; buyers always claim as
  // themselves (the server reads identity from the auth token).
  const [cart, setCart] = useState({})
  const [isOpen, setIsOpen] = useState(false)
  const [placing, setPlacing] = useState(false)
  const [lastSuccess, setLastSuccess] = useState(null)
  const [lastOrder, setLastOrder] = useState(null)

  const items = Object.values(cart)
  const total = items.reduce((s, item) => s + itemPrice(item), 0)

  function addToCart(lot, buyerName = null, qty = null) {
    const max = Number(lot.weight_kg) || 0
    const safeQty = qty == null ? max : Math.min(Math.max(Number(qty) || 0, 0), max)
    if (safeQty <= 0) return
    setCart(prev => ({ ...prev, [lot.id]: { lot, buyerName, qty: safeQty } }))
    setIsOpen(true)
  }

  function updateQty(lotId, qty) {
    const safeQty = Number(qty) || 0
    if (safeQty <= 0) return removeFromCart(lotId)
    setCart(prev => prev[lotId] ? { ...prev, [lotId]: { ...prev[lotId], qty: safeQty } } : prev)
  }

  function removeFromCart(lotId) {
    setCart(prev => {
      const next = { ...prev }
      delete next[lotId]
      return next
    })
  }

  function clearCart() { setCart({}) }

  // fallbackBuyerName is shown in the order summary; the server decides who claims.
  async function checkout(fallbackBuyerName, onDone) {
    if (!items.length || placing) return
    setPlacing(true)
    // Snapshot the order before we clear the cart, so the confirmation popup
    // can show what was just claimed and the impact it carried.
    const summary = items.map(({ lot, qty }) => {
      const weight = qty == null ? lot.weight_kg : qty
      const ratio = lot.weight_kg > 0 ? Math.min(weight / lot.weight_kg, 1) : 1
      return {
        name: lot.name,
        fabric_type: lot.fabric_type,
        color_hex: lot.color_hex,
        weight,
        price: itemPrice({ lot, qty }),
        carbon: (lot.carbon_saved_kg || 0) * ratio,
        water: (lot.water_saved_l || 0) * ratio,
      }
    })
    try {
      for (const { lot, buyerName, qty } of items) {
        const components = lot.component_lots?.length ? lot.component_lots : [lot]
        let remaining = qty == null ? lot.weight_kg : qty
        for (const component of components) {
          if (remaining <= 0) break
          const componentWeight = Number(component.weight_kg) || 0
          if (componentWeight <= 0) continue
          const claimQty = Math.min(remaining, componentWeight)
          await claimLot(component.id, buyerName || fallbackBuyerName, claimQty)
          remaining = Number((remaining - claimQty).toFixed(3))
        }
      }
      const count = items.length
      clearCart()
      setIsOpen(false)
      setLastOrder({
        count,
        lots: summary,
        totalPrice: summary.reduce((s, l) => s + l.price, 0),
        totalWeight: summary.reduce((s, l) => s + l.weight, 0),
        totalCarbon: summary.reduce((s, l) => s + l.carbon, 0),
        totalWater: summary.reduce((s, l) => s + l.water, 0),
      })
      window.dispatchEvent(new CustomEvent('lots:changed'))
      onDone?.()
    } catch (err) {
      setLastSuccess(`Checkout failed: ${err?.message || 'unknown error'}`)
      setTimeout(() => setLastSuccess(null), 7000)
    } finally {
      setPlacing(false)
    }
  }

  return (
    <CartContext.Provider value={{
      cart, items, total,
      addToCart, updateQty, removeFromCart, clearCart, checkout,
      isOpen, setIsOpen,
      placing, lastSuccess,
      lastOrder, clearLastOrder: () => setLastOrder(null),
    }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  return useContext(CartContext)
}

// Price for a partial quantity, pro-rated from the lot's current price.
export function itemPrice({ lot, qty }) {
  const totalWeight = Number(lot.weight_kg) || 0
  const totalPrice = Number(lot.current_price_usd) || 0
  if (!qty || qty >= totalWeight || totalWeight <= 0) return totalPrice
  return Number((totalPrice * (qty / totalWeight)).toFixed(4))
}
