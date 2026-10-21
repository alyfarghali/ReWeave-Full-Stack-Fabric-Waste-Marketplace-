import { postJson, request } from '../../shared/api.js'

export function detectScrap(file, options = {}) {
  const formData = new FormData()
  formData.append('image', file)
  if (options.useDeployment !== undefined) {
    formData.append('use_deployment', options.useDeployment ? 'true' : 'false')
  }
  return request('/vision/detect', { method: 'POST', body: formData })
}

// Fire-and-forget: boot the SAM container ahead of the first real scan so the
// worker never pays the cold-start delay. Safe to call repeatedly.
export function warmupVision() {
  return request('/vision/warmup', { method: 'POST' }).catch(() => {})
}

// Record a scan and list each of its sort bins as a lot, in one transaction.
export function listScan(scan, { origin_lat = null, origin_lng = null } = {}) {
  return postJson('/lots/from-scan', { scan, origin_lat, origin_lng })
}

export function analyzeDestinations(payload) {
  return postJson('/destinations/analyze', payload)
}

// Wipes all scanned lots and scan runs; logins and buyer profiles are kept.
export function resetInventory() {
  return request('/admin/reset-demo', { method: 'POST' })
}
