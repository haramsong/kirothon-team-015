import { Link } from 'react-router-dom'

import { getExpirationDisplay, sortInventoryItems } from '../../logic/date'
import type { InventoryItemDto } from '../../models/types'
import { useInventory } from './InventoryProvider'

function InventoryCard({ item, today }: { item: InventoryItemDto; today: string }) {
  const expiration = getExpirationDisplay(item.expirationDate, today)

  return (
    <li className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-bold text-stone-900">{item.name}</h2>
          <p className="mt-1 text-sm text-stone-600">
            {item.quantity}개 · {item.storageLocation}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-bold ${
            expiration.isExpired
              ? 'bg-red-100 text-red-700'
              : expiration.isExpiring
                ? 'bg-amber-100 text-amber-800'
                : 'bg-emerald-50 text-emerald-700'
          }`}
        >
          {expiration.dDayLabel}
        </span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-stone-600">
        <span>소비기한 {item.expirationDate}</span>
        {item.expirationEstimated && (
          <span className="rounded bg-stone-100 px-1.5 py-0.5 text-xs font-medium">예상</span>
        )}
        {expiration.isExpiring && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-bold text-amber-800">
            임박
          </span>
        )}
        {expiration.isExpired && (
          <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-bold text-red-700">
            지남
          </span>
        )}
      </div>
    </li>
  )
}

export function InventoryPage() {
  const { inventory, lastSuccessfulInventory, status, errorMessage, today, refreshInventory } =
    useInventory()
  const displayedInventory = inventory ?? lastSuccessfulInventory
  const items = displayedInventory
    ? sortInventoryItems(displayedInventory.items, today)
    : []
  const hasItems = items.length > 0
  const isInitialLoading = status === 'loading' && displayedInventory === null

  return (
    <main className="min-h-screen bg-stone-50 px-4 py-6 text-stone-900">
      <section className="mx-auto w-full md:max-w-[480px]">
        <header className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-emerald-700">나만의 냉장고</p>
            <h1 className="mt-1 text-2xl font-bold">냉장고</h1>
          </div>
          <Link
            className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-emerald-700"
            to="/register"
          >
            재료 등록
          </Link>
        </header>

        {status === 'error' && (
          <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
            <p className="text-sm font-medium text-red-800">{errorMessage}</p>
            <button
              className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-700"
              onClick={() => void refreshInventory()}
              type="button"
            >
              다시 불러오기
            </button>
          </div>
        )}

        {isInitialLoading && (
          <div className="mt-8 text-center" role="status">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-emerald-100 border-t-emerald-600" />
            <p className="mt-3 text-sm text-stone-600">냉장고를 불러오는 중이에요</p>
          </div>
        )}

        {!isInitialLoading && displayedInventory && !hasItems && (
          <div className="mt-8 rounded-2xl border border-dashed border-stone-300 bg-white px-5 py-10 text-center">
            <p className="text-lg font-bold">냉장고가 비어 있어요</p>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              영수증 사진 또는 주문내역 캡처를 올려 첫 재료를 등록해 보세요.
            </p>
            <Link
              className="mt-5 inline-block rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white"
              to="/register"
            >
              사진으로 재료 등록하기
            </Link>
          </div>
        )}

        {hasItems && (
          <ul className="mt-6 space-y-3" aria-label="냉장고 재고 목록">
            {items.map((item) => (
              <InventoryCard item={item} key={item.id} today={today} />
            ))}
          </ul>
        )}

        <nav className="mt-6 grid grid-cols-2 gap-3" aria-label="추천 메뉴">
          <Link
            aria-disabled={!hasItems}
            className={`rounded-xl px-4 py-3 text-center text-sm font-bold ${
              hasItems
                ? 'bg-stone-900 text-white hover:bg-stone-700'
                : 'pointer-events-none bg-stone-200 text-stone-400'
            }`}
            tabIndex={hasItems ? undefined : -1}
            to="/recipe"
          >
            한 끼 추천
          </Link>
          <Link
            aria-disabled={!hasItems}
            className={`rounded-xl px-4 py-3 text-center text-sm font-bold ${
              hasItems
                ? 'bg-white text-stone-900 ring-1 ring-stone-300 hover:bg-stone-100'
                : 'pointer-events-none bg-stone-100 text-stone-400 ring-1 ring-stone-200'
            }`}
            tabIndex={hasItems ? undefined : -1}
            to="/meal-plan"
          >
            3일 식단
          </Link>
        </nav>
      </section>
    </main>
  )
}
