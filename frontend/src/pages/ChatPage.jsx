import { useState, useRef, useEffect } from 'react'

const EXAMPLE_QUESTIONS = [
  'What\'s the best honeymoon package in Goa?',
  'Tell me about trekking options in Himachal Pradesh',
  'What visa do I need for Singapore?',
  'Suggest a 7-day family trip to Kerala',
  'What luxury hotels are in Dubai?',
  'Recommend a spiritual tour in Rajasthan',
]

const SOURCE_COLORS = {
  package:   'source-type-package',
  hotel:     'source-type-hotel',
  itinerary: 'source-type-itinerary',
  visa:      'source-type-visa',
}

function TypingIndicator() {
  return (
    <div className="message message-assistant">
      <div className="typing-indicator">
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-bubble">{msg.content}</div>

      {!isUser && msg.sources?.length > 0 && (
        <div className="sources-panel">
          <div className="sources-title">📚 Sources used ({msg.sources.length})</div>
          {msg.sources.map((s, i) => (
            <div key={i} className="source-item">
              <span className={`source-type-dot ${SOURCE_COLORS[s.result_type] || 'source-type-package'}`} />
              <span>{s.title}</span>
            </div>
          ))}
          {msg.model && (
            <div style={{ marginTop: 8, fontSize: '0.72rem', color: 'var(--color-text-dim)' }}>
              Model: {msg.model}
            </div>
          )}
        </div>
      )}

      {!isUser && msg.error && (
        <div className="sources-panel" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
          <div style={{ color: '#f87171', fontSize: '0.8rem' }}>{msg.error}</div>
        </div>
      )}
    </div>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async (text = input.trim()) => {
    if (!text || loading) return
    setInput('')

    const userMsg = { role: 'user', content: text, id: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, n_context: 10 }),
      })
      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `Server error ${res.status}`)
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        model: data.model,
        id: Date.now() + 1,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'I encountered an issue. Please check that the API server is running and your GEMINI_API_KEY is configured.',
        error: err.message,
        id: Date.now() + 1,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleExample = (q) => {
    setInput(q)
    sendMessage(q)
  }

  return (
    <div className="chat-page">
      <div className="chat-header">
        <h2>✨ AI Travel Assistant</h2>
        <p>
          Ask any travel question — powered by Gemini + your real travel data
        </p>
      </div>

      {/* Message window */}
      <div className="chat-window">
        {messages.length === 0 && (
          <div className="empty-state" style={{ padding: '20px 0' }}>
            <div className="empty-state-icon">🌍</div>
            <h3>Ask me anything about travel</h3>
            <p>
              I'll search real packages, hotels, and destinations to give you a grounded answer.
            </p>
            <div className="example-queries" style={{ marginTop: 20 }}>
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button key={i} className="example-chip" onClick={() => handleExample(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <Message key={msg.id} msg={msg} />
        ))}

        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <div className="chat-input-box">
          <textarea
            ref={inputRef}
            id="chat-input"
            className="chat-input"
            placeholder="Ask about packages, hotels, destinations, visa…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            id="chat-send-btn"
            className="chat-send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            {loading ? '…' : 'Send'}
          </button>
        </div>
        <p style={{ fontSize: '0.74rem', color: 'var(--color-text-dim)', marginTop: 8, textAlign: 'center' }}>
          Answers grounded in real travel data · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
