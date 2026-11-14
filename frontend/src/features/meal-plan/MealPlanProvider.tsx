import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'

import type { InventoryDto, MealPlanDto } from '../../models/types'

interface MealPlanContextValue {
  mealPlan: MealPlanDto | null
  inventorySnapshot: InventoryDto | null
  completedMealIds: ReadonlySet<string>
  saveMealPlan: (mealPlan: MealPlanDto, inventorySnapshot: InventoryDto) => void
  markMealCompleted: (mealId: string) => void
  clearMealPlan: () => void
}

const MealPlanContext = createContext<MealPlanContextValue | null>(null)

export function MealPlanProvider({ children }: PropsWithChildren) {
  const [mealPlan, setMealPlan] = useState<MealPlanDto | null>(null)
  const [inventorySnapshot, setInventorySnapshot] = useState<InventoryDto | null>(null)
  const [completedMealIds, setCompletedMealIds] = useState<ReadonlySet<string>>(() => new Set())

  const saveMealPlan = useCallback(
    (nextMealPlan: MealPlanDto, nextInventorySnapshot: InventoryDto) => {
      setMealPlan(nextMealPlan)
      setInventorySnapshot({
        ...nextInventorySnapshot,
        items: nextInventorySnapshot.items.map((item) => ({ ...item })),
      })
      setCompletedMealIds(new Set())
    },
    [],
  )

  const markMealCompleted = useCallback((mealId: string) => {
    setCompletedMealIds((current) => {
      const next = new Set(current)
      next.add(mealId)
      return next
    })
  }, [])

  const clearMealPlan = useCallback(() => {
    setMealPlan(null)
    setInventorySnapshot(null)
    setCompletedMealIds(new Set())
  }, [])

  const value = useMemo<MealPlanContextValue>(
    () => ({
      mealPlan,
      inventorySnapshot,
      completedMealIds,
      saveMealPlan,
      markMealCompleted,
      clearMealPlan,
    }),
    [clearMealPlan, completedMealIds, inventorySnapshot, markMealCompleted, mealPlan, saveMealPlan],
  )

  return <MealPlanContext.Provider value={value}>{children}</MealPlanContext.Provider>
}

export function useMealPlan(): MealPlanContextValue {
  const context = useContext(MealPlanContext)
  if (!context) {
    throw new Error('useMealPlan은 MealPlanProvider 안에서 사용해야 합니다.')
  }
  return context
}
