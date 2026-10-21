// Draws generated frames: the annotated table view and per-piece crop thumbnails,
// as JPEG data URLs in the same form the vision pipeline produces.
import { FRAME_HEIGHT, FRAME_WIDTH, seededRandom } from './generator.js'

const TABLE = '#d9d6cf'
const CROP_SIZE = 200

function tracePolygon(ctx, points) {
  ctx.beginPath()
  points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
  ctx.closePath()
}

function drawTexture(ctx, piece, [x, y, w, h]) {
  const rng = seededRandom(piece.id * 7919)
  ctx.lineWidth = 1
  if (piece.texture === 'denim' || piece.texture === 'twill') {
    const gap = piece.texture === 'denim' ? 4 : 3
    ctx.strokeStyle = piece.texture === 'denim' ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.08)'
    for (let d = -h; d < w + h; d += gap) {
      ctx.beginPath()
      ctx.moveTo(x + d, y)
      ctx.lineTo(x + d - h, y + h)
      ctx.stroke()
    }
  } else if (piece.texture === 'jersey') {
    if (piece.pattern_type === 'striped') {
      ctx.fillStyle = 'rgba(255,255,255,0.55)'
      for (let row = y; row < y + h; row += 10) ctx.fillRect(x, row, w, 4)
    }
    ctx.strokeStyle = 'rgba(0,0,0,0.06)'
    for (let row = y; row < y + h; row += 2) {
      ctx.beginPath()
      ctx.moveTo(x, row)
      ctx.lineTo(x + w, row)
      ctx.stroke()
    }
  } else if (piece.texture === 'fleece') {
    for (let i = 0; i < (w * h) / 6; i++) {
      ctx.fillStyle = rng() < 0.5 ? 'rgba(255,255,255,0.10)' : 'rgba(0,0,0,0.10)'
      ctx.fillRect(x + rng() * w, y + rng() * h, 1.5, 1.5)
    }
  } else {
    ctx.strokeStyle = 'rgba(0,0,0,0.07)'
    for (let d = 0; d < Math.max(w, h); d += 3) {
      ctx.beginPath()
      ctx.moveTo(x + d, y)
      ctx.lineTo(x + d, y + h)
      ctx.moveTo(x, y + d)
      ctx.lineTo(x + w, y + d)
      ctx.stroke()
    }
  }
}

function drawPiece(ctx, piece) {
  ctx.save()
  ctx.shadowColor = 'rgba(0,0,0,0.25)'
  ctx.shadowBlur = 6
  ctx.shadowOffsetY = 2
  tracePolygon(ctx, piece.contour)
  ctx.fillStyle = piece.color_hex
  ctx.fill()
  ctx.restore()

  ctx.save()
  tracePolygon(ctx, piece.contour)
  ctx.clip()
  drawTexture(ctx, piece, piece.bbox)
  ctx.restore()
}

function drawTable(ctx, width, height) {
  ctx.fillStyle = TABLE
  ctx.fillRect(0, 0, width, height)
  ctx.strokeStyle = 'rgba(0,0,0,0.05)'
  ctx.lineWidth = 1
  for (let gx = 0; gx < width; gx += 40) {
    ctx.beginPath()
    ctx.moveTo(gx, 0)
    ctx.lineTo(gx, height)
    ctx.stroke()
  }
  for (let gy = 0; gy < height; gy += 40) {
    ctx.beginPath()
    ctx.moveTo(0, gy)
    ctx.lineTo(width, gy)
    ctx.stroke()
  }
}

function canvas(width, height) {
  const el = document.createElement('canvas')
  el.width = width
  el.height = height
  return [el, el.getContext('2d')]
}

/** Annotated table view: every piece outlined in its bin color with the bin letter. */
export function renderFrame(scan) {
  const [el, ctx] = canvas(FRAME_WIDTH, FRAME_HEIGHT)
  drawTable(ctx, FRAME_WIDTH, FRAME_HEIGHT)
  for (const piece of scan.pieces) drawPiece(ctx, piece)

  for (const piece of scan.pieces) {
    tracePolygon(ctx, piece.contour)
    ctx.strokeStyle = piece.outline_color
    ctx.lineWidth = 2.5
    ctx.stroke()
    const [x, y, w, h] = piece.bbox
    ctx.font = 'bold 13px system-ui, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = piece.outline_color
    ctx.beginPath()
    ctx.arc(x + w / 2, y + h / 2, 10, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#fff'
    ctx.fillText(piece.sort_group_id, x + w / 2, y + h / 2 + 0.5)
  }
  return el.toDataURL('image/jpeg', 0.82)
}

/** Adds crop_data_url to every piece: the piece alone on the table, padded. */
export function renderCrops(scan) {
  for (const piece of scan.pieces) {
    const [x, y, w, h] = piece.bbox
    const scale = (CROP_SIZE * 0.82) / Math.max(w, h)
    const [el, ctx] = canvas(CROP_SIZE, CROP_SIZE)
    drawTable(ctx, CROP_SIZE, CROP_SIZE)
    ctx.translate(CROP_SIZE / 2 - (x + w / 2) * scale, CROP_SIZE / 2 - (y + h / 2) * scale)
    ctx.scale(scale, scale)
    drawPiece(ctx, piece)
    piece.crop_data_url = el.toDataURL('image/jpeg', 0.78)
  }
}
