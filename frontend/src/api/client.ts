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
 * Send a chat message and get a response
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

export default {
  healthCheck,
  chatApi,
}
