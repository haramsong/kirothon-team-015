import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { getExpirationDisplay, sortInventoryItems } from '../../logic/date'
import type { MealRecommendationDto, RecipeDto } from '../../models/types'
import { DeductionModal } from '../deduction/DeductionModal'
import { useDevice } from '../device/DeviceProvider'
import { useInventory } from '../inventory/InventoryProvider'
import { useToast } from '../toast/ToastProvider'

type RequestStatus = 'idle' | 'loading' | 'success' | 'error'

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

export function RecipePage() {
  const navigate = useNavigate()
  const { apiClient } = useDevice()
  const {
    inventory,
    lastSuccessfulInventory,
    replaceInventory,
    status: inventoryStatus,
    today,
  } = useInventory()
  const { showToast } = useToast()
  const displayedInventory = inventory ?? lastSuccessfulInventory
  const [recommendation, setRecommendation] = useState<MealRecommendationDto | null>(null)
  const [isDeductionOpen, setIsDeductionOpen] = useState(false)
  const [recommendationStatus, setRecommendationStatus] = useState<RequestStatus>('idle')
  const [recommendationError, setRecommendationError] = useState<string | null>(null)
  const [recipe, setRecipe] = useState<RecipeDto | null>(null)
  const [recipeStatus, setRecipeStatus] = useState<RequestStatus>('idle')
  const [recipeError, setRecipeError] = useState<string | null>(null)
  const lastExcludedMenuName = useRef<string | undefined>(undefined)
  const initialRequestStarted = useRef(false)

  const sortedItems = useMemo(
    () => (displayedInventory ? sortInventoryItems(displayedInventory.items, today) : []),
    [displayedInventory, today],
  )
  const inventoryById = useMemo(
    () => new Map(sortedItems.map((item) => [item.id, item])),
    [sortedItems],
  )
  const expiringItems = useMemo(
    () =>
      sortedItems.filter((item) => {
        const expiration = getExpirationDisplay(item.expirationDate, today)
        return expiration.isExpiring && !expiration.isExpired
      }),
    [sortedItems, today],
  )

  const requestRecipe = useCallback(
    async (nextRecommendation: MealRecommendationDto) => {
      setRecipeStatus('loading')
      setRecipeError(null)
      setRecipe(null)

      try {
        const nextRecipe = await apiClient.post<RecipeDto>('/api/recipes', {
          recommendation: nextRecommendation,
        })
        setRecipe(nextRecipe)
        setRecipeStatus('success')
      } catch (error) {
        setRecipeStatus('error')
        setRecipeError(
          getErrorMessage(error, '조리 순서를 불러오지 못했어요. 다시 시도해 주세요.'),
        )
      }
    },
    [apiClient],
  )

  const requestRecommendation = useCallback(
    async (excludedMenuName?: string) => {
      lastExcludedMenuName.current = excludedMenuName
      setRecommendationStatus('loading')
      setRecommendationError(null)

      try {
        const nextRecommendation = await apiClient.post<MealRecommendationDto>(
          '/api/recommendations',
          {
            clientDate: today,
            ...(excludedMenuName ? { excludedMenuName } : {}),
          },
        )
        setRecommendation(nextRecommendation)
        setRecommendationStatus('success')
        await requestRecipe(nextRecommendation)
      } catch (error) {
        setRecommendationStatus('error')
        setRecommendationError(
          getErrorMessage(error, '메뉴를 추천하지 못했어요. 다시 시도해 주세요.'),
        )
      }
    },
    [apiClient, requestRecipe, today],
  )

  useEffect(() => {
    if (
      initialRequestStarted.current ||
      !displayedInventory ||
      displayedInventory.items.length === 0
    ) {
      return
    }

    initialRequestStarted.current = true
    void requestRecommendation()
  }, [displayedInventory, requestRecommendation])

  const isInventoryLoading = inventoryStatus === 'loading' && displayedInventory === null
  const hasUsableInventory = sortedItems.length > 0
  const isRecommendationLoading = recommendationStatus === 'loading'

  return (
    <main className="min-h-screen bg-stone-50 px-4 py-6 text-stone-900">
      <section className="mx-auto w-full md:max-w-[480px]">
        <Link className="text-sm font-bold text-emerald-700" to="/">
          ← 냉장고로
        </Link>
        <p className="mt-5 text-sm font-semibold text-emerald-700">임박 재료 먼저</p>
        <h1 className="mt-1 text-2xl font-bold">한 끼 추천</h1>

        {isInventoryLoading && (
          <div className="mt-8 text-center" role="status">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-emerald-100 border-t-emerald-600" />
            <p className="mt-3 text-sm text-stone-600">냉장고를 불러오는 중이에요</p>
          </div>
        )}

        {!isInventoryLoading && !hasUsableInventory && (
          <div className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 text-center">
            <p className="font-bold">추천할 재료가 없어요</p>
            <p className="mt-2 text-sm text-stone-600">냉장고에 재료를 먼저 등록해 주세요.</p>
            <Link
              className="mt-4 inline-block rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white"
              to="/register"
            >
              재료 등록하기
            </Link>
          </div>
        )}

        {hasUsableInventory && expiringItems.length > 0 && (
          <div className="mt-5" aria-label="임박 재료">
            <p className="text-sm font-bold text-stone-700">먼저 사용할 임박 재료</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {expiringItems.map((item) => (
                <span
                  className="rounded-full bg-amber-100 px-3 py-1.5 text-sm font-bold text-amber-800"
                  key={item.id}
                >
                  {item.name} · {getExpirationDisplay(item.expirationDate, today).dDayLabel}
                </span>
              ))}
            </div>
          </div>
        )}

        {isRecommendationLoading && (
          <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4" role="status">
            <p className="text-sm font-bold text-emerald-800">메뉴를 추천하는 중이에요</p>
            <p className="mt-1 text-xs text-emerald-700">임박 재료를 먼저 살펴보고 있어요.</p>
          </div>
        )}

        {recommendationStatus === 'error' && (
          <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
            <p className="text-sm font-medium text-red-800">{recommendationError}</p>
            <button
              className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-700 disabled:opacity-50"
              disabled={isRecommendationLoading}
              onClick={() => void requestRecommendation(lastExcludedMenuName.current)}
              type="button"
            >
              메뉴 추천 다시 시도
            </button>
          </div>
        )}

        {recommendation && (
          <article className="mt-6 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold text-emerald-700">오늘의 한 끼</p>
                <h2 className="mt-1 text-xl font-bold">{recommendation.menuName}</h2>
              </div>
              <button
                className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-bold text-stone-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isRecommendationLoading}
                onClick={() => void requestRecommendation(recommendation.menuName)}
                type="button"
              >
                다른 메뉴 추천
              </button>
            </div>

            <section className="mt-5" aria-labelledby="ingredient-heading">
              <h3 className="text-sm font-bold" id="ingredient-heading">
                사용할 재료
              </h3>
              <ul className="mt-2 divide-y divide-stone-100">
                {recommendation.ingredients.map((ingredient) => (
                  <li className="flex items-center justify-between gap-3 py-3 text-sm" key={ingredient.itemId}>
                    <span className="font-medium">{ingredient.name}</span>
                    <span className="text-stone-600">
                      사용 {ingredient.quantity}개 · 현재{' '}
                      {inventoryById.get(ingredient.itemId)?.quantity ?? '-'}개
                    </span>
                  </li>
                ))}
              </ul>
              {recommendation.seasonings.length > 0 && (
                <p className="mt-2 text-xs text-stone-500">
                  기본 양념: {recommendation.seasonings.join(', ')}
                </p>
              )}
            </section>

            <section className="mt-5 border-t border-stone-100 pt-5" aria-labelledby="recipe-heading">
              <h3 className="text-sm font-bold" id="recipe-heading">
                조리 순서
              </h3>

              {recipeStatus === 'loading' && (
                <div className="mt-3 rounded-xl bg-stone-100 p-4" role="status">
                  <p className="text-sm font-medium text-stone-700">조리 순서를 만드는 중이에요</p>
                </div>
              )}

              {recipeStatus === 'error' && (
                <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
                  <p className="text-sm text-red-800">{recipeError}</p>
                  <button
                    className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-700"
                    onClick={() => void requestRecipe(recommendation)}
                    type="button"
                  >
                    조리 순서 다시 시도
                  </button>
                </div>
              )}

              {recipeStatus === 'success' && recipe && (
                <ol className="mt-3 space-y-3">
                  {recipe.steps.map((step, index) => (
                    <li className="flex gap-3 text-sm leading-6" key={`${index}-${step}`}>
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-800">
                        {index + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <button
              className="mt-6 w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white hover:bg-emerald-700"
              onClick={() => setIsDeductionOpen(true)}
              type="button"
            >
              요리했어요
            </button>
          </article>
        )}
      </section>

      {isDeductionOpen && recommendation && displayedInventory && (
        <DeductionModal
          inventory={displayedInventory}
          onCancel={() => setIsDeductionOpen(false)}
          onSuccess={(result) => {
            replaceInventory(result.inventory)
            const removedMessage =
              result.removedNames.length > 0
                ? ` 냉장고에서 제거: ${result.removedNames.join(', ')}`
                : ''
            showToast(`${result.deductedCount}개 재료를 차감했어요.${removedMessage}`)
            setIsDeductionOpen(false)
            navigate('/')
          }}
          recommendation={recommendation}
          today={today}
        />
      )}
    </main>
  )
}
