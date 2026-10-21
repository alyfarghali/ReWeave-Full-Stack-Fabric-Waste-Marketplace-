// Demo entry points on the factory start screen: a continuous 1,000-piece live
// scan, or the real vision pipeline run on a bundled sample table photo.
import { useState } from 'react'
import samplePhotoUrl from './sample-table.jpg'
import './demo.css'

export default function DemoLauncher({ onLiveScan, onSamplePhoto }) {
  const [loading, setLoading] = useState(false)

  async function scanSamplePhoto() {
    setLoading(true)
    try {
      const blob = await (await fetch(samplePhotoUrl)).blob()
      onSamplePhoto(new File([blob], 'sample-table.jpg', { type: 'image/jpeg' }))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="demo-launcher">
      <button type="button" className="fx-btn" onClick={onLiveScan}>
        Live scan 1,000 pieces
      </button>
      <button type="button" className="fx-btn" onClick={scanSamplePhoto} disabled={loading}>
        {loading ? 'Loading photo…' : 'Scan sample photo'}
      </button>
      <p className="demo-launcher-note">No camera needed. Scanned lots are listed on the marketplace.</p>
    </div>
  )
}
