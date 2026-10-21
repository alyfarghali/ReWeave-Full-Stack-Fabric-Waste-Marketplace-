import { useState, useRef, useEffect } from 'react'
import { ReweaveLogo } from '../../shared/ReweaveMark.jsx'
import { sendChat } from './api.js'

const WELCOME = {
  role: 'assistant',
  content: "Hi! I'm Reweave Assistant 👋 I can help you navigate Reweave, explain how to create lots, find the right buyers, or answer questions about fabric recycling. What can I help you with?",
}

export default function ChatBot() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  async function send() {
    const text = input.trim()
    if (!text || loading) return

    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setLoading(true)

    try {
      const data = await sendChat(
        next.filter(m => m !== WELCOME).map(m => ({ role: m.role, content: m.content })),
      )
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }])
    } catch (err) {
      const content = err?.status === 503
        ? 'The assistant is not configured on this server yet.'
        : 'Sorry, something went wrong. Try again.'
      setMessages(prev => [...prev, { role: 'assistant', content }])
    } finally {
      setLoading(false)
    }
  }

  function onKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <>
      {/* Floating toggle button */}
      <button className="chat-toggle" onClick={() => setOpen(o => !o)} aria-label="Open chat">
        {open ? '✕' : 'AI'}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="chat-panel">
          <div className="chat-header">
            <div className="chat-header-info">
              <span className="chat-avatar" style={{ width: 24, height: 24, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <ReweaveLogo variant="mark" height={24} />
              </span>
              <div>
                <div className="chat-name">Reweave Assistant</div>
                <div className="chat-status">Online</div>
              </div>
            </div>
            <button className="chat-close" onClick={() => setOpen(false)}>✕</button>
          </div>

          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>
                {m.content}
              </div>
            ))}
            {loading && (
              <div className="chat-bubble assistant chat-typing">
                <span /><span /><span />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chat-input-row">
            <textarea
              className="chat-input"
              rows={1}
              placeholder="Ask me anything…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
            />
            <button className="chat-send" onClick={send} disabled={!input.trim() || loading}>
              ➤
            </button>
          </div>
        </div>
      )}
    </>
  )
}
