import fullLogo from './assets/reweave-full-logo-trimmed.png'
import fullLogoLight from './assets/reweave-full-logo-light.png'
import markLogo from './assets/reweave-mark-logo-trimmed.png'

const RATIOS = {
  full: 537 / 116,
  mark: 276 / 195,
}

export function ReweaveLogo({
  variant = 'full',
  height,
  size,
  light = false,
  className = '',
  ariaLabel = 'Reweave',
}) {
  const logoHeight = height ?? size ?? 32
  const isMark = variant === 'mark'
  const src = isMark ? markLogo : (light ? fullLogoLight : fullLogo)
  const width = Math.round(logoHeight * RATIOS[isMark ? 'mark' : 'full'])

  return (
    <img
      className={`reweave-logo reweave-logo--${isMark ? 'mark' : 'full'} ${className}`.trim()}
      src={src}
      width={width}
      height={logoHeight}
      alt={ariaLabel}
      style={{ width, height: logoHeight }}
      draggable="false"
    />
  )
}

export function ReweaveBadge(props) {
  return <ReweaveLogo variant="mark" {...props} />
}

export function ReweaveIcon(props) {
  return <ReweaveLogo variant="mark" {...props} />
}

export function ReweaveWordmark(props) {
  return <ReweaveLogo variant="full" {...props} />
}
