import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { GlobeInstance } from 'globe.gl'
import dayTexture from '../assets/earth/earth-day.jpg'
import heightTexture from '../assets/earth/earth-height.jpg'
import spaceTexture from '../assets/earth/space.jpg'

export interface GlobePoint {
  id: string | number
  latitude: number
  longitude: number
  label?: string
  /** 0..1 NDVI severity, when the area has a scored finding. */
  severity?: number | null
  /** Used for coloring when there is no score yet. */
  state?: 'queued' | 'processing' | 'failed' | null
  monitored?: boolean
}

interface EarthGlobeProps {
  points: GlobePoint[]
  selectedId?: string | number | null
  onSelect?: (id: string | number) => void
  onHover?: (id: string | number | null) => void
  onPickLocation?: (latitude: number, longitude: number) => void
  autoRotate?: boolean
  initialAltitude?: number
  className?: string
  fallback?: ReactNode
}

// Mirrors the NDVI scale and status colors in index.css; the WebGL layer
// needs literal colors rather than CSS custom properties.
const SEVERITY_COLORS = ['#4F7942', '#8F7B2E', '#B5502E', '#8C2F1B']
const STATE_COLORS: Record<NonNullable<GlobePoint['state']>, string> = {
  queued: '#8A9199',
  processing: '#556099',
  failed: '#8C2F1B',
}

function pointColor(point: GlobePoint): string {
  if (point.severity !== null && point.severity !== undefined) {
    const index = Math.min(
      SEVERITY_COLORS.length - 1,
      Math.floor(point.severity * SEVERITY_COLORS.length),
    )
    return SEVERITY_COLORS[index]
  }
  if (point.state) return STATE_COLORS[point.state]
  return '#556099'
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

/**
 * The Earth as a lit, textured sphere instead of a flat projection.
 *
 * globe.gl is imported dynamically because three.js is most of that bundle and
 * the screens that never show the planet should not pay for it. With no WebGL
 * context the caller's `fallback` renders instead, so the screen still works.
 */
export function EarthGlobe({
  points,
  selectedId = null,
  onSelect,
  onHover,
  onPickLocation,
  autoRotate = true,
  initialAltitude = 2.4,
  className = '',
  fallback = null,
}: EarthGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const globeRef = useRef<GlobeInstance | null>(null)
  const observerRef = useRef<ResizeObserver | null>(null)
  const pointsRef = useRef(points)
  const selectedRef = useRef(selectedId)
  const handlersRef = useRef({ onSelect, onHover, onPickLocation })
  const [phase, setPhase] = useState<'loading' | 'ready' | 'unsupported'>('loading')

  pointsRef.current = points
  selectedRef.current = selectedId
  handlersRef.current = { onSelect, onHover, onPickLocation }

  useEffect(() => {
    if (!containerRef.current) return
    if (!webglAvailable()) {
      setPhase('unsupported')
      return
    }

    let cancelled = false

    import('globe.gl')
      .then(({ default: Globe }) => {
        const host = containerRef.current
        if (cancelled || !host) return

        const globe = new Globe(host, { rendererConfig: { antialias: true } })
          .width(host.clientWidth)
          .height(host.clientHeight)
          .globeImageUrl(dayTexture)
          .bumpImageUrl(heightTexture)
          .backgroundImageUrl(spaceTexture)
          .showAtmosphere(true)
          .atmosphereColor('#7FA8C9')
          .atmosphereAltitude(0.16)
          .pointLat('latitude')
          .pointLng('longitude')
          .pointColor((d: object) => pointColor(d as GlobePoint))
          .pointAltitude(() => 0.06)
          .pointRadius(0.62)
          .ringLat('latitude')
          .ringLng('longitude')
          .ringColor(() => (t: number) => `rgba(127,168,201,${Math.max(0, 0.5 * (1 - t))})`)
          .ringMaxRadius(3.6)
          .ringPropagationSpeed(1.3)
          .ringRepeatPeriod(1600)
          .labelText('label')
          .labelSize(1.6)
          .labelDotRadius(0)
          .labelColor('#F3F5F0')
          .labelResolution(3)
          .labelAltitude(0.03)
          .onPointClick((point: object) => {
            handlersRef.current.onSelect?.((point as GlobePoint).id)
          })
          .onPointHover((point: object | null) => {
            handlersRef.current.onHover?.(point ? (point as GlobePoint).id : null)
            host.style.cursor = point ? 'pointer' : 'auto'
          })

        globeRef.current = globe
        writeLayers(globe, pointsRef.current, selectedRef.current)
        globe.pointOfView({ lat: 8, lng: 34, altitude: initialAltitude }, 0)
        setPhase('ready')

        observerRef.current = new ResizeObserver(() => {
          const h = containerRef.current
          if (!h) return
          globe.width(h.clientWidth).height(h.clientHeight)
        })
        observerRef.current.observe(host)
      })
      .catch(() => {
        if (!cancelled) setPhase('unsupported')
      })

    return () => {
      cancelled = true
      observerRef.current?.disconnect()
      observerRef.current = null
      globeRef.current?._destructor()
      globeRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (phase === 'ready' && globeRef.current) {
      writeLayers(globeRef.current, points, selectedId)
    }
  }, [phase, points, selectedId])

  useEffect(() => {
    const globe = globeRef.current
    if (phase !== 'ready' || !globe) return
    const controls = globe.controls()
    controls.autoRotate = autoRotate
    controls.autoRotateSpeed = 0.4
    controls.enableDamping = true
    controls.dampingFactor = 0.08
  }, [phase, autoRotate])

  // Fly to a selection only when the selection changes, so hovering or a
  // background refresh never drags the camera around.
  useEffect(() => {
    const globe = globeRef.current
    if (phase !== 'ready' || selectedId === null || !globe) return
    const focus = points.find((point) => point.id === selectedId)
    if (focus) globe.pointOfView({ lat: focus.latitude, lng: focus.longitude, altitude: 1.6 }, 900)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, selectedId])

  useEffect(() => {
    const globe = globeRef.current
    if (phase !== 'ready' || !onPickLocation || !globe) return
    globe.onGlobeClick((coords) => {
      if (coords) onPickLocation(coords.lat, coords.lng)
    })
  }, [phase, onPickLocation])

  if (phase === 'unsupported') {
    return <div className={className}>{fallback}</div>
  }

  return (
    <div className={`relative ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      {phase === 'loading' && (
        <div className="font-tabular absolute inset-0 flex items-center justify-center text-[0.7rem] tracking-[0.22em] text-[var(--color-orbit-soft)] uppercase">
          Acquiring signal
        </div>
      )}
    </div>
  )
}

function writeLayers(globe: GlobeInstance, points: GlobePoint[], selectedId: string | number | null) {
  globe
    .pointsData(points)
    .ringsData(points.filter((point) => point.monitored))
    .labelsData(points.filter((point) => point.id === selectedId))
}
