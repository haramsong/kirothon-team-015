import type { InventoryDto, MealPlanDto } from '../models/types'
import { summarizeMealPlan } from './mealPlan'

const inventory: InventoryDto = {
  version: 2,
  items: [
    {
      id: 'onion',
      name: '양파',
      quantity: 2,
      storageLocation: '실온',
      expirationDate: '2026-04-10',
      expirationEstimated: true,
    },
    {
      id: 'egg',
      name: '달걀',
      quantity: 3,
      storageLocation: '냉장',
      expirationDate: '2026-04-12',
      expirationEstimated: false,
    },
  ],
}

const mealPlan: MealPlanDto = {
  id: 'plan-1',
  inventoryVersion: 2,
  meals: Array.from({ length: 6 }, (_, index) => ({
    id: `meal-${index + 1}`,
    day: (Math.floor(index / 2) + 1) as 1 | 2 | 3,
    slot: index % 2 === 0 ? ('점심' as const) : ('저녁' as const),
    recommendation: {
      id: `recommendation-${index + 1}`,
      menuName: `메뉴 ${index + 1}`,
      ingredients:
        index < 3
          ? [{ itemId: 'onion', name: '양파', quantity: 1 }]
          : [{ itemId: 'egg', name: '달걀', quantity: 0.5 }],
      seasonings: [],
    },
  })),
}

describe('summarizeMealPlan', () => {
  it('생성 시점 재고에서 사용 합계와 잔여·부족 수량을 반 개 단위로 계산한다', () => {
    expect(summarizeMealPlan(inventory, mealPlan)).toEqual([
      {
        itemId: 'onion',
        name: '양파',
        currentQuantity: 2,
        usedQuantity: 3,
        remainingQuantity: 0,
        shortageQuantity: 1,
      },
      {
        itemId: 'egg',
        name: '달걀',
        currentQuantity: 3,
        usedQuantity: 1.5,
        remainingQuantity: 1.5,
        shortageQuantity: 0,
      },
    ])
  })
})
