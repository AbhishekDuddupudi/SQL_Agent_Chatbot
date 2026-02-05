import React, { useState, useRef, useEffect, useCallback } from 'react'
import { 
  chatApiStream, 
  getCurrentUser, 
  logout, 
  getSessions,
  getSessionMessages,
  type ChatResponse, 
  type User,
  type ChatSession,
  type ChatMessage 
} from './api/client'
import embed from 'vega-embed'
import LoginPage from './LoginPage'

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
  isStreaming?: boolean
  statusMessage?: string
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

    embed(containerRef.current, spec as Parameters<typeof embed>[1], {
      actions: { export: true, source: false, compiled: false, editor: false } as any,
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

  // If still streaming, show status
  if (message.isStreaming) {
    return (
      <div style={{ ...styles.message, ...styles.assistantMessage }}>
        {message.statusMessage && (
          <div style={styles.statusLine}>
            <span style={styles.statusDot}>●</span>
            <span>{message.statusMessage}</span>
          </div>
        )}
        {message.content && (
          <p style={styles.messageContent}>
            {message.content}
            <span style={styles.cursor}>▌</span>
          </p>
        )}
        {!message.content && !message.statusMessage && (
          <p style={styles.loadingText}>Connecting...</p>
        )}
      </div>
    )
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
  // Auth state
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  
  // Session state
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | undefined>(undefined)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  
  // Chat state
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [expandedSql, setExpandedSql] = useState<string | null>(null)
  const [expandedChart, setExpandedChart] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Load sessions when user logs in
  const loadSessions = useCallback(async () => {
    try {
      const userSessions = await getSessions()
      setSessions(userSessions)
    } catch (err) {
      console.error('Failed to load sessions:', err)
    }
  }, [])

  // Load messages for a session
  const loadSessionMessages = useCallback(async (sessionId: number) => {
    try {
      const chatMessages = await getSessionMessages(sessionId)
      // Convert ChatMessage to Message format
      const convertedMessages: Message[] = chatMessages.map((msg: ChatMessage) => ({
        id: String(msg.id),
        role: msg.role,
        content: msg.content,
        sql: msg.sql_query,
      }))
      setMessages(convertedMessages)
    } catch (err) {
      console.error('Failed to load messages:', err)
      setMessages([])
    }
  }, [])

  // Check for existing session on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const currentUser = await getCurrentUser()
        setUser(currentUser)
        if (currentUser) {
          await loadSessions()
        }
      } catch (err) {
        console.error('Auth check failed:', err)
      } finally {
        setAuthLoading(false)
      }
    }
    checkAuth()
  }, [loadSessions])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleLogout = async () => {
    try {
      await logout()
      setUser(null)
      setMessages([])
      setSessions([])
      setActiveSessionId(undefined)
    } catch (err) {
      console.error('Logout failed:', err)
    }
  }

  // Start new chat
  const handleNewChat = () => {
    setActiveSessionId(undefined)
    setMessages([])
    setExpandedSql(null)
    setExpandedChart(null)
  }

  // Switch to a session
  const handleSelectSession = async (sessionId: number) => {
    setActiveSessionId(sessionId)
    setExpandedSql(null)
    setExpandedChart(null)
    await loadSessionMessages(sessionId)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
    }

    const assistantMessageId = crypto.randomUUID()
    
    // Create initial streaming message
    const streamingMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      statusMessage: 'Connecting...',
    }

    setMessages((prev) => [...prev, userMessage, streamingMessage])
    setInput('')
    setIsLoading(true)

    try {
      await chatApiStream(
        activeSessionId,
        userMessage.content,
        {
          onSession: (newSessionId) => {
            // Got session ID from server (for new sessions)
            setActiveSessionId(newSessionId)
            // Reload sessions to get new session in sidebar
            loadSessions()
          },
          onStatus: (_step, message) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, statusMessage: message }
                  : m
              )
            )
          },
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: m.content + token, statusMessage: undefined }
                  : m
              )
            )
          },
          onComplete: (response: ChatResponse) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: response.answer,
                      sql: response.sql,
                      assumptions: response.assumptions,
                      followUpQuestions: response.follow_up_questions,
                      chart: response.chart,
                      metadata: response.metadata,
                      isStreaming: false,
                      statusMessage: undefined,
                    }
                  : m
              )
            )
            // Reload sessions to get updated title
            loadSessions()
          },
          onError: (error) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? {
                      ...m,
                      content: `Error: ${error}`,
                      isStreaming: false,
                      statusMessage: undefined,
                    }
                  : m
              )
            )
          },
        }
      )
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      
      // If not authenticated, log out and redirect to login
      if (errorMessage === 'Not authenticated') {
        setUser(null)
        setMessages([])
        setSessions([])
        setActiveSessionId(undefined)
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem('session_id')
        }
        return
      }
      
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessageId
            ? {
                ...m,
                content: `Error: ${errorMessage}`,
                isStreaming: false,
                statusMessage: undefined,
              }
            : m
        )
      )
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

  // Handle successful login
  const handleLoginSuccess = useCallback(async (loggedInUser: User) => {
    setUser(loggedInUser)
    await loadSessions()
  }, [loadSessions])

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}>Loading...</div>
      </div>
    )
  }

  // Show login page if not authenticated
  if (!user) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />
  }

  return (
    <div style={styles.appWrapper}>
      {/* Sidebar */}
      <aside style={{
        ...styles.sidebar,
        width: sidebarOpen ? '260px' : '0',
        padding: sidebarOpen ? '16px' : '0',
      }}>
        <button 
          onClick={handleNewChat} 
          style={styles.newChatButton}
        >
          + New Chat
        </button>
        
        <div style={styles.sessionList}>
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => handleSelectSession(session.id)}
              style={{
                ...styles.sessionItem,
                backgroundColor: activeSessionId === session.id ? '#e8f0fe' : 'transparent',
                borderLeft: activeSessionId === session.id ? '3px solid #1a73e8' : '3px solid transparent',
              }}
            >
              <span style={styles.sessionTitle}>
                {session.title || 'New conversation'}
              </span>
              <span style={styles.sessionDate}>
                {new Date(session.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
          {sessions.length === 0 && (
            <p style={styles.noSessions}>No conversations yet</p>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div style={styles.mainContent}>
        <header style={styles.header}>
          <div style={styles.headerContent}>
            <div style={styles.headerLeft}>
              <button 
                onClick={() => setSidebarOpen(!sidebarOpen)} 
                style={styles.menuButton}
              >
                ☰
              </button>
              <div>
                <h1 style={styles.title}>🧬 Pharma Analyst Bot</h1>
                <p style={styles.subtitle}>Ask questions about pharmaceutical sales data</p>
              </div>
            </div>
            <div style={styles.userInfo}>
              <span style={styles.userName}>👤 {user.display_name}</span>
              <button onClick={handleLogout} style={styles.logoutButton}>
                Logout
              </button>
            </div>
          </div>
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
              {/* Status shown via streaming message */}
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
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  appWrapper: {
    minHeight: '100vh',
    display: 'flex',
    backgroundColor: '#f5f7fa',
  },
  sidebar: {
    backgroundColor: '#ffffff',
    borderRight: '1px solid #e5e7eb',
    display: 'flex',
    flexDirection: 'column',
    transition: 'width 0.2s ease, padding 0.2s ease',
    overflow: 'hidden',
    flexShrink: 0,
  },
  newChatButton: {
    padding: '12px 16px',
    backgroundColor: '#1a73e8',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 500,
    cursor: 'pointer',
    marginBottom: '16px',
    whiteSpace: 'nowrap',
  },
  sessionList: {
    flex: 1,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  sessionItem: {
    padding: '12px',
    borderRadius: '6px',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    transition: 'background-color 0.15s ease',
  },
  sessionTitle: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#333',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  sessionDate: {
    fontSize: '11px',
    color: '#888',
  },
  noSessions: {
    fontSize: '13px',
    color: '#888',
    textAlign: 'center',
    padding: '20px 0',
  },
  mainContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#f5f7fa',
  },
  loadingContainer: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f5f7fa',
  },
  loadingSpinner: {
    fontSize: '18px',
    color: '#666',
  },
  header: {
    backgroundColor: '#1a73e8',
    color: 'white',
    padding: '16px 20px',
  },
  headerContent: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  menuButton: {
    background: 'none',
    border: 'none',
    color: 'white',
    fontSize: '20px',
    cursor: 'pointer',
    padding: '8px',
    borderRadius: '4px',
  },
  title: {
    margin: 0,
    fontSize: '24px',
  },
  subtitle: {
    margin: '4px 0 0',
    fontSize: '14px',
    opacity: 0.9,
  },
  userInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  userName: {
    fontSize: '14px',
    opacity: 0.9,
  },
  logoutButton: {
    padding: '8px 16px',
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    color: 'white',
    border: '1px solid rgba(255, 255, 255, 0.3)',
    borderRadius: '6px',
    fontSize: '13px',
    cursor: 'pointer',
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
  statusLine: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
    padding: '8px 12px',
    backgroundColor: '#f0f9ff',
    borderRadius: '6px',
    fontSize: '13px',
    color: '#0369a1',
  },
  statusDot: {
    color: '#0ea5e9',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  cursor: {
    animation: 'blink 1s step-end infinite',
    color: '#1a73e8',
  },
}

export default App
