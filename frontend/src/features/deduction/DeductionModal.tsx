import { useMemo, useState } from 'react'

import { ApiError } from '../../api/client'
import type {
  DeductionRequestDto,
  DeductionResultDto,
  InventoryDto,
  MealRecommendationDto,
} from '../../models/types'
import { useDevice } from '../device/DeviceProvider'

interface DeductionModalProps {
  recommendation: MealRecommendationDto
  inventory: InventoryDto
  today: string
  onCancel: () => void
  onSuccess: (result: DeductionResultDto) => void | Promise<void>
}

interface DraftLine {
  itemId: string
  name: string
  currentQuantity: number
  quantity: string
  included: boolean
}

function toHalfUnits(quantity: number): number {
  return Math.round(quantity * 2)
}

function fromHalfUnits(halfUnits: number): number {
  return halfUnits / 2
}

function isValidUseQuantity(value: string, currentQuantity: number): boolean {
  const quantity = Number(value)
  return (
    value.trim() !== '' &&
    Number.isFinite(quantity) &&
    Number.isInteger(quantity * 2) &&
    quantity >= 0.5 &&
    quantity <= currentQuantity
  )
}

function createInitialDraft(
  recommendation: MealRecommendationDto,
  inventory: InventoryDto,
): DraftLine[] {
  const inventoryById = new Map(inventory.items.map((item) => [item.id, item]))

  return recommendation.ingredients.flatMap((ingredient) => {
    const item = inventoryById.get(ingredient.itemId)
    if (!item) return []

    return [
      {
        itemId: item.id,
        name: item.name,
        currentQuantity: item.quantity,
        quantity: String(ingredient.quantity),
        included: true,
      },
    ]
  })
}

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : '재고를 차감하지 못했어요. 수정 내용을 유지했으니 다시 시도해 주세요.'
}

