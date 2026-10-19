import limbRender from '../assets/earth/limb-render.jpg'

interface EarthLimbProps {
  className?: string
  /** Which band of a portrait render survives inside a wide box. */
  position?: string
  /** Empty alt keeps it out of the accessibility tree, as decoration should be. */
  alt?: string
}

/**
 * The Earth as a still: a lit limb with the sun coming over the horizon.
 *
 * This is not a texture -- a perspective view of the horizon cannot be wrapped
 * onto a sphere -- so it only replaces `EarthGlobe` on the screens where the
 * planet had no points and no handlers. The console keeps the live globe
 * because that one is a chart. The side effect is that the public pages no
 * longer load the ~1.9MB three.js chunk to show you a horizon.
 */
export function EarthLimb({ className = '', position = '60% 40%', alt = '' }: EarthLimbProps) {
  return (
    <img
      src={limbRender}
      alt={alt}
      draggable={false}
      style={{ objectPosition: position }}
      className={`h-full w-full object-cover ${className}`}
    />
  )
}
