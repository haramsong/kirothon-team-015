import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { InventoryPage } from '../features/inventory/InventoryPage'
import { InventoryProvider } from '../features/inventory/InventoryProvider'
import { MealPlanPage } from '../features/meal-plan/MealPlanPage'
import { MealPlanProvider } from '../features/meal-plan/MealPlanProvider'
import { RecipePage } from '../features/recipe/RecipePage'
import { RegistrationPage } from '../features/registration/RegistrationPage'
import { ToastProvider } from '../features/toast/ToastProvider'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<InventoryPage />} path="/" />
      <Route element={<RegistrationPage />} path="/register" />
      <Route element={<RecipePage />} path="/recipe" />
      <Route element={<MealPlanPage />} path="/meal-plan" />
      <Route element={<Navigate replace to="/" />} path="*" />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <InventoryProvider>
          <MealPlanProvider>
            <AppRoutes />
          </MealPlanProvider>
        </InventoryProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
