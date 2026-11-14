export type StorageLocation = '냉장' | '냉동' | '실온'

export interface ApiSuccess<T> {
  data: T
  requestId: string
}

export interface ApiErrorBody {
  code: string
  message: string
  retryable: boolean
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody
  requestId: string
}

export interface InventoryItemDto {
  id: string
  name: string
  quantity: number
  storageLocation: StorageLocation
  expirationDate: string
  expirationEstimated: boolean
}

export interface InventoryDto {
  items: InventoryItemDto[]
  version: number
}

export interface RecognitionResultDto {
  purchaseDate: string
  purchaseDateSource: 'detected' | 'request_date'
  items: InventoryItemDto[]
}

export interface MealIngredientDto {
  itemId: string
  name: string
  quantity: number
}

export interface MealRecommendationDto {
  id: string
  menuName: string
  ingredients: MealIngredientDto[]
  seasonings: string[]
}

export interface RecipeDto {
  steps: string[]
}

export interface MealPlanMealDto {
  id: string
  day: 1 | 2 | 3
  slot: '점심' | '저녁'
  recommendation: MealRecommendationDto
}

export interface MealPlanDto {
  id: string
  inventoryVersion: number
  meals: MealPlanMealDto[]
}

export interface DeductionItemInput {
  itemId: string
  quantity: number
}

export interface DeductionRequestDto {
  deductionRequestId: string
  items: DeductionItemInput[]
}
