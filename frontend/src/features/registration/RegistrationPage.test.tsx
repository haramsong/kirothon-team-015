import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { RecognitionResultDto } from '../../models/types'
import { RegistrationPage } from './RegistrationPage'

const { postMock, processImageMock, replaceInventoryMock, showToastMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  processImageMock: vi.fn(),
  replaceInventoryMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../device/DeviceProvider', () => ({
  useDevice: () => ({ apiClient: { post: postMock }, deviceId: 'test-device' }),
}))

vi.mock('../inventory/InventoryProvider', () => ({
  useInventory: () => ({
    lastSuccessfulInventory: { items: [], version: 0 },
    replaceInventory: replaceInventoryMock,
    today: '2026-04-07',
  }),
}))

vi.mock('../toast/ToastProvider', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('./imageProcessor', async () => {
  const actual = await vi.importActual<typeof import('./imageProcessor')>('./imageProcessor')
  return { ...actual, processImage: processImageMock }
})

const recognition: RecognitionResultDto = {
  purchaseDate: '2026-04-07',
  purchaseDateSource: 'detected',
  items: [
    {
      id: '223e4567-e89b-42d3-a456-426614174000',
      name: '양파',
      quantity: 2,
      storageLocation: '실온',
      expirationDate: '2026-04-12',
      expirationEstimated: true,
    },
  ],
}

function renderPage() {
  return render(
    <MemoryRouter>
      <RegistrationPage />
    </MemoryRouter>,
  )
}

describe('RegistrationPage', () => {
  beforeEach(() => {
    postMock.mockReset()
    processImageMock.mockReset()
    replaceInventoryMock.mockReset()
    showToastMock.mockReset()
    processImageMock.mockResolvedValue({
      blob: new Blob(['jpeg'], { type: 'image/jpeg' }),
      width: 1200,
      height: 800,
    })
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:preview'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
  })

  it('지원하지 않는 파일은 인식 요청 없이 지정 오류를 표시한다', async () => {
    const user = userEvent.setup({ applyAccept: false })
    renderPage()

    await user.upload(
      screen.getByLabelText('영수증 사진 또는 주문내역 캡처 올리기'),
      new File(['text'], 'order.txt', { type: 'text/plain' }),
    )

    expect(screen.getByRole('alert')).toHaveTextContent('사진 파일만 올릴 수 있어요')
    expect(processImageMock).not.toHaveBeenCalled()
    expect(postMock).not.toHaveBeenCalled()
  })

  it('한 장을 처리해 인식 결과를 표시하고 확인 후 batch 저장한다', async () => {
    const user = userEvent.setup()
    postMock
      .mockResolvedValueOnce(recognition)
      .mockResolvedValueOnce({
        inventory: { items: recognition.items, version: 1 },
        savedCount: 1,
      })
    renderPage()

    await user.upload(
      screen.getByLabelText('영수증 사진 또는 주문내역 캡처 올리기'),
      new File(['image'], 'receipt.png', { type: 'image/png' }),
    )

    expect(await screen.findByText('양파')).toBeInTheDocument()
    expect(screen.getByAltText('선택한 장보기 이미지')).toBeInTheDocument()
    expect(screen.getByText('JPEG 변환 완료 · 1200×800px')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '냉장고에 저장' }))
    expect(screen.getByText('1개 재료를 냉장고에 저장할까요?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '저장 확정' }))

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(2))
    expect(postMock).toHaveBeenLastCalledWith('/api/inventory/items:batch?today=2026-04-07', {
      expectedVersion: 0,
      items: recognition.items,
    })
    expect(replaceInventoryMock).toHaveBeenCalledWith({
      items: recognition.items,
      version: 1,
    })
    expect(showToastMock).toHaveBeenCalledWith('1개 재료를 냉장고에 저장했어요.')
  })

  it('인식 실패 시 원본과 처리 이미지를 유지하고 같은 이미지로 재시도한다', async () => {
    const user = userEvent.setup()
    postMock
      .mockRejectedValueOnce(new ApiError(502, 'RECOGNITION_FAILED', '인식에 실패했어요.', true))
      .mockResolvedValueOnce(recognition)
    renderPage()

    await user.upload(
      screen.getByLabelText('영수증 사진 또는 주문내역 캡처 올리기'),
      new File(['image'], 'order.webp', { type: 'image/webp' }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('인식에 실패했어요.')
    expect(screen.getByAltText('선택한 장보기 이미지')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '같은 이미지 다시 시도' }))

    expect(await screen.findByText('양파')).toBeInTheDocument()
    expect(processImageMock).toHaveBeenCalledOnce()
    expect(postMock).toHaveBeenCalledTimes(2)
  })

  it('빈 인식 결과에서 직접 품목을 추가하고 삭제할 수 있다', async () => {
    const user = userEvent.setup()
    postMock.mockResolvedValueOnce({ ...recognition, items: [] })
    renderPage()

    await user.upload(
      screen.getByLabelText('영수증 사진 또는 주문내역 캡처 올리기'),
      new File(['image'], 'empty.jpg', { type: 'image/jpeg' }),
    )

    expect(await screen.findByText('인식된 식재료가 없어요')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '냉장고에 저장' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: '품목 추가' }))
    await user.type(screen.getByLabelText('품목명'), '달걀')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(screen.getByText('달걀')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '수정' }))
    await user.click(screen.getByRole('button', { name: '품목 삭제' }))
    await user.click(screen.getByRole('button', { name: '삭제 확정' }))
    expect(screen.getByText('인식된 식재료가 없어요')).toBeInTheDocument()
  })

  it('batch 저장 실패 후 수정 초안과 저장 확인 상태를 유지해 재시도한다', async () => {
    const user = userEvent.setup()
    postMock
      .mockResolvedValueOnce(recognition)
      .mockRejectedValueOnce(new ApiError(500, 'STORAGE_ERROR', '저장에 실패했어요.', true))
      .mockResolvedValueOnce({
        inventory: { items: recognition.items, version: 1 },
        savedCount: 1,
      })
    renderPage()

    await user.upload(
      screen.getByLabelText('영수증 사진 또는 주문내역 캡처 올리기'),
      new File(['image'], 'receipt.jpg', { type: 'image/jpeg' }),
    )
    await screen.findByText('양파')
    await user.click(screen.getByRole('button', { name: '냉장고에 저장' }))
    await user.click(screen.getByRole('button', { name: '저장 확정' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('저장에 실패했어요.')
    expect(screen.getByText('양파')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '저장 확정' }))

    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(3))
  })
})
