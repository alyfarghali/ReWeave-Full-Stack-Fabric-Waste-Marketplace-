import { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { getMe, saveMyLocation } from '../auth/api.js'
import FactoryPanel from './FactoryPanel.jsx'
import { DASH_SEQ, arcCoords, buildFactories, haversineKm } from './geo.js'

// Vite exposes this at build time. Keep the real value in frontend/.env.
const TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''

// Default buyer position — NYC garment district, until the browser shares a real one
const DEFAULT_BUYER = { lat: 40.7128, lng: -74.006 }

export default function SupplierMap({ lots }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef([])
  const rafRef = useRef(null)
  const [selected, setSelected] = useState(null)
  const [buyerPos, setBuyerPos] = useState(DEFAULT_BUYER)
  const [locating, setLocating] = useState(false)
  const [located, setLocated] = useState(false)
  const [placeNames, setPlaceNames] = useState({})

  // Real origins captured from the factory floor. One scan with a shared
  // location gives one populated pin, so a single scan already looks right.
  const rawFactories = buildFactories(lots)
  const factories = rawFactories.map(f => ({ ...f, name: placeNames[f.key] || 'Factory location' }))
  const factoryKeys = rawFactories.map(f => f.key).join('|')
  const sel = selected !== null && selected < factories.length ? factories[selected] : null

  // Init map once
  useEffect(() => {
    if (!TOKEN || mapRef.current) return
    mapboxgl.accessToken = TOKEN

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [-83.5, 34.4],
      zoom: 5.5,
      attributionControl: false,
    })

    map.addControl(new mapboxgl.AttributionControl({ compact: true }), 'bottom-right')
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Use the buyer's saved location if we have one, otherwise ask the browser
  // and persist whatever it returns so the next visit is instant.
  useEffect(() => {
    let cancelled = false
    getMe()
      .then(me => {
        if (cancelled) return
        if (typeof me?.lat === 'number' && typeof me?.lng === 'number') {
          setBuyerPos({ lat: me.lat, lng: me.lng })
          setLocated(true)
        } else {
          locateMe(true)
        }
      })
      .catch(() => { if (!cancelled) locateMe(true) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Redraw factory markers when lots or selection changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const render = () => {
      markersRef.current.forEach(m => m.remove())
      markersRef.current = []

      factories.forEach((factory, i) => {
        const el = document.createElement('div')
        el.className = `map-pin${selected === i ? ' map-pin--active' : ''}`
        el.innerHTML = `<span class="map-pin-count">${factory.lots.length}</span>`
        el.addEventListener('click', e => {
          e.stopPropagation()
          setSelected(prev => (prev === i ? null : i))
        })

        const marker = new mapboxgl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat([factory.lng, factory.lat])
          .addTo(map)
        markersRef.current.push(marker)
      })
    }

    if (map.isStyleLoaded()) render()
    else map.once('load', render)
  }, [lots, selected])

  // Animated waste-flow arcs + buyer dot
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const draw = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)

      // Clean up previous layers/sources
      ;['flow-anim', 'flow-base', 'buyer-pulse', 'buyer-dot'].forEach(id => {
        if (map.getLayer(id)) map.removeLayer(id)
      })
      ;['flow-src', 'buyer-src'].forEach(id => {
        if (map.getSource(id)) map.removeSource(id)
      })

      const features = factories
        // Only draw a flow when there is real distance to cover. When the buyer
        // is essentially at the factory there is no meaningful route to show.
        .filter(f => f.lots.length > 0 && haversineKm(buyerPos.lat, buyerPos.lng, f.lat, f.lng) > 8)
        .map(f => ({
          type: 'Feature',
          geometry: {
            type: 'LineString',
            coordinates: arcCoords([f.lng, f.lat], [buyerPos.lng, buyerPos.lat]),
          },
          properties: {},
        }))

      map.addSource('flow-src', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features },
      })
      map.addLayer({
        id: 'flow-base',
        type: 'line',
        source: 'flow-src',
        paint: { 'line-color': '#166534', 'line-width': 1.5, 'line-opacity': 0.14 },
      })
      map.addLayer({
        id: 'flow-anim',
        type: 'line',
        source: 'flow-src',
        paint: {
          'line-color': '#166534',
          'line-width': 2.5,
          'line-opacity': 0.8,
          'line-dasharray': [0, 4, 3],
        },
      })

      map.addSource('buyer-src', {
        type: 'geojson',
        data: {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [buyerPos.lng, buyerPos.lat] },
          properties: {},
        },
      })
      map.addLayer({
        id: 'buyer-pulse',
        type: 'circle',
        source: 'buyer-src',
        paint: { 'circle-radius': 16, 'circle-color': '#166534', 'circle-opacity': 0.12 },
      })
      map.addLayer({
        id: 'buyer-dot',
        type: 'circle',
        source: 'buyer-src',
        paint: {
          'circle-radius': 7,
          'circle-color': '#166534',
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#fff',
        },
      })

      // Animate the dash pattern so flows feel like material moving
      let step = 0
      let lastTs = 0
      const animate = ts => {
        if (!mapRef.current) return
        if (ts - lastTs > 55) {
          step = (step + 1) % DASH_SEQ.length
          if (map.getLayer('flow-anim')) {
            map.setPaintProperty('flow-anim', 'line-dasharray', DASH_SEQ[step])
          }
          lastTs = ts
        }
        rafRef.current = requestAnimationFrame(animate)
      }
      rafRef.current = requestAnimationFrame(animate)
    }

    if (map.isStyleLoaded()) draw()
    else map.once('load', draw)
  }, [buyerPos, lots])

  // Turn each origin's coordinates into a real place name via Mapbox reverse
  // geocoding, instead of inventing a factory name.
  useEffect(() => {
    if (!TOKEN || rawFactories.length === 0) return
    let cancelled = false
    Promise.all(rawFactories.map(async (f) => {
      try {
        const res = await fetch(
          `https://api.mapbox.com/geocoding/v5/mapbox.places/${f.lng},${f.lat}.json` +
          `?access_token=${TOKEN}&types=place,locality,region&limit=1`
        )
        const json = await res.json()
        const feat = json?.features?.[0]
        return [f.key, feat?.text || feat?.place_name || 'Factory location']
      } catch {
        return [f.key, 'Factory location']
      }
    })).then((entries) => {
      if (cancelled) return
      setPlaceNames((prev) => {
        const next = { ...prev }
        let changed = false
        for (const [k, v] of entries) if (next[k] !== v) { next[k] = v; changed = true }
        return changed ? next : prev
      })
    })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [factoryKeys])

  // Frame the map. With a single factory we center tightly on it (and only pull
  // in the buyer when they are nearby), so a single pin never floats off-center.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const apply = () => {
      if (factories.length === 0) {
        map.flyTo({ center: [buyerPos.lng, buyerPos.lat], zoom: 4.5, duration: 900 })
        return
      }
      const nearestKm = Math.min(
        ...factories.map(f => haversineKm(buyerPos.lat, buyerPos.lng, f.lat, f.lng))
      )
      const includeBuyer = nearestKm > 8 && nearestKm < 400
      if (factories.length === 1 && !includeBuyer) {
        map.flyTo({ center: [factories[0].lng, factories[0].lat], zoom: 9.5, duration: 1100 })
        return
      }
      const bounds = new mapboxgl.LngLatBounds()
      factories.forEach(f => bounds.extend([f.lng, f.lat]))
      if (includeBuyer) bounds.extend([buyerPos.lng, buyerPos.lat])
      map.fitBounds(bounds, { padding: 110, maxZoom: 10, duration: 1100 })
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lots, buyerPos])

  function locateMe(silent = false) {
    if (!navigator.geolocation || locating) return
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude: lat, longitude: lng } = pos.coords
        setBuyerPos({ lat, lng })
        setLocated(true)
        setLocating(false)
        // Persist so the map and shipping math use it on the next visit too.
        saveMyLocation(lat, lng).catch(() => {})
      },
      () => setLocating(false),
      { timeout: 8000 }
    )
  }

  return (
    <div className="supplier-map-layout">
      {/* Map canvas */}
      <div className="supplier-map-canvas-wrap">
        <div ref={containerRef} className="supplier-map-canvas" />

        <div className="map-overlay-controls">
          <button className="map-locate-btn" onClick={() => locateMe(false)} disabled={locating}>
            {locating ? 'Locating…' : located ? '⊙ Using your location' : '⊙ Use my location'}
          </button>
        </div>

        <div className="map-legend">
          <div className="map-legend-row">
            <span className="map-legend-pin" />
            <span>Factory with lots available</span>
          </div>
          <div className="map-legend-row">
            <span className="map-legend-arc" />
            <span>Textile flow to you</span>
          </div>
          <div className="map-legend-row">
            <span className="map-legend-buyer" />
            <span>Your location</span>
          </div>
        </div>

        {factories.length === 0 && (
          <div className="map-empty-overlay">
            <div className="map-empty-card">
              <div className="map-empty-title">No factory locations yet</div>
              <div className="map-empty-sub">
                When a factory worker shares their location during a scan, their lots
                show up here on the map.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="supplier-map-sidebar">
        <FactoryPanel factories={factories} selected={sel} onSelect={setSelected} buyerPos={buyerPos} />
      </div>
    </div>
  )
}
