// Geography for the supplier map: clustering lot origins into factories,
// distances, freight estimates, and the curved flow lines.

const FACTORY_CLUSTER_RADIUS_KM = 1.0

// Build the map's factories from the real origins stamped on lots at scan time.
// Lots without a shared location simply do not appear, so there is no sample data.
// Names come from reverse geocoding the coordinates (see the component), not from
// anything hardcoded.
export function buildFactories(lots) {
  const groups = []
  for (const lot of lots) {
    if (typeof lot.origin_lat !== 'number' || typeof lot.origin_lng !== 'number') continue
    const existing = groups.find((group) =>
      haversineKm(group.lat, group.lng, lot.origin_lat, lot.origin_lng) <= FACTORY_CLUSTER_RADIUS_KM
    )

    if (existing) {
      const nextCount = existing.lots.length + 1
      existing.lat = (existing.lat * existing.lots.length + lot.origin_lat) / nextCount
      existing.lng = (existing.lng * existing.lots.length + lot.origin_lng) / nextCount
      existing.lots.push(lot)
    } else {
      groups.push({ lat: lot.origin_lat, lng: lot.origin_lng, lots: [lot] })
    }
  }
  return groups.map((g, i) => ({
    id: i,
    key: `${g.lat.toFixed(3)},${g.lng.toFixed(3)}`,
    lat: g.lat,
    lng: g.lng,
    lots: g.lots,
    totalKg: g.lots.reduce((s, l) => s + (l.weight_kg || 0), 0),
  }))
}

export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2
  return R * 2 * Math.asin(Math.sqrt(a))
}

export function kmToMiles(km) {
  return km * 0.621371
}

// $0.08 / lb / 100 miles — standard LTL freight estimate
export function shippingEst(km, weightKg) {
  const miles = kmToMiles(km)
  const lbs = weightKg * 2.205
  return (miles / 100) * lbs * 0.08
}

// Curved flow line. The bulge is perpendicular to the route and scaled to its
// length, so short routes stay gently curved instead of spiking straight up.
export function arcCoords(from, to, steps = 64) {
  const [x1, y1] = from
  const [x2, y2] = to
  const dx = x2 - x1
  const dy = y2 - y1
  const dist = Math.hypot(dx, dy) || 1
  const nx = -dy / dist
  const ny = dx / dist
  const bulge = dist * 0.18
  const pts = []
  for (let i = 0; i <= steps; i++) {
    const t = i / steps
    const offset = Math.sin(Math.PI * t) * bulge
    pts.push([x1 + dx * t + nx * offset, y1 + dy * t + ny * offset])
  }
  return pts
}

// Mapbox animated dash sequence (from the Mapbox line-animation example)
export const DASH_SEQ = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5],
  [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5],
  [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
]
