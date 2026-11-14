import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import App from './App'

const { getMock, apiClientMock } = vi.hoisted(() => {
  const get = vi.fn()
  return { getMock: get, apiClientMock: { get } }
})

vi.mock('../features/device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: apiClientMock, deviceId: 'test-device' }),
}))

describe('App', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    getMock.mockReset()
    getMock.mockResolvedValue({ items: [], version: 0 })
  })

  it('기본 경로에 냉장고 화면과 단일 열 반응형 콘텐츠 영역을 표시한다', async () => {
    render(<App />)

    expect(screen.getByText('나만의 냉장고')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '냉장고' }).closest('section')).toHaveClass(
      'w-full',
      'md:max-w-[480px]',
    )
    await waitFor(() => expect(getMock).toHaveBeenCalledOnce())
  })

  it.each([
    ['/register', '재료 등록'],
    ['/recipe', '한 끼 추천'],
    ['/meal-plan', '3일 식단'],
  ])('%s 경로를 렌더링한다', async (path, heading) => {
    window.history.replaceState({}, '', path)
    render(<App />)

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    await waitFor(() => expect(getMock).toHaveBeenCalledOnce())
  })
})
