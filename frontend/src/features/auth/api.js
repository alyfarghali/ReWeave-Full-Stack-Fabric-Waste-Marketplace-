import { postJson, request } from '../../shared/api.js'

export function login(email, password) {
  return postJson('/auth/login', { email, password })
}

export function getMe() {
  return request('/auth/me')
}

export function saveMyLocation(lat, lng) {
  return postJson('/auth/me/location', { lat, lng }, 'PUT')
}
