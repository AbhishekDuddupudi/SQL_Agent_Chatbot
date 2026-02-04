/**
 * API client for Pharma Analyst Bot
 */

// Use relative URL for proxy, or absolute URL if VITE_API_URL is set
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export interface ChatRequest {
  session_id?: string
  message: string
}

export interface ChatMetadata {
  row_count: number
  runtime_ms: number
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

export interface HealthResponse {
  status: string
}

/**
 * SSE Event Types
 */
export type StreamEventType = 'status' | 'token' | 'complete' | 'error'

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
  | { type: 'status'; data: StreamStatusEvent }
  | { type: 'token'; data: StreamTokenEvent }
  | { type: 'complete'; data: StreamCompleteEvent }
  | { type: 'error'; data: StreamErrorEvent }

/**
 * Callbacks for streaming events
 */
export interface StreamCallbacks {
  onStatus?: (step: string, message: string) => void
  onToken?: (token: string) => void
  onComplete?: (response: ChatResponse) => void
  onError?: (error: string) => void
}

/**
 * Check API health status
 */
export async function healthCheck(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`)
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`)
  }
  
  return response.json()
}

/**
 * Send a chat message and get a response (non-streaming)
 */
export async function chatApi(
  sessionId: string,
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
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
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
  sessionId: string,
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
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
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

export default {
  healthCheck,
  chatApi,
  chatApiStream,
}
