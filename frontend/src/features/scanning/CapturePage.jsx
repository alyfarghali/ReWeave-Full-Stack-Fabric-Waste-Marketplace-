// Factory worker scanning flow: photo -> crop -> processing -> pack list -> listed.
// Renders the /api/vision/detect response (backend/app/scanning/schemas.py:
// DetectResponse / Piece / SortGroup) and lists every bin as a lot.
import { useEffect, useRef, useState } from 'react'
import { saveMyLocation } from '../auth/api.js'
import DemoLauncher from '../demo/DemoLauncher.jsx'
import LiveScanDemo from '../demo/LiveScanDemo.jsx'
import { detectScrap, listScan, warmupVision } from './api.js'
import { CaptureStage, ErrorStage, ListedStage, ProcessingStage, StartStage } from './CaptureStages.jsx'
import { FactoryHeader } from './FactoryHeader.jsx'
import { IconClose } from './icons.jsx'
import ImageCropper from './ImageCropper.jsx'
import { prepareWholePhotoForVision } from './imagePrep.js'
import PlanStage from './PlanStage.jsx'
import { PIPELINE_STEPS, buildListingSummary, friendlyError, sortByBin } from './scanResults.js'

const VISION_SERVER_PREF_KEY = 'reweave_use_continuous_vision_server'

function savedContinuousServerPref() {
  // Default ON: the always-warm Replicate deployment returns in a few seconds.
  // Leaving it off sends phones down the public model's 60-90s cold start, which
  // is the slow, flaky path that surfaces as "error, please try again".
  try {
    const stored = localStorage.getItem(VISION_SERVER_PREF_KEY)
    return stored === null ? true : stored === 'true'
  } catch {
    return true
  }
}

function toggled(set, key) {
  const next = new Set(set)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  return next
}

