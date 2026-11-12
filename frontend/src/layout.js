// Where everything is, and where the camera stands in each chapter.
//
// The story is laid out left to right in one dark space:
//
//     V (x = -18)            the origin (x = 0)            E (x = 18)
//     the question:          the library:                  the hand-off:
//     words, then numbers,   every passage, first as       the chosen passages
//     then a single point    a sheet, then as a map        and the answer
//
// Coordinates are [x, y, z]: x runs left to right, y up, z towards the viewer.
// Everything here depends on the shape of the window, so a phone held upright
// gets its own arrangement.

export const FOV = 35 // the camera's angle of view, in degrees (a slightly long lens)
export const TAN = Math.tan(((FOV / 2) * Math.PI) / 180)

export const V = [-18, 0, 0]
export const E = [18, 0, 0]
const D_E = 10 // how far the camera stands from the hand-off

const unit = ([x, y, z]) => { const l = Math.hypot(x, y, z); return [x / l, y / l, z / l] }

// One camera position. `look` is the point it looks at, `dir` the direction it
// stands in from there, and `fit` the [width, height] that must fit in the frame:
// the camera backs away until it does, whatever the window's shape.
// `lift` raises the subject in the frame, leaving room for the caption below.
export function shot(look, dir, fit, aspect, o = {}) {
  const d = unit(dir)
  const dist = o.dist ?? Math.max(fit[1] / 2 / TAN, fit[0] / 2 / (TAN * aspect))
  const drop = (o.lift ?? 0) * 2 * dist * TAN
  const at = [look[0], look[1] - drop, look[2]]
  return {
    look: at,
    pos: [at[0] + d[0] * dist, at[1] + d[1] * dist, at[2] + d[2] * dist],
    sway: o.sway ?? 0,       // how much the camera drifts by itself
    orbit: o.orbit ?? 0,     // 1 = the visitor may drag to turn the view
    parallax: o.parallax ?? 1, // how much the view leans with the mouse
    focus: dist * (o.focus ?? 1), // the distance that is sharp
    aperture: o.aperture ?? 0,    // how fast things blur away from it
  }
}

export function buildLayout(w, h, count) {
  const aspect = w / h
  const tall = aspect < 0.9
  const lift = tall ? 0.11 : 0.07
  // On a wide screen the caption sits bottom left, so the map sits a little to the right of centre.
  const aside = tall ? 0 : -0.9

  // The sheet: every passage in the order it was written, in neat rows.
  const cols = Math.max(2, Math.ceil(Math.sqrt(Math.max(1, count) * (tall ? 0.6 : 1.9))))
  const rows = Math.max(1, Math.ceil(count / cols))
  const gw = tall ? 4.6 : 8.4
  const sp = gw / (cols - 1)
  const grid = { cols, rows, sp, w: gw, h: sp * (rows - 1) }

  // The question's numbers, as bars: one long row, or three on a tall screen.
  const bars = tall ? { rows: 3, w: 5.4, gap: 1.9 } : { rows: 1, w: 11, gap: 0 }
  const barsH = (bars.rows - 1) * bars.gap + 2.6

  // Where the question waits above the sheet before it dives in.
  const wait = [0, grid.h / 2 + (tall ? 0.8 : 0.7), 0.3]

  const base = [
    /* 0 start    */ shot(V, [0, 0, 1], [10, 6], aspect), // the same empty frame as chapter 1: asking begins the film without a cut
    /* 1 words    */ shot(V, [0, 0, 1], [10, 6], aspect),
    /* 2 numbers  */ shot(V, [0.12, 0.05, 1], [bars.w * 1.22, barsH * (tall ? 2.3 : 2.1)], aspect, { lift: tall ? 0.04 : 0 }),
    /* 3 a place  */ shot(V, [-0.1, 0.08, 1], [6.4, 4.4], aspect),
    /* 4 library  */ shot([0, 0.25, 0], [-0.2, 0.1, 1], [grid.w * 1.3, (grid.h + 1) * 1.95], aspect, { lift, aperture: 0.002 }),
    /* 5 the map  */ shot([aside, 0, 0], [0.3, 0.2, 1], [9, 9.8], aspect, { lift, sway: 0.35, orbit: 1, aperture: 0.008 }),
  ]

  // Chapter 6 looks at wherever this question landed, so it needs the question.
  function shots(focusPoint, reach) {
    const size = Math.max(5.6, reach * 3.4)
    return [
      ...base,
      /* 6 nearest  */ shot([focusPoint[0] + aside * 0.6, focusPoint[1], focusPoint[2]], [-0.28, 0.14, 1], [size, size], aspect, { lift, sway: 0.2, orbit: 1, aperture: 0.02 }),
      /* 7 evidence */ shot(E, [0, 0, 1], [1, 1], aspect, { dist: D_E, parallax: 0 }),
      /* 8 answer   */ shot(E, [0, 0, 1], [1, 1], aspect, { dist: D_E, parallax: 0 }),
    ]
  }

  return { w, h, aspect, tall, grid, bars, wait, shots }
}

// The hand-off (chapters 7 and 8) is arranged in screen pixels, because words
// have to fit: the question on top, the passages below it, then the answer.
// Each position is where a point of light comes to rest; its words hang from it.
export function handoff(w, h, n) {
  const wide = w >= 760
  if (wide) {
    const gap = 28
    const cardW = Math.min(212, (w - 120 - (n - 1) * gap) / Math.max(1, n))
    const x0 = (w - (n * cardW + (n - 1) * gap)) / 2
    const row = (y) => Array.from({ length: n }, (_, i) => ({ x: x0 + i * (cardW + gap), y }))
    return {
      wide, cardW,
      ask: [{ x: w / 2, y: h * 0.2 }, { x: w / 2, y: h * 0.1 }],
      cards: [row(h * 0.4), row(h * 0.215)],
      answerTop: h * 0.385,
    }
  }
  const x = 26
  const col = (y0, pitch) => Array.from({ length: n }, (_, i) => ({ x, y: y0 + i * pitch }))
  return {
    wide, cardW: w - x - 40,
    ask: [{ x, y: h * 0.15 }, { x, y: 84 }],
    cards: [col(h * 0.15 + 64, 46), col(84 + 36, 27)],
    answerTop: 84 + 36 + n * 27 + 22,
  }
}

// A screen position (pixels) to the place in the 3D scene that appears there,
// when the camera is standing at the hand-off.
export function toWorld({ x, y }, w, h) {
  return [E[0] + ((x / w) * 2 - 1) * D_E * TAN * (w / h), (1 - (y / h) * 2) * D_E * TAN, 0]
}

// How many screen pixels one unit of the 3D scene covers, at a distance of 1.
export const pixelsPerUnit = (heightPx) => heightPx / (2 * TAN)
