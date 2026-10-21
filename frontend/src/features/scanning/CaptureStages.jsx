// The simple stages of the factory scan flow: start, capture, processing,
// error, and the listed summary. The pack-list stage lives in PlanStage.jsx.
import { IconAlert, IconCamera, IconCheck, IconDot, IconImage, IconSpinner } from './icons.jsx'
import { PIPELINE_STEPS, readableOn } from './scanResults.js'

const PHOTO_TYPES = 'image/*,.heic,.heif'

export function StartStage({ onStart, children }) {
  return (
    <section className="fx-stage fx-start">
      <div className="fx-start-sheet">
        <div className="fx-start-content">
          <div className="fx-start-head">
            <span className="fx-eyebrow">Factory station</span>
            <h1 className="fx-title">Start a table scan</h1>
            <p className="fx-lead">
              Take one clear photo of the work table. The next screen will turn it into boxes to
              pack, then mark the finished batch as listed.
            </p>
          </div>

          <div className="fx-table-guide" aria-hidden="true">
            <div className="fx-table-surface">
              <span className="fx-scrap fx-scrap--one" />
              <span className="fx-scrap fx-scrap--two" />
              <span className="fx-scrap fx-scrap--three" />
              <span className="fx-scrap fx-scrap--four" />
            </div>
            <span className="fx-camera-line" />
          </div>

          <div className="fx-start-checklist">
            <div className="fx-check-row">
              <IconCheck />
              <span>Keep a small gap between pieces</span>
            </div>
            <div className="fx-check-row">
              <IconCheck />
              <span>Fit the whole table in the photo</span>
            </div>
            <div className="fx-check-row">
              <IconCheck />
              <span>Do not move scraps until the pack list appears</span>
            </div>
          </div>
        </div>

        <div className="fx-actions fx-actions--start">
          <button type="button" className="fx-btn fx-btn--primary" onClick={onStart}>
            <IconCamera />
            Scan table
          </button>
        </div>
        {children}
      </div>
    </section>
  )
}

export function CaptureStage({ onPick }) {
  return (
    <section className="fx-stage fx-home">
      <div className="fx-intro">
        <span className="fx-eyebrow">Factory scan</span>
        <h1 className="fx-title">Scan scraps</h1>
      </div>

      <div className="fx-frame fx-frame--idle" aria-label="No photo selected">
        <div className="fx-frame-hint">
          <IconCamera />
          <strong>Take a table photo</strong>
          <span>The app will group the scraps into boxes.</span>
        </div>
      </div>

      <div className="fx-actions">
        <label className="fx-btn fx-btn--primary">
          <IconCamera />
          Take photo
          <input type="file" accept={PHOTO_TYPES} capture="environment" onChange={onPick} />
        </label>
        <label className="fx-btn-text">
          <IconImage />
          Upload photo
          <input type="file" accept={PHOTO_TYPES} onChange={onPick} />
        </label>
      </div>
    </section>
  )
}

export function ProcessingStage({ previewUrl, activeStep }) {
  return (
    <section className="fx-stage fx-processing">
      <div className="fx-intro">
        <span className="fx-eyebrow">Reweave Vision Engine</span>
        <h1 className="fx-title">Analyzing scraps</h1>
      </div>

      {previewUrl && (
        <div className="fx-frame fx-frame--scan">
          <img src={previewUrl} alt="Your scrap pile" />
        </div>
      )}

      <div className="fx-pipeline">
        {PIPELINE_STEPS.map((label, i) => {
          const done = i < activeStep
          const active = i === activeStep
          return (
            <div
              key={i}
              className={`fx-pipeline-step${done ? ' is-done' : ''}${active ? ' is-active' : ''}`}
            >
              <span className="fx-pipeline-icon">
                {done ? <IconCheck /> : active ? <IconSpinner /> : <IconDot />}
              </span>
              <span className="fx-pipeline-label">{label}</span>
            </div>
          )
        })}
      </div>

      <div className="fx-bar-indeterminate">
        <span />
      </div>
    </section>
  )
}

export function ErrorStage({ error, onPick }) {
  return (
    <section className="fx-stage">
      <RetakePanel
        icon={<IconAlert />}
        title="Photo needs another try"
        text={error || 'Use brighter light, separate the scraps, and take the table straight on.'}
        onPick={onPick}
      />
    </section>
  )
}

export function RetakePanel({ icon, title, text, onPick }) {
  return (
    <div className="fx-panel">
      <div className="fx-panel-icon">{icon}</div>
      <h2 className="fx-panel-title">{title}</h2>
      <p className="fx-panel-text">{text}</p>
      <label className="fx-btn fx-btn--primary">
        <IconCamera />
        Retake photo
        <input type="file" accept={PHOTO_TYPES} capture="environment" onChange={onPick} />
      </label>
    </div>
  )
}

export function ListedStage({ summary, onScanAnother, onBack }) {
  return (
    <section className="fx-stage fx-listed">
      <div className="fx-listed-head">
        <div className="fx-listed-mark">
          <IconCheck />
        </div>
        <span className="fx-eyebrow">Listed just now</span>
        <h1 className="fx-title">Materials listed</h1>
        <p className="fx-lead">
          Created {summary.listings} {summary.listings === 1 ? 'listing' : 'listings'} from{' '}
          {summary.pieces} {summary.pieces === 1 ? 'piece' : 'pieces'} on this table.
        </p>
      </div>

      <div className="fx-listed-summary" aria-label="Created listing summary">
        <div>
          <span>Listings</span>
          <strong>{summary.listings}</strong>
        </div>
        <div>
          <span>Pieces</span>
          <strong>{summary.pieces}</strong>
        </div>
        <div>
          <span>Weight</span>
          <strong>{summary.weightLabel}</strong>
        </div>
      </div>

      <div className="fx-listed-table">
        <div className="fx-listed-table-head">
          <h2>Created lots</h2>
          <span>Buyer side</span>
        </div>
        <div className="fx-listed-rows">
          {summary.rows.map((row) => (
            <div className="fx-listed-row" key={row.key}>
              <span
                className="fx-listed-swatch"
                style={{ background: row.color, color: readableOn(row.color) }}
              >
                {row.letter}
              </span>
              <span className="fx-listed-info">
                <strong>{row.name}</strong>
                <span>
                  {row.pieces} {row.pieces === 1 ? 'piece' : 'pieces'}
                  {row.weightLabel ? ` - ${row.weightLabel}` : ''}
                </span>
              </span>
              <span className="fx-listed-state">Listed</span>
            </div>
          ))}
        </div>
      </div>

      <div className="fx-actions fx-actions--sticky">
        <button type="button" className="fx-btn fx-btn--primary" onClick={onScanAnother}>
          <IconCamera />
          Scan another table
        </button>
        <button type="button" className="fx-btn-text" onClick={onBack}>
          Back to pack list
        </button>
      </div>
    </section>
  )
}
