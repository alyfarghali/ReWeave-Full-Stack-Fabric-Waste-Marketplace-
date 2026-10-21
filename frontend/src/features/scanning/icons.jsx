// Inline stroke icons for the factory UI (1.6px stroke, currentColor).

function svgProps() {
  return {
    width: '1em',
    height: '1em',
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }
}

export function IconCamera() {
  return (
    <svg {...svgProps()}>
      <path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2L9 5h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v8A1.5 1.5 0 0 1 18.5 18h-13A1.5 1.5 0 0 1 4 16.5z" />
      <circle cx="12" cy="12.5" r="3.2" />
    </svg>
  )
}

export function IconImage() {
  return (
    <svg {...svgProps()}>
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <circle cx="9" cy="10" r="1.4" />
      <path d="M5 17l4.5-4.5 3 3L16 12l3 3" />
    </svg>
  )
}

export function IconCheck() {
  return (
    <svg {...svgProps()}>
      <path d="M5 12.5l4.5 4.5L19 7" />
    </svg>
  )
}

export function IconChevron() {
  return (
    <svg {...svgProps()}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  )
}

export function IconExpand() {
  return (
    <svg {...svgProps()}>
      <path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5" />
    </svg>
  )
}

export function IconClose() {
  return (
    <svg {...svgProps()}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  )
}

export function IconAlert() {
  return (
    <svg {...svgProps()}>
      <path d="M12 4.5l8.5 15h-17z" />
      <path d="M12 10v4M12 17h.01" />
    </svg>
  )
}

export function IconSpinner() {
  return (
    <svg {...svgProps()} style={{ animation: 'fx-spin 0.9s linear infinite' }}>
      <circle cx="12" cy="12" r="8" strokeDasharray="26 26" strokeDashoffset="0" />
    </svg>
  )
}

export function IconDot() {
  return (
    <svg {...svgProps()}>
      <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
    </svg>
  )
}

export function IconSearch() {
  return (
    <svg {...svgProps()}>
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.5-4.5" />
    </svg>
  )
}
