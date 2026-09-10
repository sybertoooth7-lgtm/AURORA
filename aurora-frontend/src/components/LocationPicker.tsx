import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIconUrl from 'leaflet/dist/images/marker-icon.png'
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png'

// Vite doesn't resolve Leaflet's default marker image paths the way its
// own CSS expects (a long-standing Leaflet + bundler issue), so the
// default pin renders as a broken image unless we point it at the
// bundled asset URLs ourselves.
const markerIcon = L.icon({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

interface LocationPickerProps {
  latitude: number
  longitude: number
  radiusKm: number
  onChange: (latitude: number, longitude: number) => void
}

/**
 * A plain Leaflet map (not react-leaflet) so we have direct access to the
 * map/marker/circle instances for imperative updates -- this widget needs
 * to react to both map clicks/drags AND the numeric lat/lon inputs typed
 * elsewhere on the form, which is awkward to keep in sync through
 * react-leaflet's declarative children.
 */
export function LocationPicker({ latitude, longitude, radiusKm, onChange }: LocationPickerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.Marker | null>(null)
  const circleRef = useRef<L.Circle | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  // Set up the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [latitude, longitude],
      zoom: 11,
      scrollWheelZoom: false,
    })
    mapRef.current = map

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map)

    const marker = L.marker([latitude, longitude], { icon: markerIcon, draggable: true }).addTo(map)
    markerRef.current = marker

    const circle = L.circle([latitude, longitude], {
      radius: radiusKm * 1000,
      color: '#2B3A67',
      fillColor: '#2B3A67',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map)
    circleRef.current = circle

    function setPosition(lat: number, lng: number) {
      marker.setLatLng([lat, lng])
      circle.setLatLng([lat, lng])
      onChangeRef.current(lat, lng)
    }

    map.on('click', (event: L.LeafletMouseEvent) => {
      setPosition(event.latlng.lat, event.latlng.lng)
    })
    marker.on('drag', () => {
      const pos = marker.getLatLng()
      circle.setLatLng(pos)
    })
    marker.on('dragend', () => {
      const pos = marker.getLatLng()
      onChangeRef.current(pos.lat, pos.lng)
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Keep the marker/circle in sync when the lat/lon/radius inputs change
  // from outside (typed directly into the number fields), without
  // fighting the map click/drag handlers above.
  useEffect(() => {
    const marker = markerRef.current
    const circle = circleRef.current
    if (!marker || !circle) return
    const current = marker.getLatLng()
    if (Math.abs(current.lat - latitude) > 1e-9 || Math.abs(current.lng - longitude) > 1e-9) {
      marker.setLatLng([latitude, longitude])
      circle.setLatLng([latitude, longitude])
    }
  }, [latitude, longitude])

  useEffect(() => {
    circleRef.current?.setRadius(radiusKm * 1000)
  }, [radiusKm])

  return <div ref={containerRef} className="h-full w-full" />
}
