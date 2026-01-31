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

// Vega-Lite Chart Component with error handling
function VegaChart({ spec }: { spec: Record<string, unknown> }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!containerRef.current || !spec || Object.keys(spec).length === 0) {
      return
    }

    setError(null)
    
    // Clear previous chart
    containerRef.current.innerHTML = ''

    embed(containerRef.current, spec as any, {
      actions: { export: true, source: false, compiled: false, editor: false },
      renderer: 'svg',
    })
      .then(() => {
        console.log('Vega chart rendered successfully')
      })
      .catch((err) => {
        console.error('Vega embed error:', err)
        setError(`Failed to render chart: ${err.message}`)
      })

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [spec])

  if (error) {
    return (
      <div style={styles.chartError}>
        <span>⚠️ {error}</span>
      </div>
    )
  }

  return <div ref={containerRef} style={styles.vegaContainer} />
}

// Assistant Message Component with collapsible chart
function AssistantMessageCard({
  message,
  expandedSql,
  expandedChart,
  onToggleSql,
  onToggleChart,
  onFollowUpClick,
}: {
  message: Message
  expandedSql: boolean
  expandedChart: boolean
  onToggleSql: () => void
  onToggleChart: () => void
  onFollowUpClick: (question: string) => void
}) {
  const chartRef = useRef<HTMLDivElement>(null)

  const hasChart = message.chart?.vega_lite_spec && 
    Object.keys(message.chart.vega_lite_spec).length > 0

  const handleChartToggle = () => {
    const willExpand = !expandedChart
    onToggleChart()
    
    // Scroll to chart after expansion
    if (willExpand) {
      setTimeout(() => {
        chartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    }
  }

  return (
    <div style={{ ...styles.message, ...styles.assistantMessage }}>
      <p style={styles.messageContent}>{message.content}</p>

      {message.metadata && (
        <div style={styles.metadata}>
          <span>📊 {message.metadata.row_count} rows</span>
          <span>⏱️ {message.metadata.runtime_ms}ms</span>
        </div>
      )}

      {/* Action Buttons */}
      <div style={styles.actionButtons}>
        {message.sql && (
          <button style={styles.toggleButton} onClick={onToggleSql}>
            {expandedSql ? '▼ Hide SQL' : '▶ Show SQL'}
          </button>
        )}
        {hasChart && (
          <button 
            style={{ ...styles.toggleButton, ...styles.chartToggleButton }} 
            onClick={handleChartToggle}
          >
            {expandedChart ? '▼ Hide Chart' : '📈 Show Chart'}
          </button>
        )}
      </div>

      {/* Collapsible SQL Section */}
      {expandedSql && message.sql && (
        <div style={styles.sqlSection}>
          <pre style={styles.sqlCode}>{message.sql}</pre>
        </div>
      )}

      {/* Collapsible Chart Section */}
      {expandedChart && hasChart && (
        <div ref={chartRef} style={styles.chartSection}>
          <VegaChart spec={message.chart!.vega_lite_spec} />
        </div>
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
                onClick={() => onFollowUpClick(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())
  const [expandedSql, setExpandedSql] = useState<string | null>(null)
  const [expandedChart, setExpandedChart] = useState<string | null>(null)
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

  const toggleChartPanel = (messageId: string) => {
    setExpandedChart(expandedChart === messageId ? null : messageId)
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
              {message.role === 'user' ? (
                <div style={{ ...styles.message, ...styles.userMessage }}>
                  <p style={styles.messageContent}>{message.content}</p>
                </div>
              ) : (
                <AssistantMessageCard
                  message={message}
                  expandedSql={expandedSql === message.id}
                  expandedChart={expandedChart === message.id}
                  onToggleSql={() => toggleSqlPanel(message.id)}
                  onToggleChart={() => toggleChartPanel(message.id)}
                  onFollowUpClick={handleFollowUpClick}
                />
              )}
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
    paddingBottom: '8px',
    borderBottom: '1px solid #eee',
    fontSize: '12px',
    color: '#666',
  },
  actionButtons: {
    display: 'flex',
    gap: '8px',
    marginTop: '10px',
    flexWrap: 'wrap',
  },
  toggleButton: {
    background: 'none',
    border: '1px solid #ddd',
    borderRadius: '6px',
    color: '#1a73e8',
    cursor: 'pointer',
    padding: '6px 12px',
    fontSize: '13px',
    fontWeight: 500,
  },
  chartToggleButton: {
    backgroundColor: '#f0fdf4',
    borderColor: '#86efac',
    color: '#16a34a',
  },
  sqlSection: {
    marginTop: '12px',
  },
  sqlCode: {
    backgroundColor: '#1e293b',
    color: '#e2e8f0',
    padding: '12px',
    borderRadius: '8px',
    overflow: 'auto',
    fontSize: '12px',
    fontFamily: "'Fira Code', 'Monaco', 'Consolas', monospace",
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  chartSection: {
    marginTop: '12px',
    padding: '16px',
    backgroundColor: '#fafafa',
    borderRadius: '8px',
    border: '1px solid #e5e7eb',
  },
  vegaContainer: {
    width: '100%',
    display: 'flex',
    justifyContent: 'center',
    overflow: 'auto',
  },
  chartError: {
    padding: '12px',
    backgroundColor: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    color: '#dc2626',
    fontSize: '13px',
    textAlign: 'center',
  },
  assumptions: {
    marginTop: '12px',
    paddingTop: '12px',
    borderTop: '1px solid #eee',
    fontSize: '13px',
    color: '#666',
  },
  followUps: {
    marginTop: '12px',
    paddingTop: '12px',
    borderTop: '1px solid #eee',
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
