import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import type { InventoryDto } from '../../models/types'
import { InventoryPage } from './InventoryPage'
import { useInventory } from './InventoryProvider'

vi.mock('./InventoryProvider', () => ({ useInventory: vi.fn() }))

const showToast = vi.fn()
vi.mock('../toast/ToastProvider', () => ({
  useToast: () => ({ showToast }),
}))

const mockedUseInventory = vi.mocked(useInventory)
const refreshInventory = vi.fn().mockResolvedValue(undefined)
const updateInventoryItem = vi.fn().mockResolvedValue(undefined)
const deleteInventoryItem = vi.fn().mockResolvedValue(undefined)

function inventory(items: InventoryDto['items']): InventoryDto {
  return { version: 1, items }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <InventoryPage />
    </MemoryRouter>,
  )
}

describe('InventoryPage', () => {
  beforeEach(() => {
    refreshInventory.mockClear()
    updateInventoryItem.mockReset().mockResolvedValue(undefined)
    deleteInventoryItem.mockReset().mockResolvedValue(undefined)
    showToast.mockClear()
  })

  it('재고를 소비기한 순으로 표시하고 상태 배지를 표시한다', () => {
    mockedUseInventory.mockReturnValue({
      inventory: inventory([
        {
          id: 'future',
          name: '감자',
          quantity: 2,
          storageLocation: '실온',
          expirationDate: '2026-04-12',
          expirationEstimated: false,
        },
        {
          id: 'expired',
          name: '두부',
          quantity: 1.5,
          storageLocation: '냉장',
          expirationDate: '2026-04-06',
          expirationEstimated: true,
        },
        {
          id: 'today',
          name: '양파',
          quantity: 8,
          storageLocation: '실온',
          expirationDate: '2026-04-07',
          expirationEstimated: false,
        },
      ]),
      lastSuccessfulInventory: null,
      status: 'success',
      errorMessage: null,
      today: '2026-04-07',
      refreshInventory,
      replaceInventory: vi.fn(),
      updateInventoryItem,
      deleteInventoryItem,
    })

    renderPage()

    const cards = screen.getAllByRole('listitem')
    expect(cards[0]).toHaveTextContent('두부')
    expect(cards[0]).toHaveTextContent('지남')
    expect(cards[0]).toHaveTextContent('예상')
    expect(cards[1]).toHaveTextContent('양파')
    expect(cards[1]).toHaveTextContent('D-day')
    expect(cards[1]).toHaveTextContent('임박')
    expect(cards[2]).toHaveTextContent('D-5')
    expect(screen.getByRole('link', { name: '한 끼 추천' })).toHaveAttribute(
      'aria-disabled',
      'false',
    )
  })

  it('빈 재고 안내와 비활성화된 추천 및 식단 링크를 표시한다', () => {
    mockedUseInventory.mockReturnValue({
      inventory: inventory([]),
      lastSuccessfulInventory: inventory([]),
      status: 'success',
      errorMessage: null,
      today: '2026-04-07',
      refreshInventory,
      replaceInventory: vi.fn(),
      updateInventoryItem,
      deleteInventoryItem,
    })

    renderPage()

    expect(screen.getByText('냉장고가 비어 있어요')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '한 끼 추천' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    expect(screen.getByRole('link', { name: '3일 식단' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
  })

  it('조회 오류에서도 마지막 성공 재고와 재시도 동작을 유지한다', async () => {
    const previous = inventory([
      {
        id: 'onion',
        name: '양파',
        quantity: 8,
        storageLocation: '실온',
        expirationDate: '2026-04-10',
        expirationEstimated: true,
      },
    ])
    mockedUseInventory.mockReturnValue({
      inventory: previous,
      lastSuccessfulInventory: previous,
      status: 'error',
      errorMessage: '냉장고를 불러오지 못했어요.',
      today: '2026-04-07',
      refreshInventory,
      replaceInventory: vi.fn(),
      updateInventoryItem,
      deleteInventoryItem,
    })

    renderPage()

    expect(screen.getByText('양파')).toBeInTheDocument()
    screen.getByRole('button', { name: '다시 불러오기' }).click()
    expect(refreshInventory).toHaveBeenCalledOnce()
  })

  it('첫 조회 중 로딩 상태와 한 열 반응형 영역을 표시한다', () => {
    mockedUseInventory.mockReturnValue({
      inventory: null,
      lastSuccessfulInventory: null,
      status: 'loading',
      errorMessage: null,
      today: '2026-04-07',
      refreshInventory,
      replaceInventory: vi.fn(),
      updateInventoryItem,
      deleteInventoryItem,
    })

    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent('냉장고를 불러오는 중이에요')
    expect(screen.getByRole('heading', { name: '냉장고' }).closest('section')).toHaveClass(
      'w-full',
      'md:max-w-[480px]',
    )
  })

  it('재고 카드에서 편집 모달을 열고 수정값을 InventoryProvider에 전달한다', async () => {
    const user = userEvent.setup()
    mockedUseInventory.mockReturnValue({
      inventory: inventory([
        {
          id: 'onion',
          name: '양파',
          quantity: 8,
          storageLocation: '실온',
          expirationDate: '2026-04-10',
          expirationEstimated: true,
        },
      ]),
      lastSuccessfulInventory: null,
      status: 'success',
      errorMessage: null,
      today: '2026-04-07',
      refreshInventory,
      replaceInventory: vi.fn(),
      updateInventoryItem,
      deleteInventoryItem,
    })

    renderPage()
    await user.click(screen.getByRole('button', { name: '양파 수정' }))

    const nameInput = screen.getByLabelText('품목명')
    await user.clear(nameInput)
    await user.type(nameInput, '적양파')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(updateInventoryItem).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'onion', name: '적양파' }),
    )
    expect(showToast).toHaveBeenCalledWith('적양파을(를) 수정했어요.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
