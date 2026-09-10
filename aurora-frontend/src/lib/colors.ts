// Maps a 0-1 NDVI (or NDVI-derived severity) value onto the same
// healthy -> stress -> critical scale used throughout the UI, so the
// number and the color always agree with each other.

export function healthColor(ndvi: number): string {
  if (ndvi >= 0.5) return '#4F7942' // healthy
  if (ndvi >= 0.3) return '#B5502E' // stress
  return '#8C2F1B' // critical
}

export function severityColor(severity: number | null): { text: string; bg: string; label: string } {
  if (severity == null) return { text: '#4B5A54', bg: '#F3F5F0', label: 'No score' }
  if (severity < 0.35) return { text: '#4F7942', bg: '#DCE7D6', label: 'Normal' }
  if (severity < 0.7) return { text: '#B5502E', bg: '#F1DCCF', label: 'Warning' }
  return { text: '#8C2F1B', bg: '#EFD0C6', label: 'Critical' }
}

export function alertColor(alertType: 'info' | 'warning' | 'critical'): { text: string; bg: string } {
  switch (alertType) {
    case 'critical':
      return { text: '#8C2F1B', bg: '#EFD0C6' }
    case 'warning':
      return { text: '#B5502E', bg: '#F1DCCF' }
    default:
      return { text: '#2B3A67', bg: '#DCE7D6' }
  }
}
