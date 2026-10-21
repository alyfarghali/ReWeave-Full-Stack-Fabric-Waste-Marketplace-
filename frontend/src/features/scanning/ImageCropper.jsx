import { useEffect, useRef, useState, useCallback } from 'react'
import {
  decodeToDrawable,
  cropToJpegFile,
  isBackendReadableImage,
  prepareWholePhotoForVision,
} from './imagePrep.js'

// Touch-friendly crop step shown right after a photo is taken on the factory
// page. The worker drags a box around just the fabrics + the ArUco marker; on
// confirm we hand back a JPEG crop that goes straight into the existing vision
// pipeline. Decoding here also normalizes HEIC photos from iPhones.

const MIN_BOX = 44 // smallest crop side, in display pixels
const CORNERS = [
  { id: 'nw', cx: 0, cy: 0 },
  { id: 'ne', cx: 1, cy: 0 },
  { id: 'sw', cx: 0, cy: 1 },
  { id: 'se', cx: 1, cy: 1 },
]

function clampBox(box, dw, dh) {
  let w = Math.min(Math.max(box.w, MIN_BOX), dw)
  let h = Math.min(Math.max(box.h, MIN_BOX), dh)
  let x = Math.min(Math.max(box.x, 0), dw - w)
  let y = Math.min(Math.max(box.y, 0), dh - h)
  return { x, y, w, h }
}

