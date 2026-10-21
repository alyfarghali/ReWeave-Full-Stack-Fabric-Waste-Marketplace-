// Continuous "live scan": streams generated camera frames, lists each one on the
// marketplace through the same endpoint as a real scan, and shows totals as they land.
import { useEffect, useRef, useState } from 'react'
import { formatMoney, formatWeightKg } from '../../shared/formatters.js'
import { listScan } from '../scanning/api.js'
import { generateFrame } from './generator.js'
import { renderCrops, renderFrame } from './render.js'
import './demo.css'

const TOTAL_PIECES = 1000
const PIECES_PER_FRAME = 50
const FRAME_INTERVAL_MS = 3000
const FRAMES = Math.ceil(TOTAL_PIECES / PIECES_PER_FRAME)

const EMPTY_TOTALS = { pieces: 0, frames: 0, lots: 0, weightKg: 0, carbonKg: 0, waterL: 0, valueUsd: 0 }

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export default function LiveScanDemo({ origin, onExit }) {
  const [status, setStatus] = useState('idle') // idle | running | done | stopped | error
  const [frameUrl, setFrameUrl] = useState(null)
  const [totals, setTotals] = useState(EMPTY_TOTALS)
  const [bins, setBins] = useState({})
  const [error, setError] = useState(null)
  const stopRef = useRef(false)

  useEffect(() => () => { stopRef.current = true }, [])

  async function start() {
    stopRef.current = false
    setStatus('running')
    setError(null)
    setTotals(EMPTY_TOTALS)
    setBins({})
    const seed = Date.now()

    for (let frame = 0; frame < FRAMES && !stopRef.current; frame++) {
      const startedAt = performance.now()
      const count = Math.min(PIECES_PER_FRAME, TOTAL_PIECES - frame * PIECES_PER_FRAME)
      const scan = generateFrame(seed + frame, count, frame * PIECES_PER_FRAME + 1)
      scan.annotated_image_data_url = renderFrame(scan)
      renderCrops(scan)
      setFrameUrl(scan.annotated_image_data_url)

      let listed
      try {
        listed = await listScan(withoutDrawingData(scan), origin || {})
      } catch (err) {
        setError(err.message || 'Listing failed')
        setStatus('error')
        return
      }
      record(scan, listed)
      await sleep(Math.max(0, FRAME_INTERVAL_MS - (performance.now() - startedAt)))
    }
    setStatus(stopRef.current ? 'stopped' : 'done')
  }

  function record(scan, listed) {
    setTotals((t) => ({
      pieces: t.pieces + scan.pieces.length,
      frames: t.frames + 1,
      lots: t.lots + listed.bins.length,
      weightKg: t.weightKg + listed.total_weight_kg,
      carbonKg: t.carbonKg + listed.total_carbon_saved_kg,
      waterL: t.waterL + listed.total_water_saved_l,
      valueUsd: t.valueUsd + listed.bins.reduce((sum, b) => sum + b.price_usd, 0),
    }))
    const colors = Object.fromEntries(scan.groups.map((g) => [g.sort_group_id, g.color_hex]))
    setBins((prev) => {
      const next = { ...prev }
      for (const bin of listed.bins) {
        const entry = next[bin.name] || { pieces: 0, kg: 0, color: colors[bin.sort_group_id] }
        next[bin.name] = { ...entry, pieces: entry.pieces + bin.piece_count, kg: entry.kg + bin.weight_kg }
      }
      return next
    })
  }

  const running = status === 'running'
  const progress = (totals.pieces / TOTAL_PIECES) * 100
  const binRows = Object.entries(bins).sort((a, b) => b[1].kg - a[1].kg)
  const maxKg = binRows[0]?.[1].kg || 1

  return (
    <section className="fx-stage demo-live">
      <div className="fx-intro">
        <span className="fx-eyebrow">Continuous scan · Reweave Vision Engine</span>
        <h1 className="fx-title">Live scan {TOTAL_PIECES.toLocaleString()} pieces</h1>
        <p className="fx-lead fx-lead--muted">
          Each frame is sorted into bins and listed on the marketplace as it is scanned.
        </p>
      </div>

      <div className="fx-frame fx-frame--plan demo-live-frame">
        {frameUrl ? <img src={frameUrl} alt="Live table scan" /> : <span className="demo-live-idle">Camera ready</span>}
        {running && <span className="demo-live-badge">● LIVE</span>}
      </div>

      <div className="fx-progress" aria-label="Scan progress">
        <div className="fx-progress-copy">
          <span className="fx-progress-label">Pieces scanned</span>
          <strong>{totals.pieces.toLocaleString()} of {TOTAL_PIECES.toLocaleString()}</strong>
        </div>
        <div className="fx-progress-bar">
          <div className="fx-progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="fx-cv-summary">
        <div className="fx-cv-stats">
          <Stat value={totals.lots} label="lots listed" />
          <Stat value={formatWeightKg(totals.weightKg)} label="diverted from landfill" />
          <Stat value={formatMoney(totals.valueUsd)} label="listed value" />
          <Stat value={`${totals.carbonKg.toFixed(1)} kg CO₂`} label="emissions avoided" tone="green" />
          <Stat value={`${Math.round(totals.waterL).toLocaleString()} L`} label="water saved" tone="blue" />
        </div>
      </div>

      {binRows.length > 0 && (
        <div className="demo-bins">
          {binRows.map(([name, bin]) => (
            <div className="demo-bin" key={name}>
              <span className="demo-bin-swatch" style={{ background: bin.color }} />
              <span className="demo-bin-name">{name}</span>
              <span className="demo-bin-bar">
                <span style={{ width: `${(bin.kg / maxKg) * 100}%`, background: bin.color }} />
              </span>
              <span className="demo-bin-meta">{bin.pieces} pcs · {formatWeightKg(bin.kg)}</span>
            </div>
          ))}
        </div>
      )}

      {status === 'error' && <div className="demo-error">{error}</div>}
      {status === 'done' && (
        <div className="demo-done">
          Listed {totals.lots} lots from {totals.pieces.toLocaleString()} pieces. Buyers can see them now.
        </div>
      )}

      <div className="fx-actions fx-actions--sticky">
        {running ? (
          <button type="button" className="fx-btn fx-btn--primary" onClick={() => { stopRef.current = true }}>
            Stop scanning
          </button>
        ) : (
          <button type="button" className="fx-btn fx-btn--primary" onClick={start}>
            {status === 'idle' ? 'Start live scan' : 'Scan another 1,000'}
          </button>
        )}
        <button type="button" className="fx-btn-text" onClick={onExit} disabled={running}>
          Back
        </button>
      </div>
    </section>
  )
}

function Stat({ value, label, tone }) {
  return (
    <div className={`fx-cv-stat${tone ? ` fx-cv-stat--${tone}` : ''}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

// Outlines and textures are only for drawing; the server gets the pipeline shape.
function withoutDrawingData(scan) {
  return { ...scan, pieces: scan.pieces.map(({ texture, ...piece }) => piece) }
}
