import type { ApiErrorEnvelope, ApiSuccess } from '../models/types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean
  readonly requestId?: string

  constructor(
    status: number,
    code: string,
    message: string,
    retryable: boolean,
    requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.retryable = retryable
    this.requestId = requestId
  }
}

type FetchTransport = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

function isErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (!value || typeof value !== 'object') return false

  const candidate = value as Partial<ApiErrorEnvelope>
  return (
    typeof candidate.requestId === 'string' &&
    typeof candidate.error?.code === 'string' &&
    typeof candidate.error.message === 'string' &&
    typeof candidate.error.retryable === 'boolean'
  )
}

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly deviceId: string,
    private readonly transport: FetchTransport = fetch,
  ) {}

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    headers.set('X-Device-Id', this.deviceId)

    if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }

    let response: Response
    try {
      response = await this.transport(`${this.baseUrl}${path}`, { ...init, headers })
    } catch {
      throw new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없어요. 다시 시도해 주세요.', true)
    }

    const payload: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      if (isErrorEnvelope(payload)) {
        throw new ApiError(
          response.status,
          payload.error.code,
          payload.error.message,
          payload.error.retryable,
          payload.requestId,
        )
      }
      throw new ApiError(
        response.status,
        'UNEXPECTED_RESPONSE',
        '요청을 처리하지 못했어요. 다시 시도해 주세요.',
        response.status >= 500,
      )
    }

    const envelope = payload as Partial<ApiSuccess<T>> | null
    if (!envelope || !('data' in envelope) || typeof envelope.requestId !== 'string') {
      throw new ApiError(
        response.status,
        'INVALID_RESPONSE',
        '서버 응답을 확인할 수 없어요. 다시 시도해 주세요.',
        true,
      )
    }

    return envelope.data as T
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path)
  }

  post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: this.serializeBody(body) })
  }

  put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body: this.serializeBody(body) })
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }

  private serializeBody(body: unknown): BodyInit {
    return body instanceof FormData ? body : JSON.stringify(body)
  }
}

export function createApiClient(deviceId: string): ApiClient {
  return new ApiClient(import.meta.env.VITE_API_BASE_URL ?? '', deviceId)
}
