import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type {
  DeductionResultDto,
  InventoryDto,
  MealRecommendationDto,
} from '../../models/types'
import { DeductionModal } from './DeductionModal'

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }))

vi.mock('../device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: { post: postMock }, deviceId: 'test-device' }),
}))

const inventory: InventoryDto = {
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
    {
      id: 'carrot',
      name: '당근',
      quantity: 3,
      storageLocation: '냉장',
      expirationDate: '2026-04-12',
      expirationEstimated: true,
    },
    {
      id: 'garlic',
      name: '마늘',
      quantity: 0.5,
      storageLocation: '냉장',
      expirationDate: '2026-04-20',
      expirationEstimated: true,
    },
  ],
}

const recommendation: MealRecommendationDto = {
  id: 'recommendation-1',
  menuName: '양파 달걀 덮밥',
  ingredients: [
    { itemId: 'onion', name: '양파', quantity: 1 },
    { itemId: 'egg', name: '달걀', quantity: 0.5 },
  ],
  seasonings: ['간장'],
}

const result: DeductionResultDto = {
  inventory: {
    version: 4,
    items: inventory.items.filter((item) => item.id !== 'egg'),
  },
  deductedCount: 2,
  removedNames: ['달걀'],
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

function renderModal(overrides?: {
  onCancel?: () => void
  onSuccess?: (nextResult: DeductionResultDto) => void
}) {
  const onCancel = overrides?.onCancel ?? vi.fn()
  const onSuccess = overrides?.onSuccess ?? vi.fn()
  render(
    <DeductionModal
      inventory={inventory}
      onCancel={onCancel}
      onSuccess={onSuccess}
      recommendation={recommendation}
      today="2026-04-07"
    />,
  )
  return { onCancel, onSuccess }
}

describe('DeductionModal', () => {
  beforeEach(() => {
    postMock.mockReset()
    vi.stubGlobal('crypto', { randomUUID: () => '323e4567-e89b-42d3-a456-426614174000' })
  })

  it('추천 재료를 모두 포함하고 수정·해제·다른 품목 추가 결과만 전송한다', async () => {
    const user = userEvent.setup()
    const { onSuccess } = renderModal()
    postMock.mockResolvedValue(result)

    expect(screen.getByRole('checkbox', { name: '양파' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: '달걀' })).toBeChecked()
    expect(screen.getByText('양파 8개 → 7개')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: '양파' }))
    const eggQuantity = screen.getByRole('spinbutton', { name: '달걀 사용량 (개)' })
    await user.clear(eggQuantity)
    await user.type(eggQuantity, '4')

    expect(screen.getByText('달걀 4개 → 0개')).toBeInTheDocument()
    expect(screen.getByText('차감 후 냉장고 목록에서 제거됩니다.')).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox', { name: '다른 재료 추가' }), 'carrot')
    await user.click(screen.getByRole('button', { name: '1개 사용으로 추가' }))
    expect(screen.getByText('당근 3개 → 2개')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '재고에서 차감하기' }))

    expect(postMock).toHaveBeenCalledWith('/api/deductions?today=2026-04-07', {
      deductionRequestId: '323e4567-e89b-42d3-a456-426614174000',
      items: [
        { itemId: 'egg', quantity: 4 },
        { itemId: 'carrot', quantity: 1 },
      ],
    })
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(result))
  })

  it('선택이 비어 있으면 확정을 막고 취소할 때 요청하지 않는다', async () => {
    const user = userEvent.setup()
    const { onCancel } = renderModal()

    await user.click(screen.getByRole('checkbox', { name: '양파' }))
    await user.click(screen.getByRole('checkbox', { name: '달걀' }))

    expect(screen.getByText('차감할 재료를 한 개 이상 선택해 주세요.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '재고에서 차감하기' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: '취소' }))
    expect(onCancel).toHaveBeenCalledOnce()
    expect(postMock).not.toHaveBeenCalled()
  })

  it('재고 초과 입력을 막고 실패 후 수정 초안과 같은 요청 ID로 재시도한다', async () => {
    const user = userEvent.setup()
    const firstRequest = deferred<DeductionResultDto>()
    postMock
      .mockReturnValueOnce(firstRequest.promise)
      .mockResolvedValueOnce(result)
    renderModal()

    const onionQuantity = screen.getByRole('spinbutton', { name: '양파 사용량 (개)' })
    await user.clear(onionQuantity)
    await user.type(onionQuantity, '8.5')
    expect(screen.getByText('0.5개 단위로 현재 재고 이하를 입력해 주세요.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '재고에서 차감하기' })).toBeDisabled()

    await user.clear(onionQuantity)
    await user.type(onionQuantity, '1.5')
    await user.click(screen.getByRole('checkbox', { name: '달걀' }))
    await user.click(screen.getByRole('button', { name: '재고에서 차감하기' }))

    expect(screen.getByRole('button', { name: '차감하는 중...' })).toBeDisabled()
    expect(postMock).toHaveBeenCalledTimes(1)
    firstRequest.reject(
      new ApiError(500, 'STORAGE_ERROR', '재고를 차감하지 못했어요.', true),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('재고를 차감하지 못했어요.')
    expect(onionQuantity).toHaveValue(1.5)

    await user.click(screen.getByRole('button', { name: '재고에서 차감하기' }))

    expect(postMock).toHaveBeenCalledTimes(2)
    expect(postMock.mock.calls[0][1]).toEqual(postMock.mock.calls[1][1])
  })
})
