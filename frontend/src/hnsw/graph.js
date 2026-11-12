// A small HNSW graph and the walk through it, for teaching.
//
// HNSW (Hierarchical Navigable Small World) keeps the same points on several
// floors. Every point lives on the ground floor; a random few are copied up to
// the next floor, and fewer again to the top. On each floor, every point is
// linked to its nearest neighbours there. Because the top floor has so few
// points, its links are long: a few steps cross the whole map. Each floor down
// has more points and shorter links, so the search zooms in.
//
// This is a toy: 150 points on a flat map with ordinary distance, built the
// same way every time (a fixed random seed), so the walk is the same on every visit.

// A tiny seeded random-number generator (mulberry32): same seed, same numbers.
function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const N = 150
export const FLOORS = 3
export const QUERY = { x: 0.84, y: 0.8 } // where the question lands on the map (0..1)

export function buildGraph() {
  const r = rng(3)
  const pts = []
  let guard = 0
  // Scatter points, keeping a little space between them so they are easy to see.
  while (pts.length < N && guard++ < 20000) {
    const x = 0.04 + r() * 0.92, y = 0.04 + r() * 0.92
    if (pts.every((p) => Math.hypot(p.x - x, p.y - y) > 0.05)) pts.push({ x, y, level: 0, seed: 0 })
  }
  // Each point's top floor is random: most stay at 0, about 1 in 4 reach 1, 1 in 16 reach 2.
  const mL = 1 / Math.log(4)
  pts.forEach((p) => { p.level = Math.min(FLOORS - 1, Math.floor(-Math.log(1 - r()) * mL)) })
  pts.forEach((p) => { p.seed = r() }) // a random number per point, so they don't all move in step

  const M = [4, 3, 3] // links per point on each floor
  const between = (i, j) => Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)
  const floors = [0, 1, 2].map((L) => {
    const ids = pts.map((_, i) => i).filter((i) => pts[i].level >= L)
    const adj = new Map(ids.map((i) => [i, new Set()]))
    ids.forEach((i) => {
      ids.filter((j) => j !== i).sort((u, v) => between(u, i) - between(v, i)).slice(0, M[L])
        .forEach((j) => { adj.get(i).add(j); adj.get(j).add(i) })
    })
    const edges = []
    adj.forEach((set, i) => set.forEach((j) => { if (i < j) edges.push([i, j]) }))
    return { ids, adj, edges }
  })

  const toQuery = (i) => Math.hypot(pts[i].x - QUERY.x, pts[i].y - QUERY.y)
  // Start from the top-floor point farthest from the question: the worst case.
  const entry = floors[2].ids.slice().sort((u, v) => toQuery(v) - toQuery(u))[0]
  const nearest = pts.map((_, i) => i).sort((u, v) => toQuery(u) - toQuery(v))[0]
  return { pts, floors, entry, toQuery, nearest }
}

// The walk: on each floor, look at the current point's neighbours, step to
// whichever is closest to the question, and repeat. When no neighbour is
// closer, go down to the same point one floor below. Stop on the ground floor.
//
// `order` is the floors to use, top first: [2, 1, 0] is HNSW, [0] is the ground floor alone.
// Each step records which neighbours it looked at (`asked`), which of those had
// never been compared before (`fresh`), and the running totals.
export function walk(graph, order) {
  const { floors, entry, toQuery } = graph
  const seen = new Set([entry])
  const steps = [{ type: 'start', floor: order[0], at: entry, asked: [], fresh: [entry], seenBefore: 0, seen: 1, hops: 0 }]
  let cur = entry, hops = 0
  order.forEach((L, li) => {
    for (;;) {
      const nb = [...floors[L].adj.get(cur)]
      const seenBefore = seen.size
      const fresh = nb.filter((n) => !seen.has(n))
      fresh.forEach((n) => seen.add(n))
      let best = cur
      nb.forEach((n) => { if (toQuery(n) < toQuery(best)) best = n })
      const step = { floor: L, from: cur, asked: nb, fresh, seenBefore, seen: seen.size }
      if (best === cur) {
        const last = li === order.length - 1
        steps.push({ ...step, type: last ? 'end' : 'down', at: cur, hops })
        break
      }
      hops++
      steps.push({ ...step, type: 'hop', at: best, hops })
      cur = best
    }
  })
  return steps
}

// Lay steps `from` to `to` of a walk out in time, in seconds. A step is up to
// three moves, one after another:
//   fall   drop to this floor from the one above (only on the first step of a floor)
//   look   compare the neighbours with the question (or, on the first step, appear)
//   hop    move to the closest neighbour (only when one is closer)
// Each step gets the moment each of its moves ends: t0 (begins), t1, t2, t3.
export function schedule(steps, from, to, { fall = 0.7, look = 0.45, hop = 0.45, appear = 0.6, rest = 0.3 } = {}) {
  let t = 0
  const list = steps.slice(from, to).map((s, k) => {
    const before = steps[from + k - 1]
    const fromFloor = before ? before.floor : s.floor
    const t0 = t
    const t1 = t0 + (fromFloor !== s.floor ? fall : 0)
    const t2 = t1 + (s.type === 'start' ? appear : look)
    const t3 = t2 + (s.type === 'hop' ? hop : s.type === 'start' ? 0 : rest)
    t = t3
    return { ...s, fromFloor, t0, t1, t2, t3 }
  })
  return { list, total: t }
}
