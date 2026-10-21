import { postJson } from '../../shared/api.js'

export function sendChat(messages) {
  return postJson('/chat', { messages })
}
