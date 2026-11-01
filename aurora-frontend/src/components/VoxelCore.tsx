import { useEffect, useRef } from 'react'

interface Voxel {
  x: number
  y: number
  z: number
}

/**
 * The shell of a 5x5x5 lattice: the cubes that share a face with the
 * outside. Ninety-eight cells, enough for the translucent layered look of a
 * holographic core without turning every frame into a thousand rectangles.
 */
function shellVoxels(): Voxel[] {
  const voxels: Voxel[] = []
  for (let x = -2; x <= 2; x += 1) {
    for (let y = -2; y <= 2; y += 1) {
      for (let z = -2; z <= 2; z += 1) {
        if (Math.max(Math.abs(x), Math.abs(y), Math.abs(z)) === 2) {
          voxels.push({ x, y, z })
        }
      }
    }
  }
  return voxels
}

const VOXELS = shellVoxels()

interface VoxelCoreProps {
  size?: number
  className?: string
}

/**
 * The assistant's presence: a slowly turning cube of blue voxels, drawn on a
 * canvas rather than shipped as an image.
 *
 * It is original artwork built from primitives, so there is no stock or
 * licensed asset in the product. Under a reduced-motion preference it draws
 * one still frame instead of animating.
 */
export function VoxelCore({ size = 48, className = '' }: VoxelCoreProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.round(size * dpr)
    canvas.height = Math.round(size * dpr)
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const reduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const cx = size / 2
    const cy = size / 2
    const unit = Math.min(size, size) / 7.4
    const fov = 8
    const startedAt = performance.now()
    let raf = 0

    const draw = (now: number) => {
      const seconds = reduceMotion ? 1.4 : (now - startedAt) / 1000
      const settle = reduceMotion ? 1 : Math.min(1, seconds / 1.1)
      const push = 0.9 * Math.pow(1 - settle, 2)
      const angle = reduceMotion ? 0.65 : 0.65 + seconds * 0.4

      ctx.clearRect(0, 0, size, size)

      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.62)
      glow.addColorStop(0, 'rgba(80, 150, 255, 0.34)')
      glow.addColorStop(0.5, 'rgba(37, 99, 235, 0.13)')
      glow.addColorStop(1, 'rgba(5, 7, 12, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(0, 0, size, size)

      const cosY = Math.cos(angle * 0.9)
      const sinY = Math.sin(angle * 0.9)
      const cosX = Math.cos(angle * 0.45)
      const sinX = Math.sin(angle * 0.45)

      const projected = VOXELS.map((voxel, index) => {
        const norm = Math.hypot(voxel.x, voxel.y, voxel.z) || 1
        const sx = voxel.x + (voxel.x / norm) * push
        const sy = voxel.y + (voxel.y / norm) * push
        const sz = voxel.z + (voxel.z / norm) * push

        const x1 = sx * cosY + sz * sinY
        let z1 = -sx * sinY + sz * cosY
        const y1 = sy * cosX - z1 * sinX
        z1 = sy * sinX + z1 * cosX

        const perspective = fov / (fov + z1)
        return {
          x: cx + x1 * unit * perspective,
          y: cy + y1 * unit * perspective,
          size: unit * 0.52 * perspective,
          depth: z1,
          shimmer: reduceMotion ? 1 : 0.78 + 0.22 * Math.sin(seconds * 2.1 + index * 0.9),
        }
      })
      projected.sort((a, b) => b.depth - a.depth)

      for (const cube of projected) {
        const near = Math.max(0, Math.min(1, (fov - cube.depth) / (2 * fov)))
        const alpha = (0.18 + near * 0.62) * cube.shimmer
        const side = Math.max(0.6, cube.size)
        ctx.fillStyle = `rgba(59, 130, 246, ${alpha * 0.4})`
        ctx.strokeStyle = `rgba(191, 219, 254, ${alpha})`
        ctx.lineWidth = Math.max(0.4, side * 0.1)
        ctx.beginPath()
        ctx.rect(cube.x - side / 2, cube.y - side / 2, side, side)
        ctx.fill()
        ctx.stroke()
      }

      if (!reduceMotion) raf = requestAnimationFrame(draw)
    }

    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [size])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size }}
      className={className}
      aria-hidden="true"
    />
  )
}
