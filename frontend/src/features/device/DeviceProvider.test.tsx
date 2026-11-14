import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  DEVICE_ID_STORAGE_KEY,
  DeviceProvider,
  initializeDeviceId,
  isValidDeviceId,
} from './DeviceProvider'

const DEVICE_ID = '123e4567-e89b-42d3-a456-426614174000'

afterEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('기기 식별자 초기화', () => {
  it('저장된 UUID v4를 그대로 재사용한다', () => {
    window.localStorage.setItem(DEVICE_ID_STORAGE_KEY, DEVICE_ID)

    expect(initializeDeviceId(window.localStorage)).toBe(DEVICE_ID)
  })

  it('유효한 값이 없으면 UUID v4를 생성하고 저장값을 다시 확인한다', () => {
    const deviceId = initializeDeviceId(window.localStorage, () => DEVICE_ID)

    expect(deviceId).toBe(DEVICE_ID)
    expect(window.localStorage.getItem(DEVICE_ID_STORAGE_KEY)).toBe(DEVICE_ID)
    expect(isValidDeviceId(deviceId)).toBe(true)
  })

  it('localStorage 저장이 실패하면 자식 대신 차단 화면을 표시한다', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('저장 실패')
    })

    render(
      <DeviceProvider>
        <p>API 화면</p>
      </DeviceProvider>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('기기 식별자를 저장할 수 없어요')
    expect(screen.queryByText('API 화면')).not.toBeInTheDocument()
  })
})
