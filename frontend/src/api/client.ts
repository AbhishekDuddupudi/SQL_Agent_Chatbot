/**
 * API client for Pharma Analyst Bot
 */

// Use relative URL for proxy, or absolute URL if VITE_API_URL is set
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

function getSessionHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {}
  const sessionId = window.localStorage.getItem('session_id')
  return sessionId ? { 'X-Session-Id': sessionId } : {}
}

// ============ Auth Types ============

export interface User {
  id: number
  email: string
  display_name: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  success: boolean
  user: User | null
  session_id?: string | null
  message: string
}

// ============ Chat Types ============

export interface ChatRequest {
  session_id?: number  // Database session ID (integer)
  message: string
}

export interface ChatMetadata {
  row_count: number
  runtime_ms: number
  session_id?: number  // Return session_id in metadata
}

export interface ChartSpec {
  vega_lite_spec: Record<string, unknown>
}

export interface ChatResponse {
  answer: string
  sql: string | null
  assumptions: string[]
  chart: ChartSpec
  follow_up_questions: string[]
  metadata: ChatMetadata
}

// ============ Session Types ============

export interface ChatSession {
  id: number
  user_id: number
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant'
  content: string
  sql_query: string | null
  created_at: string
}

export interface HealthResponse {
  status: string
}

/**
 * SSE Event Types
 */
export type StreamEventType = 'session' | 'status' | 'token' | 'complete' | 'error'

export interface StreamSessionEvent {
  request_id: string
  timestamp: number
  session_id: number
}

export interface StreamStatusEvent {
  request_id: string
  timestamp: number
  step: string
  message: string
}

export interface StreamTokenEvent {
  request_id: string
  timestamp: number
  token: string
}

export interface StreamCompleteEvent {
  request_id: string
  timestamp: number
  answer: string
  sql: string | null
  assumptions: string[]
  chart: ChartSpec
  follow_up_questions: string[]
  metadata: ChatMetadata
}

export interface StreamErrorEvent {
  request_id: string
  timestamp: number
  error: string
}

export type StreamEvent = 
  | { type: 'session'; data: StreamSessionEvent }
  | { type: 'status'; data: StreamStatusEvent }
  | { type: 'token'; data: StreamTokenEvent }
  | { type: 'complete'; data: StreamCompleteEvent }
  | { type: 'error'; data: StreamErrorEvent }

/**
 * Callbacks for streaming events
 */
export interface StreamCallbacks {
  onSession?: (sessionId: number) => void
  onStatus?: (step: string, message: string) => void
  onToken?: (token: string) => void
  onComplete?: (response: ChatResponse) => void
  onError?: (error: string) => void
}

/**
 * Check API health status
 */
export async function healthCheck(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    credentials: 'include',
  })
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`)
  }
  
  return response.json()
}

// ============ Auth API ============

/**
 * Login with email and password
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include', // Important: include cookies
    body: JSON.stringify({ email, password }),
  })

  if (!response.ok) {
    throw new Error(`Login failed: ${response.statusText}`)
  }

  const data = await response.json()
  if (data?.session_id && typeof window !== 'undefined') {
    window.localStorage.setItem('session_id', data.session_id)
  }
  return data
}

/**
 * Logout current user
 */
export async function logout(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      ...getSessionHeader(),
    },
  })

  if (!response.ok) {
    throw new Error(`Logout failed: ${response.statusText}`)
  }
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem('session_id')
  }
}

/**
 * Get current logged-in user
 */
export async function getCurrentUser(): Promise<User | null> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    credentials: 'include',
    headers: {
      ...getSessionHeader(),
    },
  })

  if (!response.ok) {
    return null
  }

  const data = await response.json()
  return data
}

// ============ Chat API ============

/**
 * Send a chat message and get a response (non-streaming)
 */
export async function chatApi(
  sessionId: number | undefined,
  message: string
): Promise<ChatResponse> {
  const request: ChatRequest = {
    session_id: sessionId,
    message: message,
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getSessionHeader(),
    },
    credentials: 'include', // Important: include cookies for auth
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Not authenticated')
    }
    const errorText = await response.text()
    throw new Error(`Chat request failed: ${response.statusText} - ${errorText}`)
  }

  return response.json()
}

/**
 * Parse SSE event from raw text
 */
function parseSSEEvent(eventText: string): StreamEvent | null {
  const lines = eventText.trim().split('\n')
  let eventType: string | null = null
  let data: string | null = null

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      eventType = line.substring(7).trim()
    } else if (line.startsWith('data: ')) {
      data = line.substring(6)
    }
  }

  if (!eventType || !data) {
    return null
  }

  try {
    const parsedData = JSON.parse(data)
    return { type: eventType as StreamEventType, data: parsedData } as StreamEvent
  } catch (e) {
    console.error('Failed to parse SSE data:', e)
    return null
  }
}

/**
 * Send a chat message with streaming response (SSE)
 */
export async function chatApiStream(
  sessionId: number | undefined,
  message: string,
  callbacks: StreamCallbacks
): Promise<void> {
  const request: ChatRequest = {
    session_id: sessionId,
    message: message,
  }

  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...getSessionHeader(),
    },
    credentials: 'include', // Important: include cookies for auth
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Not authenticated')
    }
    const errorText = await response.text()
    throw new Error(`Chat stream request failed: ${response.statusText} - ${errorText}`)
  }

  if (!response.body) {
    throw new Error('Response body is null')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      
      // Process complete events (separated by double newline)
      const events = buffer.split('\n\n')
      buffer = events.pop() || '' // Keep incomplete event in buffer

      for (const eventText of events) {
        if (!eventText.trim()) continue
        
        const event = parseSSEEvent(eventText)
        if (!event) continue

        switch (event.type) {
          case 'session':
            callbacks.onSession?.(event.data.session_id)
            break
          case 'status':
            callbacks.onStatus?.(event.data.step, event.data.message)
            break
          case 'token':
            callbacks.onToken?.(event.data.token)
            break
          case 'complete':
            callbacks.onComplete?.({
              answer: event.data.answer,
              sql: event.data.sql,
              assumptions: event.data.assumptions,
              chart: event.data.chart,
              follow_up_questions: event.data.follow_up_questions,
              metadata: event.data.metadata,
            })
            break
          case 'error':
            callbacks.onError?.(event.data.error)
            break
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// ============ Session API ============

/**
 * Get all chat sessions for the current user
 */
export async function getSessions(): Promise<ChatSession[]> {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    credentials: 'include',
    headers: {
      ...getSessionHeader(),
    },
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Not authenticated')
    }
    throw new Error(`Failed to fetch sessions: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Create a new chat session
 */
export async function createSession(): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getSessionHeader(),
    },
    credentials: 'include',
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Not authenticated')
    }
    throw new Error(`Failed to create session: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Get messages for a specific session
 */
export async function getSessionMessages(sessionId: number): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`, {
    credentials: 'include',
    headers: {
      ...getSessionHeader(),
    },
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Not authenticated')
    }
    if (response.status === 404) {
      throw new Error('Session not found')
    }
    throw new Error(`Failed to fetch messages: ${response.statusText}`)
  }

  return response.json()
}

export default {
  healthCheck,
  login,
  logout,
  getCurrentUser,
  chatApi,
  chatApiStream,
  getSessions,
  createSession,
  getSessionMessages,
}
