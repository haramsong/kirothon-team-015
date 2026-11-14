import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { InventoryDto, MealRecommendationDto, RecipeDto } from '../../models/types'
import { RecipePage } from './RecipePage'

const { postMock, replaceInventoryMock, showToastMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  replaceInventoryMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: { post: postMock }, deviceId: 'test-device' }),
}))

const currentInventory: InventoryDto = {
  version: 3,
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
      quantity: 4,
      storageLocation: '냉장',
      expirationDate: '2026-04-15',
      expirationEstimated: true,
    },
  ],
}

vi.mock('../inventory/InventoryProvider', () => ({
  useInventory: () => ({
    inventory: currentInventory,
    lastSuccessfulInventory: currentInventory,
    replaceInventory: replaceInventoryMock,
    status: 'success',
    today: '2026-04-07',
  }),
}))

vi.mock('../toast/ToastProvider', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

const recommendation: MealRecommendationDto = {
  id: 'recommendation-1',
  menuName: '양파 달걀 덮밥',
  ingredients: [
    { itemId: 'onion', name: '양파', quantity: 1 },
    { itemId: 'egg', name: '달걀', quantity: 0.5 },
  ],
  seasonings: ['간장'],
}

const recipe: RecipeDto = {
  steps: ['양파를 썰어요.', '달걀과 함께 볶아요.'],
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RecipePage />
    </MemoryRouter>,
  )
}

describe('RecipePage', () => {
  beforeEach(() => {
    postMock.mockReset()
    replaceInventoryMock.mockReset()
    showToastMock.mockReset()
    vi.stubGlobal('crypto', { randomUUID: () => '323e4567-e89b-42d3-a456-426614174000' })
  })

  it('임박 재료를 표시하고 추천 응답 뒤 조리 순서를 별도로 요청한다', async () => {
    const recipeRequest = deferred<RecipeDto>()
    postMock.mockResolvedValueOnce(recommendation).mockReturnValueOnce(recipeRequest.promise)

    renderPage()

    expect(screen.getByLabelText('임박 재료')).toHaveTextContent('양파 · D-1')
    expect(screen.getByRole('status')).toHaveTextContent('메뉴를 추천하는 중이에요')

    expect(await screen.findByRole('heading', { name: '양파 달걀 덮밥' })).toBeInTheDocument()
    expect(postMock).toHaveBeenNthCalledWith(1, '/api/recommendations', {
      clientDate: '2026-04-07',
    })
    expect(postMock).toHaveBeenNthCalledWith(2, '/api/recipes', {
      recommendation,
    })
    expect(screen.getByText('사용 1개 · 현재 8개')).toBeInTheDocument()
    expect(screen.getByText('사용 0.5개 · 현재 4개')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('조리 순서를 만드는 중이에요')
    expect(screen.getByRole('button', { name: '요리했어요' })).toBeInTheDocument()

    recipeRequest.resolve(recipe)
    expect(await screen.findByText('달걀과 함께 볶아요.')).toBeInTheDocument()
  })

  it('조리 순서 실패 중에도 추천을 유지하고 조리 순서만 재시도한다', async () => {
    const user = userEvent.setup()
    postMock
      .mockResolvedValueOnce(recommendation)
      .mockRejectedValueOnce(
        new ApiError(502, 'GENERATION_FAILED', '조리 순서를 만들지 못했어요.', true),
      )
      .mockResolvedValueOnce(recipe)

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('조리 순서를 만들지 못했어요.')
    expect(screen.getByRole('heading', { name: '양파 달걀 덮밥' })).toBeInTheDocument()
    expect(screen.getByText('사용 1개 · 현재 8개')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '요리했어요' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '조리 순서 다시 시도' }))

    expect(await screen.findByText('양파를 썰어요.')).toBeInTheDocument()
    expect(postMock).toHaveBeenCalledTimes(3)
    expect(postMock).toHaveBeenLastCalledWith('/api/recipes', { recommendation })
  })

  it('다른 메뉴 요청에 직전 메뉴 이름을 제외하고 실패 시 같은 입력으로 재시도한다', async () => {
    const user = userEvent.setup()
    postMock
      .mockResolvedValueOnce(recommendation)
      .mockResolvedValueOnce(recipe)
      .mockRejectedValueOnce(
        new ApiError(502, 'GENERATION_FAILED', '다른 메뉴를 만들지 못했어요.', true),
      )
      .mockResolvedValueOnce({ ...recommendation, id: 'recommendation-2', menuName: '양파전' })
      .mockResolvedValueOnce({ steps: ['양파를 부쳐요.'] })

    renderPage()
    await screen.findByText('달걀과 함께 볶아요.')

    await user.click(screen.getByRole('button', { name: '다른 메뉴 추천' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('다른 메뉴를 만들지 못했어요.')
    expect(screen.getByRole('heading', { name: '양파 달걀 덮밥' })).toBeInTheDocument()
    expect(postMock).toHaveBeenNthCalledWith(3, '/api/recommendations', {
      clientDate: '2026-04-07',
      excludedMenuName: '양파 달걀 덮밥',
    })

    await user.click(screen.getByRole('button', { name: '메뉴 추천 다시 시도' }))

    expect(await screen.findByRole('heading', { name: '양파전' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('양파를 부쳐요.')).toBeInTheDocument())
    expect(postMock).toHaveBeenNthCalledWith(4, '/api/recommendations', {
      clientDate: '2026-04-07',
      excludedMenuName: '양파 달걀 덮밥',
    })
  })

  it('차감 성공 시 최신 재고를 반영하고 차감 수와 제거 품목을 알린다', async () => {
    const user = userEvent.setup()
    const updatedInventory: InventoryDto = {
      version: 4,
      items: [
        { ...currentInventory.items[0], quantity: 7 },
        { ...currentInventory.items[1], quantity: 3.5 },
      ],
    }
    postMock
      .mockResolvedValueOnce(recommendation)
      .mockResolvedValueOnce(recipe)
      .mockResolvedValueOnce({
        inventory: updatedInventory,
        deductedCount: 2,
        removedNames: ['대파'],
      })

    renderPage()
    await screen.findByText('달걀과 함께 볶아요.')

    await user.click(screen.getByRole('button', { name: '요리했어요' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('양파 8개 → 7개')
    expect(screen.getByRole('dialog')).toHaveTextContent('달걀 4개 → 3.5개')

    await user.click(screen.getByRole('button', { name: '재고에서 차감하기' }))

    await waitFor(() => expect(replaceInventoryMock).toHaveBeenCalledWith(updatedInventory))
    expect(showToastMock).toHaveBeenCalledWith(
      '2개 재료를 차감했어요. 냉장고에서 제거: 대파',
    )
    expect(postMock).toHaveBeenNthCalledWith(3, '/api/deductions?today=2026-04-07', {
      deductionRequestId: '323e4567-e89b-42d3-a456-426614174000',
      items: [
        { itemId: 'onion', quantity: 1 },
        { itemId: 'egg', quantity: 0.5 },
      ],
    })
  })
})
