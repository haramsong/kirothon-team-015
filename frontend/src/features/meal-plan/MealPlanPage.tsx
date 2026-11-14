import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { getExpirationDisplay } from '../../logic/date'
import { summarizeMealPlan } from '../../logic/mealPlan'
import type { InventoryDto, MealPlanDto } from '../../models/types'
import { useDevice } from '../device/DeviceProvider'
import { useInventory } from '../inventory/InventoryProvider'
import { useMealPlan } from './MealPlanProvider'

type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

interface MealPlanLocationState {
  mealPlanSession?: boolean
}

function getErrorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : '3일 식단을 만들지 못했어요. 다시 시도해 주세요.'
}

function hasUsableItems(inventory: InventoryDto, today: string): boolean {
  return inventory.items.some(
    (item) => !getExpirationDisplay(item.expirationDate, today).isExpired,
  )
}

export function MealPlanPage() {
  const { apiClient } = useDevice()
  const { inventory, lastSuccessfulInventory, status: inventoryStatus, today } = useInventory()
  const {
    mealPlan,
    inventorySnapshot,
    completedMealIds,
    saveMealPlan,
  } = useMealPlan()
  const location = useLocation()
  const navigate = useNavigate()
  const displayedInventory = inventory ?? lastSuccessfulInventory
  const locationState = location.state as MealPlanLocationState | null
  const initialRequestStarted = useRef(false)
  const [requestStatus, setRequestStatus] = useState<RequestStatus>(
    mealPlan ? 'success' : 'idle',
  )
  const [requestError, setRequestError] = useState<string | null>(null)

  const requestMealPlan = useCallback(async () => {
    if (!displayedInventory || !hasUsableItems(displayedInventory, today)) return

    setRequestStatus('loading')
    setRequestError(null)
    try {
      const nextMealPlan = await apiClient.post<MealPlanDto>('/api/meal-plans', {
        clientDate: today,
      })
      if (nextMealPlan.meals.length !== 6) {
        throw new Error('식단의 끼니 수가 올바르지 않습니다.')
      }
      saveMealPlan(nextMealPlan, displayedInventory)
      setRequestStatus('success')
      navigate('/meal-plan', { replace: true, state: { mealPlanSession: true } })
    } catch (error) {
      setRequestStatus('error')
      setRequestError(getErrorMessage(error))
    }
  }, [apiClient, displayedInventory, navigate, saveMealPlan, today])

  useEffect(() => {
    if (mealPlan || initialRequestStarted.current || !displayedInventory) return

    if (locationState?.mealPlanSession) {
      navigate('/', { replace: true })
      return
    }

    if (!hasUsableItems(displayedInventory, today)) return
    initialRequestStarted.current = true
    void requestMealPlan()
  }, [displayedInventory, locationState?.mealPlanSession, mealPlan, navigate, requestMealPlan, today])

  const summaries = useMemo(
    () =>
      mealPlan && inventorySnapshot
        ? summarizeMealPlan(inventorySnapshot, mealPlan)
        : [],
    [inventorySnapshot, mealPlan],
  )
  const isInitialLoading = inventoryStatus === 'loading' && !displayedInventory
  const noUsableItems =
    displayedInventory !== null && !hasUsableItems(displayedInventory, today)

  function regenerateMealPlan() {
    if (!window.confirm('현재 냉장고 재고로 3일 식단을 다시 만들까요?')) return
    void requestMealPlan()
  }

  return (
    <main className="min-h-screen bg-stone-50 px-4 py-6 text-stone-900">
      <section className="mx-auto w-full md:max-w-[480px]">
        <Link className="text-sm font-bold text-emerald-700" to="/">
          ← 냉장고로
        </Link>
        <p className="mt-5 text-sm font-semibold text-emerald-700">임박 재료를 끝까지</p>
        <h1 className="mt-1 text-2xl font-bold">3일 식단</h1>

        {(isInitialLoading || requestStatus === 'loading') && (
          <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4" role="status">
            <p className="text-sm font-bold text-emerald-800">
              {isInitialLoading ? '냉장고를 불러오는 중이에요' : '3일 식단을 만드는 중이에요'}
            </p>
          </div>
        )}

        {!isInitialLoading && noUsableItems && (
          <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-center">
            <p className="font-bold">사용 가능한 재료가 없어요</p>
            <p className="mt-2 text-sm text-stone-600">
              소비기한이 지나지 않은 재료를 먼저 등록해 주세요.
            </p>
            <Link
              className="mt-4 inline-block rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white"
              to="/register"
            >
              재료 등록하기
            </Link>
          </div>
        )}

        {requestStatus === 'error' && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
            <p className="text-sm font-medium text-red-800">{requestError}</p>
            <button
              className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-700"
              onClick={() => void requestMealPlan()}
              type="button"
            >
              식단 생성 다시 시도
            </button>
          </div>
        )}

        {mealPlan && inventorySnapshot && (
          <>
            <section className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-labelledby="summary-heading">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-bold" id="summary-heading">3일 뒤 재고 예상</h2>
                  <p className="mt-1 text-xs text-stone-500">식단을 짠 시점의 재고 기준</p>
                </div>
                <button
                  className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-bold text-stone-700 disabled:opacity-50"
                  disabled={requestStatus === 'loading'}
                  onClick={regenerateMealPlan}
                  type="button"
                >
                  식단 다시 만들기
                </button>
              </div>
              <ul className="mt-4 divide-y divide-stone-100" aria-label="식단 재고 요약">
                {summaries.map((summary) => (
                  <li className="py-3" key={summary.itemId}>
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="font-bold">{summary.name}</span>
                      <span className="text-stone-700">
                        현재 {summary.currentQuantity}개 · 사용 {summary.usedQuantity}개 · 3일 뒤 {summary.remainingQuantity}개
                      </span>
                    </div>
                    {summary.shortageQuantity > 0 && (
                      <p className="mt-1 text-right text-xs font-bold text-red-700">
                        {summary.shortageQuantity}개 부족
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <section className="mt-6" aria-labelledby="meals-heading">
              <h2 className="text-lg font-bold" id="meals-heading">6개 끼니</h2>
              <div className="mt-3 space-y-3">
                {mealPlan.meals.map((meal) => {
                  const isCompleted = completedMealIds.has(meal.id)
                  return (
                    <article className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm" key={meal.id}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-bold text-emerald-700">{meal.day}일차 {meal.slot}</p>
                          <h3 className="mt-1 font-bold">{meal.recommendation.menuName}</h3>
                        </div>
                        {isCompleted && (
                          <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">완료</span>
                        )}
                      </div>
                      <p className="mt-2 text-xs text-stone-500">
                        {meal.recommendation.ingredients
                          .map((ingredient) => `${ingredient.name} ${ingredient.quantity}개`)
                          .join(' · ')}
                      </p>
                      <button
                        className="mt-3 w-full rounded-xl border border-emerald-300 px-3 py-2.5 text-sm font-bold text-emerald-700"
                        onClick={() => navigate('/recipe', { state: { mealPlanMealId: meal.id } })}
                        type="button"
                      >
                        {isCompleted ? '레시피 다시 보기' : '레시피 보기'}
                      </button>
                    </article>
                  )
                })}
              </div>
            </section>
          </>
        )}
      </section>
    </main>
  )
}
