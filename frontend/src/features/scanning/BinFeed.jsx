import { useEffect, useState, useRef } from 'react'
import { getLots } from '../marketplace/api.js'
import { FactoryHeader } from './FactoryHeader.jsx'
import { capitalize } from '../../shared/formatters.js'

const BINS = [
  { id: 'A', label: 'Bin A', desc: 'White / natural', colors: ['white', 'natural', 'cream', 'ivory'], bg: '#fbfaf7', border: '#d6cdbd' },
  { id: 'B', label: 'Bin B', desc: 'Blue / denim', colors: ['blue', 'navy', 'denim', 'indigo'], bg: '#f2f6fa', border: '#b8c7d8' },
  { id: 'C', label: 'Bin C', desc: 'Black / gray', colors: ['black', 'grey', 'gray', 'charcoal'], bg: '#f5f5f4', border: '#c7c7c3' },
  { id: 'D', label: 'Bin D', desc: 'Earth / warm', colors: ['beige', 'brown', 'tan', 'red', 'orange'], bg: '#fbf6ef', border: '#d7b98f' },
  { id: 'E', label: 'Bin E', desc: 'Mixed / review', colors: [], bg: '#f0fdf4', border: '#86b596' },
]

function assignBin(colorName) {
  const c = colorName.toLowerCase()
  for (const bin of BINS) {
    if (bin.colors.includes(c)) return bin
  }
  return BINS[4]
}

export default function BinFeed() {
  const [lots, setLots] = useState([])
  const [idx, setIdx] = useState(0)
  const [flash, setFlash] = useState(false)
  const [binCounts, setBinCounts] = useState({ A: 0, B: 0, C: 0, D: 0, E: 0 })
  const intervalRef = useRef(null)

  useEffect(() => {
    getLots().then(data => setLots(data.filter(l => l.status === 'available')))
  }, [])

  useEffect(() => {
    if (lots.length === 0) return
    intervalRef.current = setInterval(() => {
      setIdx(i => {
        const next = (i + 1) % lots.length
        const bin = assignBin(lots[next]?.color_name || '')
        setBinCounts(prev => ({ ...prev, [bin.id]: (prev[bin.id] || 0) + 1 }))
        setFlash(true)
        setTimeout(() => setFlash(false), 400)
        return next
      })
    }, 3000)
    return () => clearInterval(intervalRef.current)
  }, [lots])

  const current = lots[idx]
  const currentBin = current ? assignBin(current.color_name) : null
  const assignedCount = Object.values(binCounts).reduce((sum, count) => sum + count, 0)
  const recentLots = lots.slice(0, idx + 1).reverse().slice(0, 8)

  const totalPieces = Object.values(binCounts).reduce((a, b) => a + b, 0)

  return (
    <div className="factory-app factory-app--wide">
      <FactoryHeader />
      <main className="fx-main fx-main--wide">
        <section className="binfeed">
          <div className="fx-intro binfeed-head">
            <span className="fx-eyebrow">Live feed</span>
            <h1 className="fx-title">Bin feed</h1>
          </div>

          {current ? (
            <section className={`binfeed-current ${flash ? 'binfeed-flash' : ''}`} aria-live="polite">
              <div className="binfeed-piece">
                <span className="binfeed-label">Current lot</span>
                <div className="binfeed-piece-main">
                  <div className="binfeed-swatch" style={{ background: current.color_hex }} />
                  <div>
                    <div className="binfeed-piece-name">{capitalize(current.color_name)} - {current.fabric_type}</div>
                    <div className="binfeed-piece-meta">{current.composition} - {current.piece_count} pieces</div>
                  </div>
                </div>
              </div>
              <div className="binfeed-route" aria-hidden="true" />
              <div className="binfeed-bin-target" style={{ background: currentBin.bg, borderColor: currentBin.border }}>
                <span className="binfeed-label">Send to</span>
                <div className="binfeed-bin-id">{currentBin.label}</div>
                <div className="binfeed-bin-desc">{currentBin.desc}</div>
              </div>
            </section>
          ) : (
            <section className="binfeed-empty">
              <h2>No available lots yet</h2>
              <p>Scan a table first. New groups will appear here as soon as they are listed.</p>
            </section>
          )}

          <section className="binfeed-board">
            <div className="binfeed-section-head">
              <h2>Floor bins</h2>
              <span>{assignedCount} assigned this session</span>
            </div>
            <div className="binfeed-bins">
              {BINS.map(bin => (
                <div
                  key={bin.id}
                  className={`binfeed-bin-card ${currentBin?.id === bin.id && flash ? 'binfeed-bin-active' : ''}`}
                  style={{ background: bin.bg, borderColor: bin.border }}
                >
                  <div className="binfeed-bin-card-id">{bin.label}</div>
                  <div className="binfeed-bin-card-desc">{bin.desc}</div>
                  <div className="binfeed-bin-card-count">{binCounts[bin.id] || 0}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="binfeed-log">
            <div className="binfeed-section-head">
              <h2>Recent assignments</h2>
              <span>Latest 8 lots</span>
            </div>
            <div className="binfeed-log-list">
              {recentLots.length ? recentLots.map((lot, i) => {
                const bin = assignBin(lot.color_name)
                return (
                  <div key={`${lot.id}-${i}`} className="binfeed-log-row">
                    <div className="binfeed-log-swatch" style={{ background: lot.color_hex }} />
                    <span>{capitalize(lot.color_name)} {lot.fabric_type}</span>
                    <span className="binfeed-log-bin" style={{ background: bin.bg, borderColor: bin.border }}>
                      {bin.label}
                    </span>
                  </div>
                )
              }) : (
                <div className="binfeed-log-empty">Assignments will appear here after the first piece cycles.</div>
              )}
            </div>
          </section>
        </section>
      </main>
    </div>
  )
}
