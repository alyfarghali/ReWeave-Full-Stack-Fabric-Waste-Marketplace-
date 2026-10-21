// The pack list: annotated sorting plan, scan summary, and one box per sort bin.
import { useEffect, useRef } from 'react'
import { capitalize, formatWeightKg } from '../../shared/formatters.js'
import { RetakePanel } from './CaptureStages.jsx'
import DestinationAnalysis from './DestinationAnalysis.jsx'
import { IconCheck, IconChevron, IconExpand, IconSearch } from './icons.jsx'
import { readableOn } from './scanResults.js'

export default function PlanStage({
  result,
  groups,
  previewUrl,
  showOriginal,
  onShowOriginal,
  onZoom,
  packed,
  onTogglePacked,
  expandedAnalysis,
  onToggleAnalysis,
  onFinish,
  onPick,
}) {
  const annotated = result.annotated_image_data_url

  return (
    <section className="fx-stage fx-plan">
      <div className="fx-intro">
        <span className="fx-eyebrow">Pack list · Reweave Vision Engine</span>
        <h1 className="fx-title">Sort into boxes</h1>
        <p className="fx-lead fx-lead--muted">
          Factories sort scraps manually. Reweave does it in seconds.
        </p>
      </div>

      {groups.length === 0 ? (
        <RetakePanel
          icon={<IconSearch />}
          title="No fabric groups found"
          text="Spread the pieces out more clearly and retake the table from above."
          onPick={onPick}
        />
      ) : (
        <>
          <div className="fx-image-wrap">
            <button
              type="button"
              className="fx-frame fx-frame--plan"
              onClick={() => annotated && !showOriginal && onZoom()}
            >
              {showOriginal ? (
                <img src={previewUrl} alt="Original photo" />
              ) : annotated ? (
                <img src={annotated} alt="Annotated sorting plan" />
              ) : (
                <BoundingBoxFallback result={result} previewUrl={previewUrl} />
              )}
              {annotated && !showOriginal && (
                <span className="fx-zoom-hint">
                  <IconExpand />
                  View larger
                </span>
              )}
            </button>
            {annotated && (
              <div className="fx-image-toggle">
                <button
                  type="button"
                  className={`fx-image-toggle-btn${!showOriginal ? ' is-active' : ''}`}
                  onClick={() => onShowOriginal(false)}
                >
                  Annotated
                </button>
                <button
                  type="button"
                  className={`fx-image-toggle-btn${showOriginal ? ' is-active' : ''}`}
                  onClick={() => onShowOriginal(true)}
                >
                  Original
                </button>
              </div>
            )}
          </div>

          <CvSummary result={result} />

          <div className="fx-progress" aria-label="Packing progress">
            <div className="fx-progress-copy">
              <span className="fx-progress-label">Boxes packed</span>
              <strong>{packed.size} of {groups.length}</strong>
            </div>
            <div className="fx-progress-bar">
              <div
                className="fx-progress-fill"
                style={{ width: `${(packed.size / groups.length) * 100}%` }}
              />
            </div>
          </div>

          <div className="fx-section-heading">
            <h2>Pack manifest</h2>
          </div>

          <div className="fx-manifest">
            {groups.map((group, i) => {
              const key = group.sort_group_id || group.color_name
              const letter = group.sort_group_id || String.fromCharCode(65 + i)
              const isPacked = packed.has(key)
              const isAnalysisOpen = expandedAnalysis.has(key)
              const chip = group.outline_color || group.color_hex
              const count = group.piece_count
              return (
                <div key={key} className="fx-box-wrap" style={{ animationDelay: `${i * 0.08}s` }}>
                  <button
                    type="button"
                    className={`fx-box ${isPacked ? 'is-packed' : ''}`}
                    onClick={() => onTogglePacked(key)}
                  >
                    <span className="fx-box-chip" style={{ background: chip, color: readableOn(chip) }}>
                      {letter}
                    </span>
                    <span className="fx-box-info">
                      <span className="fx-box-code">Box {letter}</span>
                      <span className="fx-box-name">
                        {capitalize(group.color_name)}
                        {group.fabric_type_guess ? ` - ${group.fabric_type_guess}` : ''}
                      </span>
                      <span className="fx-box-data">
                        {count} {count === 1 ? 'piece' : 'pieces'}
                        {group.total_weight_label ? ` - ${group.total_weight_label}` : ''}
                      </span>
                    </span>
                    <span className="fx-box-check" aria-hidden="true">
                      <IconCheck />
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`fx-analysis-toggle ${isAnalysisOpen ? 'is-open' : ''}`}
                    onClick={() => onToggleAnalysis(key)}
                  >
                    <IconChevron />
                    AI destination analysis
                  </button>
                  {isAnalysisOpen && <DestinationAnalysis group={group} />}
                </div>
              )
            })}
          </div>

          <div className="fx-actions fx-actions--sticky">
            <button type="button" className="fx-btn fx-btn--primary" onClick={onFinish}>
              Finish Batch
            </button>
          </div>
        </>
      )}
    </section>
  )
}

// Used only if the backend returned no rendered plan image: draws each piece's
// bounding box over the worker's own photo, scaled to the displayed size.
function BoundingBoxFallback({ result, previewUrl }) {
  const imgRef = useRef(null)
  const canvasRef = useRef(null)

  useEffect(() => {
    const img = imgRef.current
    const canvas = canvasRef.current
    if (!img || !canvas) return

    function draw() {
      canvas.width = img.clientWidth
      canvas.height = img.clientHeight
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      const scaleX = canvas.width / result.image_width
      const scaleY = canvas.height / result.image_height
      result.pieces.forEach((piece) => {
        const [x, y, w, h] = piece.bbox
        ctx.strokeStyle = piece.outline_color || piece.color_hex
        ctx.lineWidth = 3
        ctx.strokeRect(x * scaleX, y * scaleY, w * scaleX, h * scaleY)
      })
    }

    if (img.complete) draw()
    else img.onload = draw
  }, [result])

  return (
    <span className="fx-fallback">
      <img ref={imgRef} src={previewUrl} alt="Your scrap pile" />
      <canvas ref={canvasRef} className="fx-fallback-canvas" />
    </span>
  )
}

function CvSummary({ result }) {
  const groups = result.groups || []
  const pieces = result.pieces || []
  const weightKg = groups.reduce((s, g) => s + (Number(g.estimated_weight_g) || 0), 0) / 1000
  const carbonKg = (weightKg * 2.1).toFixed(1)
  const waterL = Math.round(weightKg * 2700)

  return (
    <div className="fx-cv-summary">
      <div className="fx-cv-summary-head">
        <span className="fx-cv-badge">Reweave Vision Engine</span>
        {result.segmentation_method && <span className="fx-cv-method">{result.segmentation_method}</span>}
      </div>
      <div className="fx-cv-stats">
        <div className="fx-cv-stat">
          <strong>{pieces.length}</strong>
          <span>pieces detected</span>
        </div>
        <div className="fx-cv-stat">
          <strong>{groups.length}</strong>
          <span>material groups</span>
        </div>
        {weightKg > 0 && (
          <>
            <div className="fx-cv-stat">
              <strong>{formatWeightKg(weightKg)}</strong>
              <span>est. weight</span>
            </div>
            <div className="fx-cv-stat fx-cv-stat--green">
              <strong>{carbonKg} kg CO₂</strong>
              <span>diverted from landfill</span>
            </div>
            <div className="fx-cv-stat fx-cv-stat--blue">
              <strong>{waterL.toLocaleString()} L</strong>
              <span>water saved</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
