export const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const
export const MAX_IMAGE_LONG_EDGE = 1568
export const MAX_JPEG_BYTES = 3_932_160
const MIN_IMAGE_LONG_EDGE = 640
const RESIZE_FACTOR = 0.85
const JPEG_QUALITIES = [0.9, 0.8, 0.7, 0.6, 0.5] as const

interface DecodedImage {
  width: number
  height: number
  source: CanvasImageSource
  close?: () => void
}

interface CanvasEncoder {
  draw: (source: CanvasImageSource, width: number, height: number) => void
  encodeJpeg: (quality: number) => Promise<Blob>
}

export interface ImageProcessorEnvironment {
  decode: (file: File) => Promise<DecodedImage>
  createEncoder: (width: number, height: number) => CanvasEncoder
}

export interface ProcessedImage {
  blob: Blob
  width: number
  height: number
}

export class ImageProcessingError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ImageProcessingError'
  }
}

export function isSupportedImage(file: Pick<File, 'type'>): boolean {
  return (SUPPORTED_IMAGE_TYPES as readonly string[]).includes(file.type)
}

export function calculateImageDimensions(
  width: number,
  height: number,
  maxLongEdge = MAX_IMAGE_LONG_EDGE,
): { width: number; height: number } {
  if (width <= 0 || height <= 0 || maxLongEdge <= 0) {
    throw new ImageProcessingError('이미지 크기를 확인할 수 없어요.')
  }

  const scale = Math.min(1, maxLongEdge / Math.max(width, height))
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  }
}

function createBrowserEnvironment(): ImageProcessorEnvironment {
  return {
    decode: async (file) => {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return {
        width: bitmap.width,
        height: bitmap.height,
        source: bitmap,
        close: () => bitmap.close(),
      }
    },
    createEncoder: (width, height) => {
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const context = canvas.getContext('2d')
      if (!context) {
        throw new ImageProcessingError('이미지를 변환할 수 없어요.')
      }

      return {
        draw: (source, drawWidth, drawHeight) => {
          context.drawImage(source, 0, 0, drawWidth, drawHeight)
        },
        encodeJpeg: (quality) =>
          new Promise<Blob>((resolve, reject) => {
            canvas.toBlob(
              (blob) => {
                if (blob) resolve(blob)
                else reject(new ImageProcessingError('JPEG 이미지를 만들 수 없어요.'))
              },
              'image/jpeg',
              quality,
            )
          }),
      }
    },
  }
}

export async function processImage(
  file: File,
  environment: ImageProcessorEnvironment = createBrowserEnvironment(),
): Promise<ProcessedImage> {
  if (!isSupportedImage(file)) {
    throw new ImageProcessingError('사진 파일만 올릴 수 있어요')
  }

  let decoded: DecodedImage | null = null
  try {
    decoded = await environment.decode(file)
    let dimensions = calculateImageDimensions(decoded.width, decoded.height)

    while (true) {
      const encoder = environment.createEncoder(dimensions.width, dimensions.height)
      encoder.draw(decoded.source, dimensions.width, dimensions.height)

      for (const quality of JPEG_QUALITIES) {
        const blob = await encoder.encodeJpeg(quality)
        if (blob.type === 'image/jpeg' && blob.size <= MAX_JPEG_BYTES) {
          return { blob, ...dimensions }
        }
      }

      const currentLongEdge = Math.max(dimensions.width, dimensions.height)
      if (currentLongEdge <= MIN_IMAGE_LONG_EDGE) break

      dimensions = calculateImageDimensions(
        dimensions.width,
        dimensions.height,
        Math.max(MIN_IMAGE_LONG_EDGE, Math.floor(currentLongEdge * RESIZE_FACTOR)),
      )
    }
  } catch (error) {
    if (error instanceof ImageProcessingError) throw error
    throw new ImageProcessingError('사진을 처리하지 못했어요. 다시 시도해 주세요.')
  } finally {
    decoded?.close?.()
  }

  throw new ImageProcessingError('사진 용량을 3.75MB 이하로 줄이지 못했어요.')
}
