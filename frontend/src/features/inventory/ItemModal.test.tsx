import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { InventoryItemDto } from '../../models/types'
import { ItemModal } from './ItemModal'

const item: InventoryItemDto = {
  id: '223e4567-e89b-42d3-a456-426614174000',
  name: '양파',
  quantity: 2,
  storageLocation: '실온',
  expirationDate: '2026-04-12',
  expirationEstimated: true,
}

describe('ItemModal', () => {
  it('등록 초안의 모든 필드를 수정하고 소비기한을 확정값으로 저장한다', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)

    render(
      <ItemModal
        item={item}
        mode="draft"
        onClose={vi.fn()}
        onDelete={vi.fn()}
        onSave={onSave}
      />,
    )

    const nameInput = screen.getByLabelText('품목명')
    await user.clear(nameInput)
    await user.type(nameInput, '대파')
    const quantityInput = screen.getByLabelText('수량 (개)')
    await user.clear(quantityInput)
    await user.type(quantityInput, '1.5')
    await user.selectOptions(screen.getByLabelText('보관 위치'), '냉장')
    const expirationInput = screen.getByLabelText('소비기한')
    await user.clear(expirationInput)
    await user.type(expirationInput, '2026-04-15')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(onSave).toHaveBeenCalledWith({
      ...item,
      name: '대파',
      quantity: 1.5,
      storageLocation: '냉장',
      expirationDate: '2026-04-15',
      expirationEstimated: false,
    })
  })

  it('등록 초안의 잘못된 수량에서는 오류를 표시하고 저장을 막는다', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()

    render(<ItemModal item={item} mode="draft" onClose={vi.fn()} onSave={onSave} />)

    const quantityInput = screen.getByLabelText('수량 (개)')
    await user.clear(quantityInput)
    await user.type(quantityInput, '0.75')

    expect(screen.getByText('수량은 0.5개 이상의 0.5개 단위로 입력해 주세요.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    expect(onSave).not.toHaveBeenCalled()
  })

  it('저장 재고의 0개 입력을 삭제 요청용 수정값으로 허용한다', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)

    render(<ItemModal item={item} mode="inventory" onClose={vi.fn()} onSave={onSave} />)

    const quantityInput = screen.getByLabelText('수량 (개)')
    await user.clear(quantityInput)
    await user.type(quantityInput, '0')

    expect(screen.getByText('수량이 0개이면 냉장고에서 삭제됩니다.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '저장' }))
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ quantity: 0 }))
  })

  it('저장 실패 시 수정값을 보존하고 같은 입력으로 재시도한다', async () => {
    const user = userEvent.setup()
    const onSave = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, 'STORAGE_ERROR', '저장에 실패했어요.', true))
      .mockResolvedValueOnce(undefined)

    render(<ItemModal item={item} mode="inventory" onClose={vi.fn()} onSave={onSave} />)

    const nameInput = screen.getByLabelText('품목명')
    await user.clear(nameInput)
    await user.type(nameInput, '적양파')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('저장에 실패했어요.')
    expect(nameInput).toHaveValue('적양파')

    await user.click(screen.getByRole('button', { name: '저장' }))
    expect(onSave).toHaveBeenCalledTimes(2)
    expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ name: '적양파' }))
  })

  it('요청 중에는 저장과 닫기를 비활성화해 중복 요청을 막는다', async () => {
    const user = userEvent.setup()
    let resolveSave: (() => void) | undefined
    const onSave = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveSave = resolve
        }),
    )

    render(<ItemModal item={item} mode="inventory" onClose={vi.fn()} onSave={onSave} />)

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(screen.getByRole('button', { name: '저장 중...' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '닫기' })).toBeDisabled()
    expect(onSave).toHaveBeenCalledOnce()

    resolveSave?.()
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
  })

  it('삭제 확인 후 삭제 콜백을 한 번 호출한다', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn().mockResolvedValue(undefined)

    render(
      <ItemModal
        item={item}
        mode="inventory"
        onClose={vi.fn()}
        onDelete={onDelete}
        onSave={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '품목 삭제' }))
    expect(screen.getByText('이 품목을 삭제할까요?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '삭제 확정' }))

    expect(onDelete).toHaveBeenCalledOnce()
  })
})