export default function CapturePage() {
  const [stage, setStage] = useState('start') // start | capture | crop | processing | plan | listed | error | demo
  const [pickedFile, setPickedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [packed, setPacked] = useState(() => new Set())
  const [expandedAnalysis, setExpandedAnalysis] = useState(() => new Set())
  const [finishedBatch, setFinishedBatch] = useState(null)
  const [activeStep, setActiveStep] = useState(0)
  const [showOriginal, setShowOriginal] = useState(false)
  const [zoomOpen, setZoomOpen] = useState(false)
  const [useContinuousServer, setUseContinuousServer] = useState(savedContinuousServerPref)

  const autoSavedRef = useRef(false)
  // Where this factory station is. Captured once from the browser so every lot
  // scanned here is pinned to the worker's real location on the buyer map.
  const originRef = useRef(null)

  // Boot the SAM container as soon as the worker lands on the factory page so the
  // first scan hits a warm model instead of a cold start.
  useEffect(() => {
    warmupVision()
  }, [])

  useEffect(() => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude, longitude } = pos.coords
        originRef.current = { origin_lat: latitude, origin_lng: longitude }
        saveMyLocation(latitude, longitude).catch(() => {})
      },
      () => {},
      { timeout: 8000 }
    )
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(VISION_SERVER_PREF_KEY, useContinuousServer ? 'true' : 'false')
    } catch {
      // Preference just won't persist.
    }
  }, [useContinuousServer])

  // Advance pipeline steps while waiting on the detect call. Cap at the
  // second-to-last step so the final step only completes when results arrive.
  useEffect(() => {
    if (stage !== 'processing') return
    setActiveStep(0)
    const timer = setInterval(() => {
      setActiveStep(i => Math.min(i + 1, PIPELINE_STEPS.length - 2))
    }, 2200)
    return () => clearInterval(timer)
  }, [stage])

  // A photo was picked (camera or library). Hand it to the crop step first --
  // the worker frames just the fabrics + marker before we run detection. This
  // also lets us decode HEIC photos so the pipeline always gets a clean JPEG.
  function pickPhoto(e) {
    const selected = e.target.files && e.target.files[0]
    e.target.value = '' // allow re-picking the same file later
    if (!selected) return
    setPickedFile(selected)
    setError(null)
    setStage('crop')
  }

  function showPreview(file) {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(URL.createObjectURL(file))
  }

  function showResult(res) {
    setResult(res)
    autoSaveLots(res)
    setStage('plan')
  }

  // Run the vision pipeline on the photo the worker confirmed. If a crop fails
  // on mobile, retry once with the full-resolution original before asking the
  // worker to retake it.
  async function runDetect(file, meta = {}) {
    if (!file) return
    autoSavedRef.current = false
    setError(null)
    setResult(null)
    setPacked(new Set())
    setFinishedBatch(null)
    setZoomOpen(false)
    showPreview(file)
    setStage('processing')

    try {
      showResult(await detectScrap(file, { useDeployment: useContinuousServer }))
    } catch (err) {
      if (meta.wasCropped && pickedFile) {
        try {
          const fullPhoto = await prepareWholePhotoForVision(pickedFile)
          showPreview(fullPhoto)
          showResult(await detectScrap(fullPhoto, { useDeployment: useContinuousServer }))
          return
        } catch {
          // Show the original crop error below; it is usually the most useful
          // message for the worker.
        }
      }
      setError(friendlyError(err))
      setStage('error')
    }
  }

  // Silently turn each detected sort bin into a marketplace lot. Invisible to
  // the worker -- it just makes scanned materials available to buyers right away.
  // The server records the scan run and lists every bin in one transaction.
  function autoSaveLots(res) {
    if (autoSavedRef.current) return
    autoSavedRef.current = true
    if (!res?.groups?.length) return
    listScan(res, originRef.current || {})
      .catch((err) => console.warn('Scan could not be listed:', err))
  }

  function reset(nextStage = 'start') {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    autoSavedRef.current = false
    setPreviewUrl(null)
    setResult(null)
    setError(null)
    setPacked(new Set())
    setFinishedBatch(null)
    setShowOriginal(false)
    setZoomOpen(false)
    setStage(nextStage)
  }

  const groups = result ? [...result.groups].sort(sortByBin) : []
  const annotated = result && result.annotated_image_data_url

  let body = null
  if (stage === 'start') {
    body = (
      <StartStage onStart={() => setStage('capture')}>
        <DemoLauncher onLiveScan={() => setStage('demo')} onSamplePhoto={(file) => runDetect(file)} />
      </StartStage>
    )
  } else if (stage === 'demo') {
    body = <LiveScanDemo origin={originRef.current} onExit={() => setStage('start')} />
  } else if (stage === 'capture') {
    body = <CaptureStage onPick={pickPhoto} />
  } else if (stage === 'crop') {
    body = pickedFile
      ? <ImageCropper file={pickedFile} onConfirm={runDetect} onCancel={() => setStage('capture')} />
      : <section className="fx-stage" />
  } else if (stage === 'processing') {
    body = <ProcessingStage previewUrl={previewUrl} activeStep={activeStep} />
  } else if (stage === 'error') {
    body = <ErrorStage error={error} onPick={pickPhoto} />
  } else if (stage === 'plan') {
    body = (
      <PlanStage
        result={result}
        groups={groups}
        previewUrl={previewUrl}
        showOriginal={showOriginal}
        onShowOriginal={setShowOriginal}
        onZoom={() => setZoomOpen(true)}
        packed={packed}
        onTogglePacked={(key) => setPacked((prev) => toggled(prev, key))}
        expandedAnalysis={expandedAnalysis}
        onToggleAnalysis={(key) => setExpandedAnalysis((prev) => toggled(prev, key))}
        onFinish={() => {
          setFinishedBatch(buildListingSummary(result))
          setStage('listed')
        }}
        onPick={pickPhoto}
      />
    )
  } else if (stage === 'listed') {
    body = (
      <ListedStage
        summary={finishedBatch || buildListingSummary(result)}
        onScanAnother={() => reset('capture')}
        onBack={() => setStage('plan')}
      />
    )
  }

  return (
    <div className="factory-app">
      <FactoryHeader
        useContinuousServer={useContinuousServer}
        onUseContinuousServerChange={setUseContinuousServer}
      />
      <main className={`fx-main ${stage === 'start' ? 'fx-main--dashboard' : ''}`}>{body}</main>

      {zoomOpen && annotated && (
        <div className="fx-zoom" onClick={() => setZoomOpen(false)}>
          <button type="button" className="fx-zoom-close" aria-label="Close">
            <IconClose />
          </button>
          <img src={annotated} alt="Annotated sorting plan" />
        </div>
      )}
    </div>
  )
}
