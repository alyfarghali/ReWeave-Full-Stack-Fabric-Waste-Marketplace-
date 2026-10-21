// Generates scan results in the exact shape the vision pipeline returns
// (backend/app/scanning/schemas.py: DetectResponse), so the server lists them
// as lots through the same /lots/from-scan path as real scans.

export const FRAME_WIDTH = 960
export const FRAME_HEIGHT = 640

// Offcut mix for an apparel cutting floor: knit-heavy, with denim, twill,
// fleece, linen and wool lines. GSM drives weight (area x GSM).
const FABRICS = [
  { fabric: 'cotton jersey', family: 'cotton', structure: 'knit', composition: '95% cotton, 5% spandex', gsm: 180, share: 30,
    colors: ['white', 'grey', 'red', 'green', 'navy'], pattern: 'jersey' },
  { fabric: 'denim', family: 'denim/cotton', structure: 'denim twill', composition: '98% cotton, 2% elastane', gsm: 340, share: 20,
    colors: ['navy', 'blue', 'black'], pattern: 'denim' },
  { fabric: 'cotton twill', family: 'cotton', structure: 'twill', composition: '100% cotton', gsm: 240, share: 18,
    colors: ['cream', 'beige', 'navy'], pattern: 'twill' },
  { fabric: 'fleece', family: 'polyester', structure: 'fleece/nap', composition: '100% polyester', gsm: 280, share: 16,
    colors: ['grey', 'black', 'red'], pattern: 'fleece' },
  { fabric: 'linen', family: 'linen', structure: 'woven', composition: '100% linen', gsm: 190, share: 9,
    colors: ['natural', 'beige'], pattern: 'woven' },
  { fabric: 'wool blend', family: 'wool', structure: 'woven', composition: '70% wool, 30% nylon', gsm: 300, share: 7,
    colors: ['charcoal', 'grey'], pattern: 'woven' },
]

export const COLOR_HEX = {
  white: '#f2f0ea', natural: '#e6dcc6', cream: '#ece2cc', beige: '#cdb894', grey: '#9a9c9e', charcoal: '#45484c',
  black: '#1d1e20', navy: '#1f2b46', blue: '#3c5f8f', red: '#b3302e', green: '#3f6b46',
}

const BIN_OUTLINES = ['#16a34a', '#2563eb', '#dc2626', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d', '#ea580c', '#4f46e5']

function pick(rng, items, weight = () => 1) {
  const total = items.reduce((sum, item) => sum + weight(item), 0)
  let roll = rng() * total
  for (const item of items) {
    roll -= weight(item)
    if (roll <= 0) return item
  }
  return items[items.length - 1]
}

// Small deterministic PRNG so a frame's shapes and its crops agree.
export function seededRandom(seed) {
  let t = seed >>> 0
  return () => {
    t += 0x6d2b79f5
    let r = Math.imul(t ^ (t >>> 15), 1 | t)
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r)
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296
  }
}

// An irregular offcut outline around (cx, cy), roughly `radius` px across.
function offcutPolygon(rng, cx, cy, radius) {
  const points = []
  const corners = 5 + Math.floor(rng() * 4)
  const stretch = 0.6 + rng() * 0.8
  const turn = rng() * Math.PI
  for (let i = 0; i < corners; i++) {
    const angle = (i / corners) * Math.PI * 2 + (rng() - 0.5) * 0.5
    const r = radius * (0.7 + rng() * 0.35)
    const x = Math.cos(angle) * r * stretch
    const y = Math.sin(angle) * r
    points.push([
      Math.round(cx + x * Math.cos(turn) - y * Math.sin(turn)),
      Math.round(cy + x * Math.sin(turn) + y * Math.cos(turn)),
    ])
  }
  return points
}

function polygonArea(points) {
  let area = 0
  for (let i = 0; i < points.length; i++) {
    const [x1, y1] = points[i]
    const [x2, y2] = points[(i + 1) % points.length]
    area += x1 * y2 - x2 * y1
  }
  return Math.abs(area) / 2
}

function bbox(points) {
  const xs = points.map(([x]) => x)
  const ys = points.map(([, y]) => y)
  const x = Math.min(...xs)
  const y = Math.min(...ys)
  return [x, y, Math.max(...xs) - x, Math.max(...ys) - y]
}

function sizeLabel(sizePercent) {
  if (sizePercent >= 1.2) return 'large'
  if (sizePercent >= 0.5) return 'medium'
  return 'small'
}

function weightLabel(grams) {
  return grams >= 1000 ? `${(grams / 1000).toFixed(2)} kg` : `${Math.round(grams)} g`
}

// The frame covers 4.8 m of cutting line, so offcuts average ~700 cm² (~17 g).
const PX_PER_CM = FRAME_WIDTH / 480

