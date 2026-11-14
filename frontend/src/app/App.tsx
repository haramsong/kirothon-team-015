import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'

import { InventoryPage } from '../features/inventory/InventoryPage'
import { InventoryProvider } from '../features/inventory/InventoryProvider'
import { ToastProvider } from '../features/toast/ToastProvider'

interface PlaceholderPageProps {
  title: string
  description: string
}

function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <main className="min-h-screen bg-stone-50 px-4 py-6 text-stone-900">
      <section className="mx-auto w-full md:max-w-[480px]">
        <Link className="text-sm font-bold text-emerald-700" to="/">
          ← 냉장고로
        </Link>
        <h1 className="mt-5 text-2xl font-bold">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-stone-600">{description}</p>
      </section>
    </main>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<InventoryPage />} path="/" />
      <Route
        element={
          <PlaceholderPage
            description="영수증 사진 또는 주문내역 캡처로 재료를 등록할 수 있습니다."
            title="재료 등록"
          />
        }
        path="/register"
      />
      <Route
        element={
          <PlaceholderPage
            description="현재 냉장고 재료로 만들 수 있는 한 끼를 추천합니다."
            title="한 끼 추천"
          />
        }
        path="/recipe"
      />
      <Route
        element={
          <PlaceholderPage
            description="임박한 재료를 먼저 사용하는 3일 식단을 준비합니다."
            title="3일 식단"
          />
        }
        path="/meal-plan"
      />
      <Route element={<Navigate replace to="/" />} path="*" />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <InventoryProvider>
          <AppRoutes />
        </InventoryProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
