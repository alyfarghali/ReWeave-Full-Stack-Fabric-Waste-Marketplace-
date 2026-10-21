// Client-side image prep for the factory scan.
//
// Phones (especially iPhones) hand us HEIC/HEIF files that the FastAPI vision
// pipeline cannot decode (PIL / OpenCV only speak JPEG/PNG). Rather than touch
// the backend, we decode the photo in the browser, let the worker crop it, and
// re-encode the crop as a plain JPEG before it ever reaches /api/vision/detect.
// The detection pipeline stays exactly the same -- it just always receives a
// clean JPEG of the region the worker selected.

const BACKEND_READABLE_TYPES = new Set(['image/jpeg', 'image/jpg', 'image/png', 'image/webp'])
const BACKEND_READABLE_EXTENSIONS = /\.(jpe?g|png|webp)$/i
const MAX_CANVAS_PIXELS = 14_000_000

export function isBackendReadableImage(file) {
  if (!file) return false
  const type = String(file.type || '').toLowerCase()
  if (BACKEND_READABLE_TYPES.has(type)) return true
  return BACKEND_READABLE_EXTENSIONS.test(file.name || '')
}

// Decode any picked file into something <canvas> can draw. The <img> path is
// intentionally first: mobile browsers apply the camera photo orientation there
// most consistently. createImageBitmap remains as a fallback for formats the
// browser can decode but will not load into an image element.
export async function decodeToDrawable(file) {
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error('Could not decode image'))
      el.src = url
    })
    if (!img.naturalWidth || !img.naturalHeight) {
      throw new Error('Image has no dimensions')
    }
    return { drawable: img, width: img.naturalWidth, height: img.naturalHeight, objectUrl: url }
  } catch {
    URL.revokeObjectURL(url)
  }

  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
      if (bitmap && bitmap.width && bitmap.height) {
        return { drawable: bitmap, width: bitmap.width, height: bitmap.height }
      }
    } catch {
      try {
        const bitmap = await createImageBitmap(file)
        if (bitmap && bitmap.width && bitmap.height) {
          return { drawable: bitmap, width: bitmap.width, height: bitmap.height }
        }
      } catch {
        // fall through to the final error below
      }
    }
  }

  throw new Error('Could not decode image')
}

// Crop a source-pixel rectangle out of the decoded drawable and return it as a
// JPEG File. Keep substantially more source detail than the preview canvas;
// the backend can downsample after it receives a clean high-quality crop.
export function cropToJpegFile(drawable, rect, { maxDim = 4096, quality = 0.97, name = 'scan.jpg' } = {}) {
  const sourceW = drawable.naturalWidth || drawable.videoWidth || drawable.width
  const sourceH = drawable.naturalHeight || drawable.videoHeight || drawable.height
  const sx = clamp(Math.round(rect.x), 0, Math.max(0, sourceW - 1))
  const sy = clamp(Math.round(rect.y), 0, Math.max(0, sourceH - 1))
  const srcW = clamp(Math.round(rect.width), 1, Math.max(1, sourceW - sx))
  const srcH = clamp(Math.round(rect.height), 1, Math.max(1, sourceH - sy))
  const maxDimScale = Math.max(srcW, srcH) > maxDim ? maxDim / Math.max(srcW, srcH) : 1
  const pixelScale = srcW * srcH > MAX_CANVAS_PIXELS ? Math.sqrt(MAX_CANVAS_PIXELS / (srcW * srcH)) : 1
  const scale = Math.min(maxDimScale, pixelScale)
  const outW = Math.max(1, Math.round(srcW * scale))
  const outH = Math.max(1, Math.round(srcH * scale))

  const canvas = document.createElement('canvas')
  canvas.width = outW
  canvas.height = outH
  const ctx = canvas.getContext('2d')
  ctx.imageSmoothingEnabled = scale !== 1
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(drawable, sx, sy, srcW, srcH, 0, 0, outW, outH)

  return new Promise((resolve, reject) => {
    if (canvas.toBlob) {
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('Could not encode crop'))
            return
          }
          resolve(fileFromBlob(blob, name, 'image/jpeg'))
        },
        'image/jpeg',
        quality,
      )
      return
    }

    try {
      const dataUrl = canvas.toDataURL('image/jpeg', quality)
      resolve(fileFromBlob(dataUrlToBlob(dataUrl), name, 'image/jpeg'))
    } catch (err) {
      reject(err)
    }
  })
}

export async function prepareWholePhotoForVision(file) {
  if (isBackendReadableImage(file)) return file
  const { drawable, width, height } = await decodeToDrawable(file)
  return cropToJpegFile(drawable, { x: 0, y: 0, width, height }, { name: 'scan-full.jpg' })
}

function fileFromBlob(blob, name, type) {
  try {
    return new File([blob], name, { type })
  } catch {
    return new Blob([blob], { type })
  }
}

function dataUrlToBlob(dataUrl) {
  const [meta, data] = dataUrl.split(',')
  const mime = /data:([^;]+)/.exec(meta)?.[1] || 'image/jpeg'
  const binary = atob(data)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}
