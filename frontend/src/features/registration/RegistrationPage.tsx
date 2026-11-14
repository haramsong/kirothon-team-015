import { type ChangeEvent, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import type { InventoryDto, InventoryItemDto, RecognitionResultDto } from '../../models/types'
import { formatLocalDate } from '../../logic/date'
import { useDevice } from '../device/DeviceProvider'
import { ItemModal } from '../inventory/ItemModal'
import { useInventory } from '../inventory/InventoryProvider'
import { useToast } from '../toast/ToastProvider'
import {
  ImageProcessingError,
  isSupportedImage,
  type ProcessedImage,
  processImage,
} from './imageProcessor'

type RegistrationStatus = 'idle' | 'processing' | 'recognizing' | 'ready' | 'saving' | 'error'

interface BatchInventoryResponse {
  inventory: InventoryDto
  savedCount: number
}

function useObjectUrl(value: Blob | null): string | null {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!value) {
      setUrl(null)
      return
    }

    const nextUrl = URL.createObjectURL(value)
    setUrl(nextUrl)
    return () => URL.revokeObjectURL(nextUrl)
  }, [value])

  return url
}

function toMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof ImageProcessingError) {
    return error.message
  }
  return fallback
}

function createDraftItem(today: string): InventoryItemDto {
  return {
    id: crypto.randomUUID(),
    name: '',
    quantity: 1,
    storageLocation: '냉장',
    expirationDate: today,
    expirationEstimated: true,
  }
}

