import { act, renderHook } from '@testing-library/react'
import type { PropsWithChildren } from 'react'

import type { InventoryDto, MealPlanDto } from '../../models/types'
import { MealPlanProvider, useMealPlan } from './MealPlanProvider'

const inventory: InventoryDto = {
  version: 1,
  items: [
    {
      id: 'onion',
      name: '양파',
      quantity: 8,
      storageLocation: '실온',
      expirationDate: '2026-04-08',
      expirationEstimated: true,
    },
  ],
}

const mealPlan: MealPlanDto = {
  id: 'plan-1',
  inventoryVersion: 1,
  meals: [
    {
      id: 'meal-1',
      day: 1,
      slot: '점심',
      recommendation: {
        id: 'recommendation-1',
        menuName: '양파 덮밥',
        ingredients: [{ itemId: 'onion', name: '양파', quantity: 1 }],
        seasonings: ['간장'],
      },
    },
  ],
}

function wrapper({ children }: PropsWithChildren) {
  return <MealPlanProvider>{children}</MealPlanProvider>
}

describe('MealPlanProvider', () => {
  it('식단과 snapshot을 메모리에 저장하고 성공한 끼니만 완료 처리한다', () => {
    const { result } = renderHook(() => useMealPlan(), { wrapper })

    act(() => result.current.saveMealPlan(mealPlan, inventory))
    inventory.items[0].quantity = 1

    expect(result.current.mealPlan).toEqual(mealPlan)
    expect(result.current.inventorySnapshot?.items[0].quantity).toBe(8)
    expect(result.current.completedMealIds.size).toBe(0)

    act(() => result.current.markMealCompleted('meal-1'))
    expect(result.current.completedMealIds).toEqual(new Set(['meal-1']))

    act(() => result.current.clearMealPlan())
    expect(result.current.mealPlan).toBeNull()
    expect(result.current.inventorySnapshot).toBeNull()
    expect(result.current.completedMealIds.size).toBe(0)
  })
})
