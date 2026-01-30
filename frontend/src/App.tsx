import React, { useState, useRef, useEffect } from 'react'
import { chatApi, type ChatResponse } from './api/client'
import embed from 'vega-embed'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sql?: string | null
  assumptions?: string[]
  followUpQuestions?: string[]
  chart?: { vega_lite_spec: Record<string, unknown> }
  metadata?: {
    row_count: number
    runtime_ms: number
  }
}

// Vega-Lite Chart Component
function VegaChart({ spec, messageId }: { spec: Record<string, unknown>; messageId: string }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current && spec && Object.keys(spec).length > 0) {
      embed(containerRef.current, spec as any, {
        actions: false,
        renderer: 'svg',
        width: 500,
        height: 300,
      }).catch((err) => {
        console.error('Vega embed error:', err)
      })
    }
  }, [spec, messageId])

  if (!spec || Object.keys(spec).length === 0) {
    return null
  }

  return (
    <div style={styles.chartContainer}>
      <div ref={containerRef} />
    </div>
  )
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())
  const [expandedSql, setExpandedSql] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response: ChatResponse = await chatApi(sessionId, userMessage.content)
      
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer,
        sql: response.sql,
        assumptions: response.assumptions,
        followUpQuestions: response.follow_up_questions,
        chart: response.chart,
        metadata: response.metadata,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFollowUpClick = (question: string) => {
    setInput(question)
  }

  const toggleSqlPanel = (messageId: string) => {
    setExpandedSql(expandedSql === messageId ? null : messageId)
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🧬 Pharma Analyst Bot</h1>
        <p style={styles.subtitle}>Ask questions about pharmaceutical sales data</p>
      </header>

      <main style={styles.chatContainer}>
        <div style={styles.messagesContainer}>
          {messages.length === 0 && (
            <div style={styles.welcomeMessage}>
              <h2>Welcome! 👋</h2>
              <p>Try asking questions like:</p>
              <ul style={styles.exampleList}>
                <li onClick={() => setInput('What are the top products by revenue?')}>
                  "What are the top products by revenue?"
                </li>
                <li onClick={() => setInput('Show me revenue by territory')}>
                  "Show me revenue by territory"
                </li>
                <li onClick={() => setInput('Show sales data')}>
                  "Show sales data"
                </li>
              </ul>
            </div>
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              style={{
                ...styles.messageWrapper,
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div
                style={{
                  ...styles.message,
                  ...(message.role === 'user' ? styles.userMessage : styles.assistantMessage),
                }}
              >
                <p style={styles.messageContent}>{message.content}</p>

                {message.metadata && (
                  <div style={styles.metadata}>
                    <span>📊 {message.metadata.row_count} rows</span>
                    <span>⏱️ {message.metadata.runtime_ms}ms</span>
                  </div>
                )}

                {message.sql && (
                  <div style={styles.sqlSection}>
                    <button
                      style={styles.sqlToggle}
                      onClick={() => toggleSqlPanel(message.id)}
                    >
                      {expandedSql === message.id ? '▼ Hide SQL' : '▶ Show SQL'}
                    </button>
                    {expandedSql === message.id && (
                      <pre style={styles.sqlCode}>{message.sql}</pre>
                    )}
                  </div>
                )}

                {message.chart && message.chart.vega_lite_spec && Object.keys(message.chart.vega_lite_spec).length > 0 && (
                  <VegaChart spec={message.chart.vega_lite_spec} messageId={message.id} />
                )}

                {message.assumptions && message.assumptions.length > 0 && (
                  <div style={styles.assumptions}>
                    <strong>Assumptions:</strong>
                    <ul>
                      {message.assumptions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {message.followUpQuestions && message.followUpQuestions.length > 0 && (
                  <div style={styles.followUps}>
                    <strong>Follow-up questions:</strong>
                    <div style={styles.followUpButtons}>
                      {message.followUpQuestions.map((q, i) => (
                        <button
                          key={i}
                          style={styles.followUpButton}
                          onClick={() => handleFollowUpClick(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div style={styles.messageWrapper}>
              <div style={{ ...styles.message, ...styles.assistantMessage }}>
                <p style={styles.loadingText}>Thinking...</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form onSubmit={handleSubmit} style={styles.inputForm}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about pharma sales..."
            style={styles.input}
            disabled={isLoading}
          />
          <button type="submit" style={styles.submitButton} disabled={isLoading}>
            Send
          </button>
        </form>
      </main>
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#f5f7fa',
  },
  header: {
    backgroundColor: '#1a73e8',
    color: 'white',
    padding: '20px',
    textAlign: 'center',
  },
  title: {
    margin: 0,
    fontSize: '24px',
  },
  subtitle: {
    margin: '8px 0 0',
    fontSize: '14px',
    opacity: 0.9,
  },
  chatContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    maxWidth: '900px',
    width: '100%',
    margin: '0 auto',
    padding: '20px',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    marginBottom: '20px',
  },
  welcomeMessage: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#555',
  },
  exampleList: {
    listStyle: 'none',
    padding: 0,
    marginTop: '20px',
  },
  messageWrapper: {
    display: 'flex',
    marginBottom: '16px',
  },
  message: {
    maxWidth: '80%',
    padding: '12px 16px',
    borderRadius: '12px',
    boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
  },
  userMessage: {
    backgroundColor: '#1a73e8',
    color: 'white',
    borderBottomRightRadius: '4px',
  },
  assistantMessage: {
    backgroundColor: 'white',
    color: '#333',
    borderBottomLeftRadius: '4px',
  },
  messageContent: {
    margin: 0,
    lineHeight: 1.5,
  },
  metadata: {
    display: 'flex',
    gap: '16px',
    marginTop: '8px',
    fontSize: '12px',
    color: '#666',
  },
  sqlSection: {
    marginTop: '12px',
  },
  sqlToggle: {
    background: 'none',
    border: 'none',
    color: '#1a73e8',
    cursor: 'pointer',
    padding: '4px 0',
    fontSize: '13px',
  },
  sqlCode: {
    backgroundColor: '#f5f5f5',
    padding: '12px',
    borderRadius: '6px',
    overflow: 'auto',
    fontSize: '12px',
    marginTop: '8px',
    border: '1px solid #e0e0e0',
  },
  chartContainer: {
    marginTop: '16px',
    padding: '12px',
    backgroundColor: '#fafafa',
    borderRadius: '8px',
    border: '1px solid #e0e0e0',
    overflow: 'auto',
  },
  assumptions: {
    marginTop: '12px',
    fontSize: '13px',
    color: '#666',
  },
  followUps: {
    marginTop: '12px',
  },
  followUpButtons: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '8px',
  },
  followUpButton: {
    background: '#e8f0fe',
    border: '1px solid #1a73e8',
    color: '#1a73e8',
    padding: '8px 12px',
    borderRadius: '20px',
    cursor: 'pointer',
    fontSize: '13px',
    textAlign: 'left',
  },
  inputForm: {
    display: 'flex',
    gap: '12px',
    backgroundColor: 'white',
    padding: '16px',
    borderRadius: '12px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    fontSize: '16px',
    outline: 'none',
  },
  submitButton: {
    padding: '12px 24px',
    backgroundColor: '#1a73e8',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    cursor: 'pointer',
  },
  loadingText: {
    margin: 0,
    fontStyle: 'italic',
    color: '#666',
  },
}

export default App
