import { useId } from 'react'

/** The Your Call mark: a football wearing a commentator's headset. The ball takes the text colour
 * (currentColor); the headset takes --logo-accent, which follows the viewer's club when themed. */
export function Logo({ size = 32 }: { size?: number }) {
  const clip = `logo-ball-${useId()}`
  const accent = 'var(--logo-accent, #22c55e)'
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" className="logo">
      <defs>
        <clipPath id={clip}><circle cx="32" cy="35" r="15" /></clipPath>
      </defs>
      {/* the ball: five edge patches cut by the outline, seams, the centre panel */}
      <g clipPath={`url(#${clip})`} fill="currentColor">
        <polygon points="32,24.2 27.72,21.09 29.35,16.06 34.65,16.06 36.28,21.09" />
        <polygon points="42.27,31.66 43.91,26.63 49.2,26.63 50.83,31.66 46.55,34.77" />
        <polygon points="38.35,43.74 43.64,43.74 45.27,48.77 40.99,51.88 36.71,48.77" />
        <polygon points="25.65,43.74 27.29,48.77 23.01,51.88 18.73,48.77 20.36,43.74" />
        <polygon points="21.73,31.66 17.45,34.77 13.17,31.66 14.8,26.63 20.09,26.63" />
      </g>
      <g stroke="currentColor" strokeWidth="2.08" strokeLinecap="round">
        <line x1="32" y1="29.9" x2="32" y2="23.3" />
        <line x1="36.85" y1="33.42" x2="43.13" y2="31.38" />
        <line x1="35" y1="39.13" x2="38.88" y2="44.47" />
        <line x1="29" y1="39.13" x2="25.12" y2="44.47" />
        <line x1="27.15" y1="33.42" x2="20.87" y2="31.38" />
      </g>
      <polygon points="32,29.9 36.85,33.42 35,39.13 29,39.13 27.15,33.42" fill="currentColor"
        stroke="currentColor" strokeWidth="1.56" strokeLinejoin="round" />
      <circle cx="32" cy="35" r="15" fill="none" stroke="currentColor" strokeWidth="2.6" />
      {/* the headset: band, ear cups, mic boom */}
      <path d="M12.5 33 A19.5 19.5 0 0 1 51.5 33" fill="none" stroke={accent} strokeWidth="4" strokeLinecap="round" />
      <rect x="7" y="28" width="9" height="15" rx="4" fill={accent} />
      <rect x="48" y="28" width="9" height="15" rx="4" fill={accent} />
      <path d="M11.5 43 Q11.5 54 22 54" fill="none" stroke={accent} strokeWidth="3" strokeLinecap="round" />
      <rect x="21" y="50.5" width="9" height="7" rx="3.5" fill={accent} />
    </svg>
  )
}