export default function ImageCropper({ file, onConfirm, onCancel }) {
  const wrapRef = useRef(null)
  const canvasRef = useRef(null)
  const drawableRef = useRef(null)
  const srcRef = useRef({ w: 0, h: 0 })
  const dragRef = useRef(null)

  const [status, setStatus] = useState('loading') // loading | ready | error
  const [display, setDisplay] = useState(null) // { w, h } display pixels
  const [box, setBox] = useState(null) // crop rect in display pixels
  const [busy, setBusy] = useState(false)

  // Fit the decoded image into the available width/height and seed the crop box.
  const layout = useCallback(() => {
    const wrap = wrapRef.current
    const { w: sw, h: sh } = srcRef.current
    if (!wrap || !sw || !sh) return
    const availW = wrap.clientWidth || sw
    const availH = Math.min(window.innerHeight * 0.56, 560)
    let dw = availW
    let dh = (dw * sh) / sw
    if (dh > availH) {
      dh = availH
      dw = (dh * sw) / sh
    }
    dw = Math.round(dw)
    dh = Math.round(dh)
    setDisplay({ w: dw, h: dh })
    setBox((prev) =>
      prev
        ? clampBox(prev, dw, dh)
        : {
            x: Math.round(dw * 0.05),
            y: Math.round(dh * 0.05),
            w: Math.round(dw * 0.9),
            h: Math.round(dh * 0.9),
          },
    )
  }, [])

  // Decode the picked file (handles HEIC) once per file.
  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setBox(null)
    setDisplay(null)
    decodeToDrawable(file)
      .then(({ drawable, width, height }) => {
        if (cancelled) return
        drawableRef.current = drawable
        srcRef.current = { w: width, h: height }
        layout()
        setStatus('ready')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [file, layout])

  useEffect(() => {
    function onResize() {
      layout()
    }
    window.addEventListener('resize', onResize)
    window.addEventListener('orientationchange', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('orientationchange', onResize)
    }
  }, [layout])

  // Paint the decoded image into the preview canvas whenever the fit changes.
  useEffect(() => {
    if (status !== 'ready' || !display || !canvasRef.current || !drawableRef.current) return
    const canvas = canvasRef.current
    canvas.width = display.w
    canvas.height = display.h
    const ctx = canvas.getContext('2d')
    ctx.imageSmoothingQuality = 'high'
    ctx.clearRect(0, 0, display.w, display.h)
    ctx.drawImage(drawableRef.current, 0, 0, display.w, display.h)
  }, [status, display])

  // Pointer drag handling for moving the box and resizing from a corner.
  useEffect(() => {
    function onMove(e) {
      const drag = dragRef.current
      if (!drag || !display) return
      e.preventDefault()
      const dx = e.clientX - drag.startX
      const dy = e.clientY - drag.startY
      const s = drag.startBox

      if (drag.mode === 'move') {
        setBox(clampBox({ ...s, x: s.x + dx, y: s.y + dy }, display.w, display.h))
        return
      }

      // resize from a corner: the opposite corner stays pinned
      let left = s.x
      let top = s.y
      let right = s.x + s.w
      let bottom = s.y + s.h
      if (drag.corner.includes('w')) left = s.x + dx
      if (drag.corner.includes('e')) right = s.x + s.w + dx
      if (drag.corner.includes('n')) top = s.y + dy
      if (drag.corner.includes('s')) bottom = s.y + s.h + dy
      const x = Math.min(left, right)
      const y = Math.min(top, bottom)
      const w = Math.abs(right - left)
      const h = Math.abs(bottom - top)
      setBox(clampBox({ x, y, w, h }, display.w, display.h))
    }

    function onUp() {
      dragRef.current = null
    }

    window.addEventListener('pointermove', onMove, { passive: false })
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [display])

  function startMove(e) {
    if (!box) return
    e.preventDefault()
    dragRef.current = { mode: 'move', startX: e.clientX, startY: e.clientY, startBox: box }
  }

  function startResize(e, corner) {
    if (!box) return
    e.preventDefault()
    e.stopPropagation()
    dragRef.current = { mode: 'resize', corner, startX: e.clientX, startY: e.clientY, startBox: box }
  }

  async function confirm(useWhole = false) {
    if (busy) return
    const { w: sw, h: sh } = srcRef.current
    let rect
    if (useWhole || !box || !display) {
      rect = { x: 0, y: 0, width: sw, height: sh }
    } else {
      const scale = sw / display.w
      rect = { x: box.x * scale, y: box.y * scale, width: box.w * scale, height: box.h * scale }
    }
    setBusy(true)
    try {
      if (useWhole) {
        const fullPhoto = await prepareWholePhotoForVision(file)
        onConfirm(fullPhoto, { wasCropped: false, source: 'whole-photo' })
        return
      }
      if (!drawableRef.current) return
      const cropped = await cropToJpegFile(drawableRef.current, rect, { name: 'scan-crop.jpg' })
      onConfirm(cropped, { wasCropped: true, source: 'crop' })
    } catch {
      setBusy(false)
      setStatus('error')
    }
  }

  function useOriginalFile() {
    if (busy || !isBackendReadableImage(file)) return
    setBusy(true)
    onConfirm(file, { wasCropped: false, source: 'original-file' })
  }

  return (
    <section className="fx-stage fx-crop">
      <div className="fx-intro">
        <span className="fx-eyebrow">Frame the scan</span>
        <h1 className="fx-title">Crop to fabrics + marker</h1>
        <p className="fx-lead fx-lead--muted">
          Drag the box so it covers only the scraps and the marker. This keeps the table edges and
          clutter out of the scan.
        </p>
      </div>

      <div className="fx-crop-frame" ref={wrapRef}>
        {status === 'loading' && <div className="fx-crop-status">Loading photo…</div>}
        {status === 'error' && (
          <div className="fx-crop-status">
            <strong>Could not preview that photo.</strong>
            <span>Try the full-resolution original, or retake if the camera saved an unsupported format.</span>
            {isBackendReadableImage(file) && (
              <button type="button" className="fx-btn-text" onClick={useOriginalFile} disabled={busy}>
                Use original photo
              </button>
            )}
          </div>
        )}
        {status === 'ready' && display && (
          <div className="fx-crop-stage" style={{ width: display.w, height: display.h }}>
            <canvas ref={canvasRef} className="fx-crop-canvas" />
            {box && (
              <>
                <div
                  className="fx-crop-shade"
                  style={{
                    clipPath: `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${box.x}px ${box.y}px, ${box.x}px ${box.y + box.h}px, ${box.x + box.w}px ${box.y + box.h}px, ${box.x + box.w}px ${box.y}px, ${box.x}px ${box.y}px)`,
                  }}
                />
                <div
                  className="fx-crop-box"
                  style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
                  onPointerDown={startMove}
                >
                  <span className="fx-crop-grid" aria-hidden="true" />
                  {CORNERS.map((c) => (
                    <span
                      key={c.id}
                      className={`fx-crop-handle fx-crop-handle--${c.id}`}
                      onPointerDown={(e) => startResize(e, c.id)}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <div className="fx-actions fx-actions--sticky">
        <button
          type="button"
          className="fx-btn fx-btn--primary"
          onClick={() => confirm(false)}
          disabled={status !== 'ready' || busy}
        >
          {busy ? 'Preparing…' : 'Use this crop'}
        </button>
        <div className="fx-crop-secondary">
          <button type="button" className="fx-btn-text" onClick={() => confirm(true)} disabled={status !== 'ready' || busy}>
            Use whole photo
          </button>
          <button type="button" className="fx-btn-text" onClick={onCancel} disabled={busy}>
            Retake
          </button>
        </div>
      </div>
    </section>
  )
}
