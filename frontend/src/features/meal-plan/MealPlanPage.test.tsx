import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'

import type { InventoryDto, MealPlanDto } from '../../models/types'
import { MealPlanPage } from './MealPlanPage'
import { MealPlanProvider } from './MealPlanProvider'

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }))

vi.mock('../device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: { post: postMock }, deviceId: 'test-device' }),
}))

const inventory: InventoryDto = {
  version: 7,
  items: [
    {
      id: 'onion',
      name: '양파',
      quantity: 8,
      storageLocation: '실온',
      expirationDate: '2026-04-08',
      expirationEstimated: true,
    },
    {
      id: 'egg',
      name: '달걀',
      quantity: 2,
      storageLocation: '냉장',
      expirationDate: '2026-04-15',
      expirationEstimated: true,
    },
  ],
}

vi.mock('../inventory/InventoryProvider', () => ({
  useInventory: () => ({
    inventory,
    lastSuccessfulInventory: inventory,
    status: 'success',
    today: '2026-04-07',
  }),
}))

function createMealPlan(id = 'plan-1'): MealPlanDto {
  return {
    id,
    inventoryVersion: 7,
    meals: Array.from({ length: 6 }, (_, index) => ({
      id: `${id}-meal-${index + 1}`,
      day: (Math.floor(index / 2) + 1) as 1 | 2 | 3,
      slot: index % 2 === 0 ? ('점심' as const) : ('저녁' as const),
      recommendation: {
        id: `${id}-recommendation-${index + 1}`,
        menuName: `양파 메뉴 ${index + 1}`,
        ingredients: [
          { itemId: 'onion', name: '양파', quantity: 1 },
          ...(index === 0 ? [{ itemId: 'egg', name: '달걀', quantity: 0.5 }] : []),
        ],
        seasonings: ['간장'],
      },
    })),
  }
}

function RecipeLocationProbe() {
  const location = useLocation()
  const state = location.state as { mealPlanMealId?: string } | null
  return <p>선택한 끼니: {state?.mealPlanMealId}</p>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/meal-plan']}>
      <MealPlanProvider>
        <Routes>
          <Route element={<MealPlanPage />} path="/meal-plan" />
          <Route element={<RecipeLocationProbe />} path="/recipe" />
          <Route element={<p>냉장고</p>} path="/" />
        </Routes>
      </MealPlanProvider>
    </MemoryRouter>,
  )
}

describe('MealPlanPage', () => {
  beforeEach(() => {
    postMock.mockReset()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('생성 시점 snapshot 요약과 정확히 6개 끼니를 표시하고 선택한 끼니를 레시피로 전달한다', async () => {
    const user = userEvent.setup()
    const mealPlan = createMealPlan()
    postMock.mockResolvedValue(mealPlan)

    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('3일 식단을 만드는 중이에요')
    expect(await screen.findByText('식단을 짠 시점의 재고 기준')).toBeInTheDocument()
    expect(postMock).toHaveBeenCalledWith('/api/meal-plans', { clientDate: '2026-04-07' })
    expect(screen.getByText('현재 8개 · 사용 6개 · 3일 뒤 2개')).toBeInTheDocument()
    expect(screen.getByText('현재 2개 · 사용 0.5개 · 3일 뒤 1.5개')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '레시피 보기' })).toHaveLength(6)

    await user.click(screen.getAllByRole('button', { name: '레시피 보기' })[0])
    expect(screen.getByText(`선택한 끼니: ${mealPlan.meals[0].id}`)).toBeInTheDocument()
  })

  it('사용자 확인 뒤 현재 재고를 기준으로 식단을 재생성한다', async () => {
    const user = userEvent.setup()
    postMock.mockResolvedValueOnce(createMealPlan()).mockResolvedValueOnce(createMealPlan('plan-2'))

    renderPage()
    await screen.findByText('양파 메뉴 1')

    await user.click(screen.getByRole('button', { name: '식단 다시 만들기' }))

    expect(window.confirm).toHaveBeenCalledWith('현재 냉장고 재고로 3일 식단을 다시 만들까요?')
    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('양파 메뉴 6')).toBeInTheDocument()
  })
})
