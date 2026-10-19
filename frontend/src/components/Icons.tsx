/** A small set of line icons, drawn in code (no icon font, no emoji): they inherit the text colour. */
type IconProps = { size?: number; className?: string; title?: string }

function Svg({ size = 18, className, title, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" className={className} role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true} aria-label={title}>
      {children}
    </svg>
  )
}

export const BallIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5l3.4 2.5-1.3 4h-4.2l-1.3-4z" fill="currentColor" stroke="none" />
    <path d="M12 3v4.5M20.5 10l-5.1 0M17.5 19l-3.4-5M6.5 19l3.4-5M3.5 10l5.1 0" />
  </Svg>
)

export const CardIcon = ({ color, ...p }: IconProps & { color: 'yellow' | 'red' }) => (
  <Svg {...p}>
    <rect x="7" y="3.5" width="10" height="17" rx="1.5" fill={color === 'red' ? '#ef4444' : '#facc15'} stroke="none"
      transform="rotate(8 12 12)" />
  </Svg>
)

export const WhistleIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 11h9l3-3h4v4a6 6 0 1 1-12 0" />
    <circle cx="13" cy="15" r="1.5" />
  </Svg>
)

export const FlagIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 21V4" />
    <path d="M6 4h11l-2.5 4L17 12H6" fill="currentColor" fillOpacity="0.25" />
  </Svg>
)

export const SwapIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 4v14M3.5 7.5L7 4l3.5 3.5M17 20V6M13.5 16.5L17 20l3.5-3.5" />
  </Svg>
)

export const TargetIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="4.5" />
    <circle cx="12" cy="12" r="1" fill="currentColor" />
  </Svg>
)

export const ClockIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Svg>
)

export const MicIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" />
  </Svg>
)

export const SpeakerIcon = ({ muted, ...p }: IconProps & { muted?: boolean }) => (
  <Svg {...p}>
    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" fillOpacity="0.2" />
    {muted ? <path d="M16 9.5l5 5M21 9.5l-5 5" /> : <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />}
  </Svg>
)

export const PlayIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" />
  </Svg>
)

export const RestartIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5" />
  </Svg>
)
