import { postJson, request } from '../../shared/api.js'

export function getLots(filters = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, value)
  }
  const query = params.toString()
  return request(`/lots${query ? `?${query}` : ''}`)
}

// Buyers always claim as themselves (the server uses the token's identity);
// buyerName only takes effect when an admin assigns a lot to a named buyer.
export function claimLot(lotId, buyerName = null, quantityKg = null) {
  const body = {}
  if (buyerName) body.buyer_name = buyerName
  if (quantityKg !== undefined && quantityKg !== null) body.quantity_kg = quantityKg
  return postJson(`/lots/${lotId}/claim`, body)
}
