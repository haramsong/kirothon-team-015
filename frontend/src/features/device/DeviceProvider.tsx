import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useState,
} from 'react'

import { ApiClient, createApiClient } from '../../api/client'

export const DEVICE_ID_STORAGE_KEY = 'my-own-fridge-device-id'

const UUID_V4_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

interface DeviceContextValue {
  deviceId: string
  apiClient: ApiClient
}

type InitializationResult =
  | { status: 'ready'; deviceId: string }
  | { status: 'error' }

const DeviceContext = createContext<DeviceContextValue | null>(null)

export function isValidDeviceId(value: string | null): value is string {
  return value !== null && UUID_V4_PATTERN.test(value)
}

export function initializeDeviceId(
  storage: Pick<Storage, 'getItem' | 'setItem'>,
  createId: () => string = () => crypto.randomUUID(),
): string {
  const storedId = storage.getItem(DEVICE_ID_STORAGE_KEY)
  if (isValidDeviceId(storedId)) return storedId

  const generatedId = createId()
  if (!isValidDeviceId(generatedId)) {
    throw new Error('유효한 기기 식별자를 생성하지 못했습니다.')
  }

  storage.setItem(DEVICE_ID_STORAGE_KEY, generatedId)
  const confirmedId = storage.getItem(DEVICE_ID_STORAGE_KEY)
  if (confirmedId !== generatedId || !isValidDeviceId(confirmedId)) {
    throw new Error('기기 식별자를 저장하지 못했습니다.')
  }

  return confirmedId
}

function initialize(): InitializationResult {
  try {
    return { status: 'ready', deviceId: initializeDeviceId(window.localStorage) }
  } catch {
    return { status: 'error' }
  }
}

export function DeviceProvider({ children }: PropsWithChildren) {
  const [initialization] = useState<InitializationResult>(initialize)
  const value = useMemo<DeviceContextValue | null>(() => {
    if (initialization.status !== 'ready') return null

    return {
      deviceId: initialization.deviceId,
      apiClient: createApiClient(initialization.deviceId),
    }
  }, [initialization])

  if (!value) {
    return (
      <main className="min-h-screen bg-stone-50 px-4 py-8 text-stone-900">
        <section
          className="mx-auto w-full rounded-2xl border border-red-200 bg-white p-6 md:max-w-[480px]"
          role="alert"
        >
          <h1 className="text-xl font-bold">기기 식별자를 저장할 수 없어요</h1>
          <p className="mt-3 text-sm leading-6 text-stone-600">
            브라우저의 사이트 데이터 저장을 허용한 뒤 페이지를 새로고침해 주세요.
          </p>
        </section>
      </main>
    )
  }

  return <DeviceContext.Provider value={value}>{children}</DeviceContext.Provider>
}

export function useDevice(): DeviceContextValue {
  const context = useContext(DeviceContext)
  if (!context) {
    throw new Error('useDevice는 DeviceProvider 안에서 사용해야 합니다.')
  }
  return context
}
