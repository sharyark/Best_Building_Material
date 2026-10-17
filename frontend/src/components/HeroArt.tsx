import type { CSSProperties } from 'react'

/** Decorative construction scene (sand and gravel heaps, a dump truck, a brick pattern). Pure SVG: no downloads. */
export function HeroArt({ style }: { style?: CSSProperties }) {
  return (
    <svg
      viewBox="0 0 640 240"
      preserveAspectRatio="xMaxYMax slice"
      aria-hidden="true"
      className="hero-art"
      style={{ position: 'absolute', right: 0, bottom: 0, height: '100%', width: 'auto', maxWidth: '70%', ...style }}
    >
      <defs>
        <pattern id="bricks" width="48" height="24" patternUnits="userSpaceOnUse">
          <rect width="48" height="24" fill="none" />
          <path d="M0 0h48M0 12h48M0 24h48M24 0v12M0 12v12M48 12v12" stroke="#fff" strokeOpacity=".10" strokeWidth="1.5" fill="none" />
        </pattern>
        <linearGradient id="sand" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f0cf8f" />
          <stop offset="1" stopColor="#d4a85a" />
        </linearGradient>
        <linearGradient id="gravel" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#b9c2cc" />
          <stop offset="1" stopColor="#8d99a6" />
        </linearGradient>
      </defs>
      <rect x="250" y="0" width="390" height="240" fill="url(#bricks)" />
      {/* material heaps */}
      <path d="M300 240 L395 120 Q410 104 425 120 L520 240Z" fill="url(#sand)" opacity=".95" />
      <path d="M470 240 L545 150 Q558 136 572 150 L640 240Z" fill="url(#gravel)" opacity=".95" />
      <path d="M215 240 L275 170 Q285 160 296 170 L350 240Z" fill="#c98f4f" opacity=".9" />
      {/* dump truck */}
      <g transform="translate(40 96)" fill="#fff" fillOpacity=".92">
        <path d="M0 70 L12 22 H60 V70Z" />
        <path d="M14 28 H52 V50 H8Z" fill="#1f4e79" fillOpacity=".55" />
        <path d="M66 70 V34 L92 12 H196 L184 70Z" />
        <rect x="0" y="68" width="200" height="12" rx="3" fillOpacity=".75" />
        <circle cx="36" cy="84" r="15" fill="#10263b" />
        <circle cx="36" cy="84" r="6" fill="#9fb3c8" />
        <circle cx="150" cy="84" r="15" fill="#10263b" />
        <circle cx="150" cy="84" r="6" fill="#9fb3c8" />
        <circle cx="176" cy="84" r="15" fill="#10263b" />
        <circle cx="176" cy="84" r="6" fill="#9fb3c8" />
      </g>
      <rect x="0" y="236" width="640" height="4" fill="#fff" fillOpacity=".25" />
    </svg>
  )
}
