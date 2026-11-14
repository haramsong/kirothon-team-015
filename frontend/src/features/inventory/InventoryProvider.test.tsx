import { act, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { InventoryDto } from '../../models/types'
import { InventoryProvider, useInventory } from './InventoryProvider'

const { getMock, putMock, deleteMock, apiClientMock } = vi.hoisted(() => {
  const get = vi.fn()
  const put = vi.fn()
  const deleteRequest = vi.fn()
  return {
    getMock: get,
    putMock: put,
    deleteMock: deleteRequest,
    apiClientMock: { get, put, delete: deleteRequest },
  }
})

vi.mock('../device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: apiClientMock, deviceId: 'test-device' }),
}))

let latestContext: ReturnType<typeof useInventory> | null = null

function ContextProbe() {
  latestContext = useInventory()
  return (
    <div>
      <span data-testid="status">{latestContext.status}</span>
      <span data-testid="inventory">
        {latestContext.inventory?.items.map((item) => item.name).join(',') ?? '없음'}
      </span>
      <span data-testid="last-success">
        {latestContext.lastSuccessfulInventory?.items.map((item) => item.name).join(',') ??
          '없음'}
      </span>
    </div>
  )
}

const successfulInventory: InventoryDto = {
  version: 3,
  items: [
    {
      id: 'onion',
      name: '양파',
      quantity: 8,
      storageLocation: '실온',
      expirationDate: '2026-04-10',
      expirationEstimated: true,
    },
  ],
}

describe('InventoryProvider', () => {
  beforeEach(() => {
    latestContext = null
    getMock.mockReset()
    putMock.mockReset()
    deleteMock.mockReset()
  })

  it('성공한 조회 결과를 현재 및 마지막 성공 재고로 저장한다', async () => {
    getMock.mockResolvedValueOnce(successfulInventory)

    render(
      <InventoryProvider>
        <ContextProbe />
      </InventoryProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('success'))
    expect(screen.getByTestId('inventory')).toHaveTextContent('양파')
    expect(screen.getByTestId('last-success')).toHaveTextContent('양파')
    expect(getMock).toHaveBeenCalledWith(expect.stringMatching(/^\/api\/inventory\?today=\d{4}-\d{2}-\d{2}$/))
  })

  it('재조회 실패 시 마지막 성공 재고를 교체하지 않는다', async () => {
    getMock.mockResolvedValueOnce(successfulInventory)

    render(
      <InventoryProvider>
        <ContextProbe />
      </InventoryProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('success'))

    getMock.mockRejectedValueOnce(
      new ApiError(500, 'STORAGE_ERROR', '냉장고를 불러오지 못했어요.', true),
    )
    await act(async () => {
      await latestContext?.refreshInventory()
    })

    expect(screen.getByTestId('status')).toHaveTextContent('error')
    expect(screen.getByTestId('inventory')).toHaveTextContent('양파')
    expect(screen.getByTestId('last-success')).toHaveTextContent('양파')
  })

  it('품목 수정 성공 때만 최신 재고로 교체하고 version을 요청에 포함한다', async () => {
    getMock.mockResolvedValueOnce(successfulInventory)
    const updatedInventory = {
      ...successfulInventory,
      version: 4,
      items: [{ ...successfulInventory.items[0], name: '적양파', expirationEstimated: false }],
    }
    putMock.mockResolvedValueOnce(updatedInventory)

    render(
      <InventoryProvider>
        <ContextProbe />
      </InventoryProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('success'))

    await act(async () => {
      await latestContext?.updateInventoryItem(updatedInventory.items[0])
    })

    expect(putMock).toHaveBeenCalledWith(
      expect.stringMatching(/^\/api\/inventory\/items\/onion\?today=\d{4}-\d{2}-\d{2}$/),
      expect.objectContaining({ expectedVersion: 3, name: '적양파', expirationEstimated: false }),
    )
    expect(screen.getByTestId('inventory')).toHaveTextContent('적양파')
    expect(screen.getByTestId('last-success')).toHaveTextContent('적양파')
  })

  it('품목 삭제 실패 시 마지막 성공 재고를 유지하고 오류를 호출자에게 전달한다', async () => {
    getMock.mockResolvedValueOnce(successfulInventory)
    deleteMock.mockRejectedValueOnce(
      new ApiError(500, 'STORAGE_ERROR', '삭제에 실패했어요.', true),
    )

    render(
      <InventoryProvider>
        <ContextProbe />
      </InventoryProvider>,
    )
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('success'))

    await expect(latestContext?.deleteInventoryItem('onion')).rejects.toThrow('삭제에 실패했어요.')
    expect(deleteMock).toHaveBeenCalledWith(
      expect.stringMatching(
        /^\/api\/inventory\/items\/onion\?today=\d{4}-\d{2}-\d{2}&expectedVersion=3$/,
      ),
    )
    expect(screen.getByTestId('inventory')).toHaveTextContent('양파')
    expect(screen.getByTestId('last-success')).toHaveTextContent('양파')
  })
})
