import { describe, expect, it } from 'vitest'

import { ApiClient, ApiError } from './client'

const DEVICE_ID = '123e4567-e89b-42d3-a456-426614174000'

describe('ApiClient', () => {
  it('모든 요청에 기기 헤더를 자동으로 넣고 성공 envelope의 data를 반환한다', async () => {
    let receivedHeaders: Headers | undefined
    const client = new ApiClient('https://api.example.com', DEVICE_ID, async (_input, init) => {
      receivedHeaders = new Headers(init?.headers)
      return new Response(
        JSON.stringify({ data: { status: 'ok' }, requestId: 'request-1' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    })

    await expect(client.get<{ status: string }>('/api/health')).resolves.toEqual({ status: 'ok' })
    expect(receivedHeaders?.get('X-Device-Id')).toBe(DEVICE_ID)
  })

  it('서버 오류 envelope를 ApiError로 정규화한다', async () => {
    const client = new ApiClient('', DEVICE_ID, async () =>
      new Response(
        JSON.stringify({
          error: { code: 'LLM_TIMEOUT', message: '시간이 초과됐어요.', retryable: true },
          requestId: 'request-2',
        }),
        { status: 504, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    const error = await client.get('/api/example').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 504,
      code: 'LLM_TIMEOUT',
      retryable: true,
      requestId: 'request-2',
    })
  })

  it('네트워크 실패를 재시도 가능한 안전한 오류로 정규화한다', async () => {
    const client = new ApiClient('', DEVICE_ID, async () => {
      throw new TypeError('내부 네트워크 상세')
    })

    const error = await client.get('/api/example').catch((caught: unknown) => caught)

    expect(error).toMatchObject({
      status: 0,
      code: 'NETWORK_ERROR',
      retryable: true,
      message: '서버에 연결할 수 없어요. 다시 시도해 주세요.',
    })
  })
})
