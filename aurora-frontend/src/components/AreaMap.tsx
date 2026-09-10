import { Circle, MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { healthColor } from '../lib/colors'

interface AreaMapProps {
  latitude: number
  longitude: number
  radiusKm: number
  /** NDVI (0-1) or change score used to color the area of interest. Omit for a neutral outline. */
  ndvi?: number | null
}

export function AreaMap({ latitude, longitude, radiusKm, ndvi }: AreaMapProps) {
  const color = ndvi == null ? '#556099' : healthColor(ndvi)

  return (
    <MapContainer
      center={[latitude, longitude]}
      zoom={12}
      scrollWheelZoom={false}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle
        center={[latitude, longitude]}
        radius={radiusKm * 1000}
        pathOptions={{ color, fillColor: color, fillOpacity: 0.18, weight: 2 }}
      />
    </MapContainer>
  )
}
