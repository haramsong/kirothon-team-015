import { vi } from 'vitest'

import {
  calculateImageDimensions,
  ImageProcessingError,
  MAX_JPEG_BYTES,
  processImage,
} from './imageProcessor'

describe('imageProcessor', () => {
  it('긴 변을 1568픽셀로 제한하면서 종횡비를 유지한다', () => {
    expect(calculateImageDimensions(4000, 2000)).toEqual({ width: 1568, height: 784 })
    expect(calculateImageDimensions(800, 1200)).toEqual({ width: 800, height: 1200 })
  })

  it('EXIF 방향이 반영된 디코딩 크기로 JPEG를 생성하고 자원을 해제한다', async () => {
    const close = vi.fn()
    const draw = vi.fn()
    const encodeJpeg = vi.fn().mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' }))
    const environment = {
      decode: vi.fn().mockResolvedValue({
        width: 1200,
        height: 2400,
        source: {} as CanvasImageSource,
        close,
      }),
      createEncoder: vi.fn().mockReturnValue({ draw, encodeJpeg }),
    }
    const file = new File(['source'], 'receipt.png', { type: 'image/png' })

    const result = await processImage(file, environment)

    expect(result).toMatchObject({ width: 784, height: 1568 })
    expect(result.blob.type).toBe('image/jpeg')
    expect(draw).toHaveBeenCalledWith(expect.anything(), 784, 1568)
    expect(encodeJpeg).toHaveBeenCalledWith(0.9)
    expect(close).toHaveBeenCalledOnce()
  })

  it('품질을 낮추고 크기를 줄여도 제한을 넘으면 전처리 오류를 반환한다', async () => {
    const oversizedJpeg = new Blob([new Uint8Array(MAX_JPEG_BYTES + 1)], {
      type: 'image/jpeg',
    })
    const environment = {
      decode: vi.fn().mockResolvedValue({
        width: 640,
        height: 320,
        source: {} as CanvasImageSource,
      }),
      createEncoder: vi.fn().mockReturnValue({
        draw: vi.fn(),
        encodeJpeg: vi.fn().mockResolvedValue(oversizedJpeg),
      }),
    }

    await expect(
      processImage(new File(['source'], 'receipt.webp', { type: 'image/webp' }), environment),
    ).rejects.toEqual(
      new ImageProcessingError('사진 용량을 3.75MB 이하로 줄이지 못했어요.'),
    )
  })
})
