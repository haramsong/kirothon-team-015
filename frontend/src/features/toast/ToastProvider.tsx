import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'

interface ToastMessage {
  id: string
  message: string
}

interface ToastContextValue {
  showToast: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((message: string) => {
    const id = crypto.randomUUID()
    setToasts((current) => [...current, { id, message }])
  }, [])

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-5 z-50 mx-auto flex max-w-[448px] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            className="pointer-events-auto flex items-center justify-between gap-3 rounded-xl bg-stone-900 px-4 py-3 text-sm text-white shadow-lg"
            key={toast.id}
            role="status"
          >
            <span>{toast.message}</span>
            <button
              aria-label="알림 닫기"
              className="shrink-0 text-stone-300 hover:text-white"
              onClick={() => dismissToast(toast.id)}
              type="button"
            >
              닫기
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast는 ToastProvider 안에서 사용해야 합니다.')
  }
  return context
}
