import { request } from '../../shared/api.js'

export { getLots } from '../marketplace/api.js'

export function getAdminMetrics() {
  return request('/admin/metrics')
}

export function delistLot(lotId) {
  return request(`/lots/${lotId}/delist`, { method: 'PATCH' })
}

export function relistLot(lotId) {
  return request(`/lots/${lotId}/relist`, { method: 'PATCH' })
}

export function deleteLot(lotId) {
  return request(`/lots/${lotId}`, { method: 'DELETE' })
}
