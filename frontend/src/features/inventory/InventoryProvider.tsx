import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { ApiError } from '../../api/client'
import type { InventoryDto, InventoryItemDto } from '../../models/types'
import { formatLocalDate } from '../../logic/date'
import { useDevice } from '../device/DeviceProvider'

type InventoryStatus = 'loading' | 'success' | 'error'

interface InventoryContextValue {
  inventory: InventoryDto | null
  lastSuccessfulInventory: InventoryDto | null
  status: InventoryStatus
  errorMessage: string | null
  today: string
  refreshInventory: () => Promise<void>
  replaceInventory: (inventory: InventoryDto) => void
  updateInventoryItem: (item: InventoryItemDto) => Promise<void>
  deleteInventoryItem: (itemId: string) => Promise<void>
}

const InventoryContext = createContext<InventoryContextValue | null>(null)

export function InventoryProvider({ children }: PropsWithChildren) {
  const { apiClient } = useDevice()
  const [inventory, setInventory] = useState<InventoryDto | null>(null)
  const [lastSuccessfulInventory, setLastSuccessfulInventory] =
    useState<InventoryDto | null>(null)
  const [status, setStatus] = useState<InventoryStatus>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const today = useMemo(() => formatLocalDate(new Date()), [])

  const replaceInventory = useCallback((nextInventory: InventoryDto) => {
    setInventory(nextInventory)
    setLastSuccessfulInventory(nextInventory)
    setStatus('success')
    setErrorMessage(null)
  }, [])

  const refreshInventory = useCallback(async () => {
    setStatus('loading')
    setErrorMessage(null)

    try {
      const nextInventory = await apiClient.get<InventoryDto>(
        `/api/inventory?today=${encodeURIComponent(today)}`,
      )
      replaceInventory(nextInventory)
    } catch (error) {
      setStatus('error')
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : '냉장고를 불러오지 못했어요. 다시 시도해 주세요.',
      )
      // 실패 시 마지막으로 성공한 재고를 표시 상태로 유지합니다.
      setInventory((current) => current)
    }
  }, [apiClient, replaceInventory, today])

  useEffect(() => {
    void refreshInventory()
  }, [refreshInventory])

  const updateInventoryItem = useCallback(
    async (item: InventoryItemDto) => {
      if (!lastSuccessfulInventory) {
        throw new ApiError(409, 'INVENTORY_NOT_LOADED', '냉장고를 다시 불러와 주세요.', true)
      }

      const nextInventory = await apiClient.put<InventoryDto>(
        `/api/inventory/items/${encodeURIComponent(item.id)}?today=${encodeURIComponent(today)}`,
        {
          expectedVersion: lastSuccessfulInventory.version,
          name: item.name,
          quantity: item.quantity,
          storageLocation: item.storageLocation,
          expirationDate: item.expirationDate,
          expirationEstimated: item.expirationEstimated,
        },
      )
      replaceInventory(nextInventory)
    },
    [apiClient, lastSuccessfulInventory, replaceInventory, today],
  )

  const deleteInventoryItem = useCallback(
    async (itemId: string) => {
      if (!lastSuccessfulInventory) {
        throw new ApiError(409, 'INVENTORY_NOT_LOADED', '냉장고를 다시 불러와 주세요.', true)
      }

      const query = new URLSearchParams({
        today,
        expectedVersion: String(lastSuccessfulInventory.version),
      })
      const nextInventory = await apiClient.delete<InventoryDto>(
        `/api/inventory/items/${encodeURIComponent(itemId)}?${query.toString()}`,
      )
      replaceInventory(nextInventory)
    },
    [apiClient, lastSuccessfulInventory, replaceInventory, today],
  )

  const value = useMemo<InventoryContextValue>(
    () => ({
      inventory,
      lastSuccessfulInventory,
      status,
      errorMessage,
      today,
      refreshInventory,
      replaceInventory,
      updateInventoryItem,
      deleteInventoryItem,
    }),
    [
      deleteInventoryItem,
      errorMessage,
      inventory,
      lastSuccessfulInventory,
      refreshInventory,
      replaceInventory,
      status,
      today,
      updateInventoryItem,
    ],
  )

  return <InventoryContext.Provider value={value}>{children}</InventoryContext.Provider>
}

export function useInventory(): InventoryContextValue {
  const context = useContext(InventoryContext)
  if (!context) {
    throw new Error('useInventory는 InventoryProvider 안에서 사용해야 합니다.')
  }
  return context
}
