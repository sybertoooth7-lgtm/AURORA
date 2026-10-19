import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export interface FieldVertex {
  lat: number
  lng: number
}

interface FieldBoundaryMapProps {
  vertices: FieldVertex[]
  /** Called with every map click so the page can append a ring vertex. */
  onAddVertex: (lat: number, lng: number) => void
}

/**
 * The crop endpoints take a boundary polygon, not a point and a radius, so the
 * survey area has to be drawn rather than typed. Plain Leaflet (like
 * LocationPicker) because the ring is rebuilt on every click.
 */
export function FieldBoundaryMap({ vertices, onAddVertex }: FieldBoundaryMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)
  const onAddVertexRef = useRef(onAddVertex)
  onAddVertexRef.current = onAddVertex

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [36.8219, -1.2921],
      zoom: 12,
      scrollWheelZoom: false,
    })
    mapRef.current = map
    layerRef.current = L.layerGroup().addTo(map)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)

    map.on('click', (event: L.LeafletMouseEvent) => {
      onAddVertexRef.current(event.latlng.lat, event.latlng.lng)
    })

    return () => {
      map.remove()
      mapRef.current = null
      layerRef.current = null
    }
  }, [])

  useEffect(() => {
    const layer = layerRef.current
    const map = mapRef.current
    if (!layer || !map) return

    layer.clearLayers()
    if (vertices.length === 0) return

    const points = vertices.map((v) => [v.lat, v.lng] as [number, number])
    if (points.length >= 3) {
      L.polygon(points, {
        color: '#2B3A67',
        fillColor: '#4F7942',
        fillOpacity: 0.18,
        weight: 2,
      }).addTo(layer)
    } else {
      L.polyline(points, { color: '#2B3A67', weight: 2, dashArray: '4 4' }).addTo(layer)
    }
    points.forEach((point, index) => {
      L.circleMarker(point, {
        radius: 5,
        color: '#2B3A67',
        fillColor: index === 0 ? '#B5502E' : '#2B3A67',
        fillOpacity: 1,
      }).addTo(layer)
    })
    map.fitBounds(L.latLngBounds(points).pad(0.35))
  }, [vertices])

  return <div ref={containerRef} className="h-full w-full" />
}

/** Convert drawn vertices into the GeoJSON ring the crop endpoints expect. */
export function toFieldBoundary(vertices: FieldVertex[]) {
  if (vertices.length < 3) return null
  const ring = vertices.map((v) => [round6(v.lng), round6(v.lat)])
  ring.push(ring[0])
  return { type: 'Polygon' as const, coordinates: [ring] }
}

// Leaflet reports ~15 decimals; the backend caps a ring at 250 vertices and a
// survey radius is not finer than a Sentinel pixel, so trimming keeps the
// payload readable without changing the field.
function round6(value: number): number {
  return Math.round(value * 1e6) / 1e6
}
