import { capitalize, formatWeightKg } from '../../shared/formatters.js'

export const PIPELINE_STEPS = [
  'Segmenting fabric boundaries',
  'Identifying color clusters',
  'Classifying material types',
  'Estimating weights and yield',
  'Building marketplace listings',
]

export function buildListingSummary(res) {
  const groups = res ? [...(res.groups || [])].sort(sortByBin) : []
  const pieces = groups.reduce((sum, group) => sum + (Number(group.piece_count) || 0), 0)
  const weightG = groups.reduce((sum, group) => sum + (Number(group.estimated_weight_g) || 0), 0)

  return {
    listings: groups.length,
    pieces,
    weightLabel: weightG > 0 ? formatWeightKg(weightG / 1000) : 'Pending',
    rows: groups.map((group, i) => {
      const letter = group.sort_group_id || String.fromCharCode(65 + i)
      return {
        key: group.sort_group_id || `${group.color_name}-${i}`,
        letter,
        color: group.outline_color || group.color_hex || '#77736c',
        name: `${capitalize(group.color_name)}${group.fabric_type_guess ? ` - ${group.fabric_type_guess}` : ''}`,
        pieces: Number(group.piece_count) || 0,
        weightLabel: group.total_weight_label || (
          group.estimated_weight_g ? formatWeightKg(Number(group.estimated_weight_g) / 1000) : ''
        ),
      }
    }),
  }
}

export function sortByBin(a, b) {
  const x = a.sort_group_id || a.color_name || ''
  const y = b.sort_group_id || b.color_name || ''
  return x.localeCompare(y)
}

export function friendlyError(err) {
  if (/not configured/i.test(err?.message || '')) return 'Scanning is not set up on this server yet (missing vision API key).'
  if (err?.status === 400) return 'We could not read that image. Take the photo again.'
  return 'Something went wrong on our side. Please try once more.'
}

// Pick dark or light text so the bin letter stays readable on any fabric color.
export function readableOn(hex) {
  if (!hex || hex[0] !== '#') return '#FFFFFF'
  let c = hex.slice(1)
  if (c.length === 3) c = c.split('').map((x) => x + x).join('')
  if (c.length !== 6) return '#FFFFFF'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return lum > 0.6 ? '#15191F' : '#FFFFFF'
}
