import type { InventoryItemDto } from '../models/types'
import { formatLocalDate, getExpirationDisplay, sortInventoryItems } from './date'

function item(id: string, name: string, expirationDate: string): InventoryItemDto {
  return {
    id,
    name,
    quantity: 1,
    storageLocation: '냉장',
    expirationDate,
    expirationEstimated: false,
  }
}

describe('소비기한 날짜 로직', () => {
  it('현지 날짜를 YYYY-MM-DD 형식으로 만든다', () => {
    expect(formatLocalDate(new Date(2026, 3, 7, 23, 30))).toBe('2026-04-07')
  })

  it('지남, D-day, D-n과 임박 여부를 구분한다', () => {
    expect(getExpirationDisplay('2026-04-06', '2026-04-07')).toMatchObject({
      dDayLabel: '지남',
      isExpired: true,
      isExpiring: false,
    })
    expect(getExpirationDisplay('2026-04-07', '2026-04-07')).toMatchObject({
      dDayLabel: 'D-day',
      isExpiring: true,
    })
    expect(getExpirationDisplay('2026-04-10', '2026-04-07')).toMatchObject({
      dDayLabel: 'D-3',
      isExpiring: true,
    })
    expect(getExpirationDisplay('2026-04-11', '2026-04-07')).toMatchObject({
      dDayLabel: 'D-4',
      isExpiring: false,
    })
  })

  it('지난 품목을 먼저 두고 각 그룹을 소비기한 오름차순으로 정렬한다', () => {
    const sorted = sortInventoryItems(
      [
        item('future-2', '감자', '2026-04-10'),
        item('expired-2', '대파', '2026-04-06'),
        item('future-1', '양파', '2026-04-08'),
        item('expired-1', '두부', '2026-04-05'),
      ],
      '2026-04-07',
    )

    expect(sorted.map(({ id }) => id)).toEqual([
      'expired-1',
      'expired-2',
      'future-1',
      'future-2',
    ])
  })
})