export function RegistrationPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { apiClient } = useDevice()
  const { lastSuccessfulInventory, replaceInventory, today } = useInventory()
  const { showToast } = useToast()
  const [status, setStatus] = useState<RegistrationStatus>('idle')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [processedImage, setProcessedImage] = useState<ProcessedImage | null>(null)
  const [recognition, setRecognition] = useState<RecognitionResultDto | null>(null)
  const [editingItem, setEditingItem] = useState<InventoryItemDto | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSaveConfirming, setIsSaveConfirming] = useState(false)
  const originalPreviewUrl = useObjectUrl(selectedFile)
  const processedPreviewUrl = useObjectUrl(processedImage?.blob ?? null)
  const isBusy = status === 'processing' || status === 'recognizing' || status === 'saving'

  async function recognizeImage(image: ProcessedImage) {
    setStatus('recognizing')
    setErrorMessage(null)
    const formData = new FormData()
    formData.append('image', image.blob, 'shopping-image.jpg')

    try {
      const result = await apiClient.post<RecognitionResultDto>('/api/recognitions', formData)
      setRecognition(result)
      setStatus('ready')
    } catch (error) {
      setStatus('error')
      setErrorMessage(toMessage(error, '사진에서 재료를 인식하지 못했어요.'))
    }
  }

  async function prepareAndRecognize(file: File) {
    setStatus('processing')
    setErrorMessage(null)
    setRecognition(null)
    setProcessedImage(null)
    setIsSaveConfirming(false)

    try {
      const processed = await processImage(file)
      setProcessedImage(processed)
      await recognizeImage(processed)
    } catch (error) {
      setStatus('error')
      setErrorMessage(toMessage(error, '사진을 처리하지 못했어요. 다시 시도해 주세요.'))
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || isBusy) return

    if (!isSupportedImage(file)) {
      setErrorMessage('사진 파일만 올릴 수 있어요')
      setStatus('error')
      return
    }

    setSelectedFile(file)
    void prepareAndRecognize(file)
  }

  function retrySameImage() {
    if (isBusy) return
    if (processedImage) {
      void recognizeImage(processedImage)
    } else if (selectedFile) {
      void prepareAndRecognize(selectedFile)
    }
  }

  function startDirectEntry() {
    if (isBusy) return
    setRecognition({
      purchaseDate: formatLocalDate(new Date()),
      purchaseDateSource: 'request_date',
      items: [],
    })
    setErrorMessage(null)
    setStatus('ready')
    setEditingItem(createDraftItem(today))
  }

  function updateDraftItem(item: InventoryItemDto) {
    setRecognition((current) => {
      if (!current) return current
      const exists = current.items.some((candidate) => candidate.id === item.id)
      return {
        ...current,
        items: exists
          ? current.items.map((candidate) => (candidate.id === item.id ? item : candidate))
          : [...current.items, item],
      }
    })
    setEditingItem(null)
    setIsSaveConfirming(false)
  }

  function deleteDraftItem(itemId: string) {
    setRecognition((current) =>
      current
        ? { ...current, items: current.items.filter((item) => item.id !== itemId) }
        : current,
    )
    setEditingItem(null)
    setIsSaveConfirming(false)
  }

  async function saveDraft() {
    if (!recognition?.items.length || !lastSuccessfulInventory || status === 'saving') return

    setStatus('saving')
    setErrorMessage(null)
    try {
      const result = await apiClient.post<BatchInventoryResponse>(
        `/api/inventory/items:batch?today=${encodeURIComponent(today)}`,
        {
          expectedVersion: lastSuccessfulInventory.version,
          items: recognition.items,
        },
      )
      replaceInventory(result.inventory)
      showToast(`${result.savedCount}개 재료를 냉장고에 저장했어요.`)
      navigate('/')
    } catch (error) {
      setStatus('ready')
      setErrorMessage(toMessage(error, '재료를 저장하지 못했어요. 다시 시도해 주세요.'))
      setIsSaveConfirming(true)
    }
  }

  return (
    <main className="min-h-screen bg-stone-50 px-4 py-6 text-stone-900">
      <section className="mx-auto w-full md:max-w-[480px]">
        <Link className="text-sm font-bold text-emerald-700" to="/">
          ← 냉장고로
        </Link>
        <h1 className="mt-5 text-2xl font-bold">재료 등록</h1>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          종이 영수증과 온라인 주문내역을 같은 방법으로 등록할 수 있어요.
        </p>

        <input
          accept="image/jpeg,image/png,image/webp"
          aria-label="영수증 사진 또는 주문내역 캡처 올리기"
          className="sr-only"
          disabled={isBusy}
          onChange={handleFileChange}
          ref={fileInputRef}
          type="file"
        />
        <button
          className="mt-5 w-full rounded-2xl border-2 border-dashed border-emerald-300 bg-emerald-50 px-5 py-8 font-bold text-emerald-800 disabled:border-stone-200 disabled:bg-stone-100 disabled:text-stone-400"
          disabled={isBusy}
          onClick={() => fileInputRef.current?.click()}
          type="button"
        >
          영수증 사진 또는 주문내역 캡처 올리기
        </button>

        {originalPreviewUrl && (
          <div className="mt-5 overflow-hidden rounded-2xl border border-stone-200 bg-white p-3">
            <img
              alt="선택한 장보기 이미지"
              className="max-h-64 w-full rounded-xl object-contain"
              src={processedPreviewUrl ?? originalPreviewUrl}
            />
            <p className="mt-2 truncate text-xs text-stone-500">{selectedFile?.name}</p>
            {processedImage && (
              <p className="mt-1 text-xs text-emerald-700">
                JPEG 변환 완료 · {processedImage.width}×{processedImage.height}px
              </p>
            )}
          </div>
        )}

        {(status === 'processing' || status === 'recognizing') && (
          <div className="mt-5 rounded-2xl bg-white p-5 text-center shadow-sm" role="status">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-emerald-100 border-t-emerald-600" />
            <p className="mt-3 text-sm font-semibold">
              {status === 'processing' ? '사진 처리 중이에요' : '재료 인식 중이에요'}
            </p>
          </div>
        )}

        {errorMessage && status === 'error' && (
          <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4" role="alert">
            <p className="text-sm font-medium text-red-800">{errorMessage}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedFile && (
                <button
                  className="rounded-lg bg-red-700 px-3 py-2 text-sm font-bold text-white"
                  disabled={isBusy}
                  onClick={retrySameImage}
                  type="button"
                >
                  같은 이미지 다시 시도
                </button>
              )}
              <button
                className="rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-bold text-red-700"
                disabled={isBusy}
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                다른 이미지 선택
              </button>
              <button
                className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-bold text-stone-700"
                disabled={isBusy}
                onClick={startDirectEntry}
                type="button"
              >
                직접 입력
              </button>
            </div>
          </div>
        )}

        {recognition && (
          <div className="mt-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">등록할 재료 확인</h2>
                <p className="mt-1 text-xs text-stone-500">수정한 뒤 냉장고에 저장해 주세요.</p>
              </div>
              <button
                className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-bold"
                disabled={isBusy}
                onClick={() => setEditingItem(createDraftItem(today))}
                type="button"
              >
                품목 추가
              </button>
            </div>

            {recognition.items.length === 0 ? (
              <div className="mt-4 rounded-2xl border border-dashed border-stone-300 bg-white p-6 text-center">
                <p className="font-bold">인식된 식재료가 없어요</p>
                <p className="mt-2 text-sm text-stone-600">품목을 직접 추가해 주세요.</p>
              </div>
            ) : (
              <ul className="mt-4 space-y-3" aria-label="등록할 재료 목록">
                {recognition.items.map((item) => (
                  <li className="rounded-2xl border border-stone-200 bg-white p-4" key={item.id}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-bold">{item.name}</p>
                        <p className="mt-1 text-sm text-stone-600">
                          {item.quantity}개 · {item.storageLocation}
                        </p>
                        <p className="mt-1 text-sm text-stone-600">
                          소비기한 {item.expirationDate}{' '}
                          {item.expirationEstimated && <span className="font-semibold">예상</span>}
                        </p>
                      </div>
                      <button
                        className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-bold"
                        disabled={isBusy}
                        onClick={() => setEditingItem(item)}
                        type="button"
                      >
                        수정
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {errorMessage && status === 'ready' && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3" role="alert">
                <p className="text-sm font-medium text-red-800">{errorMessage}</p>
              </div>
            )}

            {isSaveConfirming && recognition.items.length > 0 && (
              <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="font-bold text-emerald-900">
                  {recognition.items.length}개 재료를 냉장고에 저장할까요?
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    className="rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-bold"
                    disabled={isBusy}
                    onClick={() => setIsSaveConfirming(false)}
                    type="button"
                  >
                    취소
                  </button>
                  <button
                    className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-bold text-white disabled:bg-stone-300"
                    disabled={isBusy}
                    onClick={() => void saveDraft()}
                    type="button"
                  >
                    {status === 'saving' ? '저장 중...' : '저장 확정'}
                  </button>
                </div>
              </div>
            )}

            {!isSaveConfirming && (
              <button
                className="mt-5 w-full rounded-xl bg-emerald-600 px-4 py-3 font-bold text-white disabled:bg-stone-300"
                disabled={recognition.items.length === 0 || isBusy || !lastSuccessfulInventory}
                onClick={() => setIsSaveConfirming(true)}
                type="button"
              >
                냉장고에 저장
              </button>
            )}
            <button
              className="mt-2 w-full rounded-xl px-4 py-3 text-sm font-bold text-stone-600 disabled:text-stone-300"
              disabled={isBusy}
              onClick={() => navigate('/')}
              type="button"
            >
              등록 취소
            </button>
          </div>
        )}
      </section>

      {editingItem && (
        <ItemModal
          item={editingItem}
          key={editingItem.id}
          mode="draft"
          onClose={() => setEditingItem(null)}
          onDelete={() => deleteDraftItem(editingItem.id)}
          onSave={updateDraftItem}
        />
      )}
    </main>
  )
}
