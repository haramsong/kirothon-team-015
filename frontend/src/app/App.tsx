import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom'

import { InventoryPage } from '../features/inventory/InventoryPage'
import { InventoryProvider } from '../features/inventory/InventoryProvider'
import { RecipePage } from '../features/recipe/RecipePage'
import { RegistrationPage } from '../features/registration/RegistrationPage'
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
      <Route element={<RegistrationPage />} path="/register" />
      <Route element={<RecipePage />} path="/recipe" />
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
