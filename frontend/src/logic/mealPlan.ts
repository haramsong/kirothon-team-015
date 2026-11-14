import type { InventoryDto, MealPlanDto } from '../models/types'

export interface MealPlanItemSummary {
  itemId: string
  name: string
  currentQuantity: number
  usedQuantity: number
  remainingQuantity: number
  shortageQuantity: number
}

function toHalfUnits(quantity: number): number {
  return Math.round(quantity * 2)
}

export function summarizeMealPlan(
  inventorySnapshot: InventoryDto,
  mealPlan: MealPlanDto,
): MealPlanItemSummary[] {
  const usedHalfUnits = new Map<string, number>()

  for (const meal of mealPlan.meals) {
    for (const ingredient of meal.recommendation.ingredients) {
      usedHalfUnits.set(
        ingredient.itemId,
        (usedHalfUnits.get(ingredient.itemId) ?? 0) + toHalfUnits(ingredient.quantity),
      )
    }
  }

  return inventorySnapshot.items.map((item) => {
    const current = toHalfUnits(item.quantity)
    const used = usedHalfUnits.get(item.id) ?? 0

    return {
      itemId: item.id,
      name: item.name,
      currentQuantity: current / 2,
      usedQuantity: used / 2,
      remainingQuantity: Math.max(0, current - used) / 2,
      shortageQuantity: Math.max(0, used - current) / 2,
    }
  })
}
