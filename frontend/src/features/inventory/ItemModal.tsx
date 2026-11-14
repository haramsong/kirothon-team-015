import { useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import type { InventoryItemDto, StorageLocation } from '../../models/types'

const STORAGE_LOCATIONS: StorageLocation[] = ['냉장', '냉동', '실온']

export type ItemModalMode = 'draft' | 'inventory'

interface ItemModalProps {
  item: InventoryItemDto
  mode: ItemModalMode
  onClose: () => void
  onSave: (item: InventoryItemDto) => Promise<void> | void
  onDelete?: () => Promise<void> | void
}

interface ValidationErrors {
  name?: string
  quantity?: string
  storageLocation?: string
  expirationDate?: string
}

function isRealIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(Date.UTC(year, month - 1, day))

  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  )
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

export function ItemModal({ item, mode, onClose, onSave, onDelete }: ItemModalProps) {
  const [name, setName] = useState(item.name)
  const [quantity, setQuantity] = useState(String(item.quantity))
  const [storageLocation, setStorageLocation] = useState<StorageLocation>(
    item.storageLocation,
  )
  const [expirationDate, setExpirationDate] = useState(item.expirationDate)
  const [expirationEstimated, setExpirationEstimated] = useState(item.expirationEstimated)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDeleteConfirming, setIsDeleteConfirming] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)

  const parsedQuantity = Number(quantity)
  const errors = useMemo<ValidationErrors>(() => {
    const nextErrors: ValidationErrors = {}

    if (!name.trim()) nextErrors.name = '품목명을 입력해 주세요.'
    if (name.length > 80) nextErrors.name = '품목명은 80자 이하로 입력해 주세요.'

    const minimumQuantity = mode === 'inventory' ? 0 : 0.5
    if (
      quantity.trim() === '' ||
      !Number.isFinite(parsedQuantity) ||
      parsedQuantity < minimumQuantity ||
      !Number.isInteger(parsedQuantity * 2)
    ) {
      nextErrors.quantity =
        mode === 'inventory'
          ? '수량은 0개 이상의 0.5개 단위로 입력해 주세요.'
          : '수량은 0.5개 이상의 0.5개 단위로 입력해 주세요.'
    }

    if (!STORAGE_LOCATIONS.includes(storageLocation)) {
      nextErrors.storageLocation = '보관 위치를 선택해 주세요.'
    }
    if (!isRealIsoDate(expirationDate)) {
      nextErrors.expirationDate = '올바른 소비기한을 입력해 주세요.'
    }

    return nextErrors
  }, [expirationDate, mode, name, parsedQuantity, quantity, storageLocation])

  const isValid = Object.keys(errors).length === 0

  async function handleSave() {
    if (!isValid || isSubmitting) return

    setIsSubmitting(true)
    setRequestError(null)
    try {
      await onSave({
        ...item,
        name: name.trim(),
        quantity: parsedQuantity,
        storageLocation,
        expirationDate,
        expirationEstimated,
      })
    } catch (error) {
      setRequestError(errorMessage(error, '품목을 저장하지 못했어요. 다시 시도해 주세요.'))
      setIsSubmitting(false)
    }
  }

  async function handleDelete() {
    if (!onDelete || isSubmitting) return

    setIsSubmitting(true)
    setRequestError(null)
    try {
      await onDelete()
    } catch (error) {
      setRequestError(errorMessage(error, '품목을 삭제하지 못했어요. 다시 시도해 주세요.'))
      setIsSubmitting(false)
    }
  }

  return (
    <div
      aria-labelledby="item-modal-title"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-end justify-center bg-stone-950/40 p-0 sm:items-center sm:p-4"
      role="dialog"
    >
      <div className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-5 shadow-xl sm:max-w-[448px] sm:rounded-3xl">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-stone-900" id="item-modal-title">
            {mode === 'inventory' ? '재료 수정' : '등록할 재료 수정'}
          </h2>
          <button
            className="rounded-lg px-2 py-1 text-sm font-semibold text-stone-500 hover:bg-stone-100"
            disabled={isSubmitting}
            onClick={onClose}
            type="button"
          >
            닫기
          </button>
        </div>

        <div className="mt-5 space-y-4">
          <label className="block text-sm font-semibold text-stone-800">
            품목명
            <input
              aria-describedby={errors.name ? 'item-name-error' : undefined}
              aria-invalid={Boolean(errors.name)}
              className="mt-1.5 w-full rounded-xl border border-stone-300 px-3 py-2.5 font-normal outline-none focus:border-emerald-600"
              disabled={isSubmitting}
              maxLength={81}
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>
          {errors.name && (
            <p className="-mt-2 text-sm text-red-700" id="item-name-error">
              {errors.name}
            </p>
          )}

          <label className="block text-sm font-semibold text-stone-800">
            수량 (개)
            <input
              aria-describedby={errors.quantity ? 'item-quantity-error' : undefined}
              aria-invalid={Boolean(errors.quantity)}
              className="mt-1.5 w-full rounded-xl border border-stone-300 px-3 py-2.5 font-normal outline-none focus:border-emerald-600"
              disabled={isSubmitting}
              inputMode="decimal"
              min={mode === 'inventory' ? 0 : 0.5}
              onChange={(event) => setQuantity(event.target.value)}
              step="0.5"
              type="number"
              value={quantity}
            />
          </label>
          {errors.quantity && (
            <p className="-mt-2 text-sm text-red-700" id="item-quantity-error">
              {errors.quantity}
            </p>
          )}
          {mode === 'inventory' && parsedQuantity === 0 && !errors.quantity && (
            <p className="-mt-2 text-sm font-medium text-amber-700">
              수량이 0개이면 냉장고에서 삭제됩니다.
            </p>
          )}

          <label className="block text-sm font-semibold text-stone-800">
            보관 위치
            <select
              aria-describedby={errors.storageLocation ? 'item-storage-error' : undefined}
              aria-invalid={Boolean(errors.storageLocation)}
              className="mt-1.5 w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 font-normal outline-none focus:border-emerald-600"
              disabled={isSubmitting}
              onChange={(event) => setStorageLocation(event.target.value as StorageLocation)}
              value={storageLocation}
            >
              {STORAGE_LOCATIONS.map((location) => (
                <option key={location} value={location}>
                  {location}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-semibold text-stone-800">
            소비기한
            <input
              aria-describedby={errors.expirationDate ? 'item-expiration-error' : undefined}
              aria-invalid={Boolean(errors.expirationDate)}
              className="mt-1.5 w-full rounded-xl border border-stone-300 px-3 py-2.5 font-normal outline-none focus:border-emerald-600"
              disabled={isSubmitting}
              onChange={(event) => {
                setExpirationDate(event.target.value)
                setExpirationEstimated(false)
              }}
              type="date"
              value={expirationDate}
            />
          </label>
          {errors.expirationDate && (
            <p className="-mt-2 text-sm text-red-700" id="item-expiration-error">
              {errors.expirationDate}
            </p>
          )}
          {expirationEstimated && (
            <p className="-mt-2 text-xs text-stone-500">현재 소비기한은 예상값입니다.</p>
          )}
        </div>

        {requestError && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3" role="alert">
            <p className="text-sm font-medium text-red-800">{requestError}</p>
          </div>
        )}

        {isDeleteConfirming && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3">
            <p className="text-sm font-semibold text-red-800">이 품목을 삭제할까요?</p>
            <div className="mt-3 flex gap-2">
              <button
                className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-bold text-stone-700"
                disabled={isSubmitting}
                onClick={() => setIsDeleteConfirming(false)}
                type="button"
              >
                취소
              </button>
              <button
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-bold text-white disabled:bg-red-300"
                disabled={isSubmitting}
                onClick={() => void handleDelete()}
                type="button"
              >
                {isSubmitting ? '삭제 중...' : '삭제 확정'}
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 flex items-center gap-2">
          {onDelete && !isDeleteConfirming && (
            <button
              className="rounded-xl border border-red-200 px-4 py-3 text-sm font-bold text-red-700 hover:bg-red-50"
              disabled={isSubmitting}
              onClick={() => setIsDeleteConfirming(true)}
              type="button"
            >
              품목 삭제
            </button>
          )}
          <button
            className="ml-auto rounded-xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white disabled:bg-stone-300"
            disabled={!isValid || isSubmitting}
            onClick={() => void handleSave()}
            type="button"
          >
            {isSubmitting ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
