import type { InventoryItemDto } from '../models/types'

export interface ExpirationDisplay {
  dayDifference: number
  dDayLabel: string
  isExpired: boolean
  isExpiring: boolean
}

function toCalendarOrdinal(value: string): number {
  const [year, month, day] = value.split('-').map(Number)
  return Math.floor(Date.UTC(year, month - 1, day) / 86_400_000)
}

export function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function getExpirationDisplay(
  expirationDate: string,
  today: string,
): ExpirationDisplay {
  const dayDifference = toCalendarOrdinal(expirationDate) - toCalendarOrdinal(today)

  return {
    dayDifference,
    dDayLabel: dayDifference < 0 ? '지남' : dayDifference === 0 ? 'D-day' : `D-${dayDifference}`,
    isExpired: dayDifference < 0,
    isExpiring: dayDifference >= 0 && dayDifference <= 3,
  }
}

export function sortInventoryItems(
  items: readonly InventoryItemDto[],
  today: string,
): InventoryItemDto[] {
  return [...items].sort((left, right) => {
    const leftExpired = getExpirationDisplay(left.expirationDate, today).isExpired
    const rightExpired = getExpirationDisplay(right.expirationDate, today).isExpired

    if (leftExpired !== rightExpired) return leftExpired ? -1 : 1

    return (
      left.expirationDate.localeCompare(right.expirationDate) ||
      left.name.localeCompare(right.name, 'ko') ||
      left.id.localeCompare(right.id)
    )
  })
}