/**
 * One camera frame: `count` pieces laid on the table, measured and binned.
 * Returns the scan (without images; render.js adds those) plus each piece's
 * outline and texture so the frame can be drawn.
 */
export function generateFrame(seed, count, firstPieceId = 1) {
  const rng = seededRandom(seed)
  const cols = Math.ceil(Math.sqrt(count * (FRAME_WIDTH / FRAME_HEIGHT)))
  const rows = Math.ceil(count / cols)
  const cellW = FRAME_WIDTH / cols
  const cellH = FRAME_HEIGHT / rows
  const totalPx = FRAME_WIDTH * FRAME_HEIGHT

  const pieces = []
  for (let i = 0; i < count; i++) {
    const spec = pick(rng, FABRICS, (f) => f.share)
    const color = spec.colors[Math.floor(rng() * spec.colors.length)]
    const cx = (i % cols + 0.5) * cellW + (rng() - 0.5) * cellW * 0.25
    const cy = (Math.floor(i / cols) + 0.5) * cellH + (rng() - 0.5) * cellH * 0.25
    const outline = offcutPolygon(rng, cx, cy, Math.min(cellW, cellH) * (0.28 + rng() * 0.16))
    const areaPx = polygonArea(outline)
    const areaCm2 = areaPx / (PX_PER_CM * PX_PER_CM)
    const grams = Math.round(((areaCm2 * spec.gsm) / 10000) * 10) / 10
    const sizePercent = Math.round((areaPx / totalPx) * 10000) / 100
    pieces.push({
      id: firstPieceId + i,
      bbox: bbox(outline),
      contour: outline,
      color_name: color,
      color_hex: COLOR_HEX[color],
      size_percent: sizePercent,
      size_label: sizeLabel(sizePercent),
      area_pixels: Math.round(areaPx),
      area_cm2: Math.round(areaCm2 * 10) / 10,
      color_family: color,
      pattern_type: spec.pattern === 'jersey' && rng() < 0.15 ? 'striped' : 'solid',
      is_fabric: true,
      fabric_type_guess: spec.fabric,
      material_family: spec.family,
      material_sort_family: spec.family,
      weave_or_knit: spec.structure,
      composition_guess: spec.composition,
      fabric_confidence: 'high',
      gsm: spec.gsm,
      fold_factor: 1,
      estimated_weight_g: grams,
      weight_label: weightLabel(grams),
      texture: spec.pattern,
    })
  }

  const groups = binPieces(pieces)
  const scan = {
    image_width: FRAME_WIDTH,
    image_height: FRAME_HEIGHT,
    pieces,
    groups,
    scale_reference_found: true,
    px_per_cm: Math.round(PX_PER_CM * 1000) / 1000,
    scale_method: 'fixed-camera',
    scale_confidence: 'high',
    segmentation_method: 'continuous-camera',
    llm_model: null,
    warnings: [],
  }
  return scan
}

// Bins A, B, C… by color + fabric, largest bin first (like SortGrouper).
function binPieces(pieces) {
  const bins = new Map()
  for (const piece of pieces) {
    const key = `${piece.color_name}|${piece.fabric_type_guess}`
    if (!bins.has(key)) bins.set(key, [])
    bins.get(key).push(piece)
  }
  return [...bins.values()]
    .sort((a, b) => b.length - a.length)
    .map((members, index) => {
      const id = String.fromCharCode(65 + index)
      const first = members[0]
      const grams = members.reduce((sum, p) => sum + p.estimated_weight_g, 0)
      const outline = BIN_OUTLINES[index % BIN_OUTLINES.length]
      for (const piece of members) {
        piece.sort_group_id = id
        piece.outline_color = outline
      }
      const totalSize = members.reduce((sum, p) => sum + p.size_percent, 0)
      return {
        sort_group_id: id,
        color_name: first.color_name,
        color_hex: first.color_hex,
        outline_color: outline,
        piece_count: members.length,
        total_size_percent: Math.round(totalSize * 100) / 100,
        avg_size_label: sizeLabel(totalSize / members.length),
        fabric_type_guess: first.fabric_type_guess,
        material_family: first.material_family,
        material_sort_family: first.material_sort_family,
        weave_or_knit: first.weave_or_knit,
        composition_guess: first.composition_guess,
        color_family: first.color_family,
        pattern_type: 'solid',
        estimated_weight_g: Math.round(grams * 10) / 10,
        total_weight_label: weightLabel(grams),
        piece_ids: members.map((p) => p.id),
        sort_instruction: `Bin ${id}: place outlined pieces ${members.slice(0, 6).map((p) => p.id).join(', ')}${members.length > 6 ? '…' : ''} into the ${first.color_name} ${first.fabric_type_guess} lot.`,
      }
    })
}
