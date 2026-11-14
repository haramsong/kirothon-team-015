import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ToastProvider, useToast } from './ToastProvider'

function ToastTrigger() {
  const { showToast } = useToast()
  return (
    <button onClick={() => showToast('재고 등록을 완료했어요.')} type="button">
      알림 표시
    </button>
  )
}

describe('ToastProvider', () => {
  it('처리 결과 토스트를 표시하고 닫는다', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )

    await user.click(screen.getByRole('button', { name: '알림 표시' }))
    expect(screen.getByRole('status')).toHaveTextContent('재고 등록을 완료했어요.')

    await user.click(screen.getByRole('button', { name: '알림 닫기' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