export function DeductionModal({
  recommendation,
  inventory,
  today,
  onCancel,
  onSuccess,
}: DeductionModalProps) {
  const { apiClient } = useDevice()
  const [requestId] = useState(() => crypto.randomUUID())
  const [draft, setDraft] = useState<DraftLine[]>(() =>
    createInitialDraft(recommendation, inventory),
  )
  const [candidateId, setCandidateId] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)

  const draftItemIds = useMemo(() => new Set(draft.map((line) => line.itemId)), [draft])
  const addableItems = useMemo(
    () => inventory.items.filter((item) => !draftItemIds.has(item.id) && item.quantity >= 1),
    [draftItemIds, inventory.items],
  )
  const selectedLines = draft.filter((line) => line.included)
  const hasInvalidSelection = selectedLines.some(
    (line) => !isValidUseQuantity(line.quantity, line.currentQuantity),
  )
  const canSubmit = selectedLines.length > 0 && !hasInvalidSelection && !isSubmitting

  function updateLine(itemId: string, update: Partial<Pick<DraftLine, 'included' | 'quantity'>>) {
    setDraft((current) =>
      current.map((line) => (line.itemId === itemId ? { ...line, ...update } : line)),
    )
  }

  function addInventoryItem() {
    if (!candidateId || isSubmitting) return
    const item = inventory.items.find((candidate) => candidate.id === candidateId)
    if (!item || item.quantity < 1 || draftItemIds.has(item.id)) return

    setDraft((current) => [
      ...current,
      {
        itemId: item.id,
        name: item.name,
        currentQuantity: item.quantity,
        quantity: '1',
        included: true,
      },
    ])
    setCandidateId('')
  }

  async function confirmDeduction() {
    if (!canSubmit) return

    const body: DeductionRequestDto = {
      deductionRequestId: requestId,
      items: selectedLines.map((line) => ({
        itemId: line.itemId,
        quantity: Number(line.quantity),
      })),
    }

    setIsSubmitting(true)
    setRequestError(null)
    try {
      const result = await apiClient.post<DeductionResultDto>(
        `/api/deductions?today=${encodeURIComponent(today)}`,
        body,
      )
      await onSuccess(result)
    } catch (error) {
      setRequestError(getErrorMessage(error))
      setIsSubmitting(false)
    }
  }

  return (
    <div
      aria-labelledby="deduction-modal-title"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-end justify-center bg-stone-950/40 p-0 sm:items-center sm:p-4"
      role="dialog"
    >
      <div className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-5 shadow-xl sm:max-w-[448px] sm:rounded-3xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-emerald-700">차감 전 마지막 확인</p>
            <h2 className="mt-1 text-xl font-bold text-stone-900" id="deduction-modal-title">
              실제로 사용한 재료
            </h2>
          </div>
          <button
            className="rounded-lg px-2 py-1 text-sm font-semibold text-stone-500 hover:bg-stone-100 disabled:opacity-50"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            취소
          </button>
        </div>

        <ul className="mt-5 space-y-3" aria-label="차감할 재료">
          {draft.map((line) => {
            const isValid = isValidUseQuantity(line.quantity, line.currentQuantity)
            const afterQuantity = isValid
              ? fromHalfUnits(
                  toHalfUnits(line.currentQuantity) - toHalfUnits(Number(line.quantity)),
                )
              : null

            return (
              <li className="rounded-2xl border border-stone-200 p-4" key={line.itemId}>
                <div className="flex items-center justify-between gap-3">
                  <label className="flex items-center gap-2 font-bold text-stone-900">
                    <input
                      checked={line.included}
                      disabled={isSubmitting}
                      onChange={(event) =>
                        updateLine(line.itemId, { included: event.target.checked })
                      }
                      type="checkbox"
                    />
                    {line.name}
                  </label>
                  <span className="text-xs text-stone-500">현재 {line.currentQuantity}개</span>
                </div>

                {line.included && (
                  <>
                    <label className="mt-3 block text-sm font-semibold text-stone-700">
                      {line.name} 사용량 (개)
                      <input
                        aria-invalid={!isValid}
                        className="mt-1.5 w-full rounded-xl border border-stone-300 px-3 py-2.5 font-normal outline-none focus:border-emerald-600"
                        disabled={isSubmitting}
                        inputMode="decimal"
                        max={line.currentQuantity}
                        min="0.5"
                        onChange={(event) =>
                          updateLine(line.itemId, { quantity: event.target.value })
                        }
                        step="0.5"
                        type="number"
                        value={line.quantity}
                      />
                    </label>
                    {!isValid && (
                      <p className="mt-2 text-sm text-red-700" role="alert">
                        0.5개 단위로 현재 재고 이하를 입력해 주세요.
                      </p>
                    )}
                    {afterQuantity !== null && (
                      <p className="mt-3 rounded-lg bg-stone-100 px-3 py-2 text-sm font-bold text-stone-800">
                        {line.name} {line.currentQuantity}개 → {afterQuantity}개
                      </p>
                    )}
                    {afterQuantity === 0 && (
                      <p className="mt-2 text-xs font-semibold text-amber-700">
                        차감 후 냉장고 목록에서 제거됩니다.
                      </p>
                    )}
                  </>
                )}
              </li>
            )
          })}
        </ul>

        {addableItems.length > 0 && (
          <div className="mt-4 rounded-2xl border border-dashed border-stone-300 p-4">
            <label className="block text-sm font-bold text-stone-800">
              다른 재료 추가
              <select
                className="mt-2 w-full rounded-xl border border-stone-300 bg-white px-3 py-2.5 font-normal"
                disabled={isSubmitting}
                onChange={(event) => setCandidateId(event.target.value)}
                value={candidateId}
              >
                <option value="">재료를 선택해 주세요</option>
                {addableItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · 현재 {item.quantity}개
                  </option>
                ))}
              </select>
            </label>
            <button
              className="mt-2 w-full rounded-xl border border-emerald-300 px-3 py-2 text-sm font-bold text-emerald-700 disabled:border-stone-200 disabled:text-stone-400"
              disabled={!candidateId || isSubmitting}
              onClick={addInventoryItem}
              type="button"
            >
              1개 사용으로 추가
            </button>
          </div>
        )}

        {selectedLines.length === 0 && (
          <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-800">
            차감할 재료를 한 개 이상 선택해 주세요.
          </p>
        )}

        {requestError && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3" role="alert">
            <p className="text-sm font-medium text-red-800">{requestError}</p>
            <p className="mt-1 text-xs text-red-700">같은 차감 요청으로 다시 시도합니다.</p>
          </div>
        )}

        <button
          className="mt-6 w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white disabled:bg-stone-300"
          disabled={!canSubmit}
          onClick={() => void confirmDeduction()}
          type="button"
        >
          {isSubmitting ? '차감하는 중...' : '재고에서 차감하기'}
        </button>
      </div>
    </div>
  )
}
