import { useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import Passages from './Passages.jsx'
import Vector from './Vector.jsx'
import Lights from './Lights.jsx'
import Finish from './Finish.jsx'
import { Driver, Rig, usePointer } from './Rig.jsx'
import { DARK } from './theme.js'
import { FOV, toWorld } from '../layout.js'
import { tl } from '../timeline.js'

// What this question did, as places in the scene.
function plotOf(trace, stars) {
  const where = new Map(stars.map((s) => [s.id, s.position]))
  const q = trace?.retrieval?.query_position ?? null
  const sources = trace?.sources ?? []
  const hits = sources.map((s) => where.get(s.chunk_id) ?? q ?? [0, 0, 0])
  // "Near" = every passage that stays lit after the search. With a sorting step,
  // that is all the candidates search kept; without one, just the passages used.
  const near = new Set(trace?.rank?.applied ? trace.rank.before.map((b) => b.chunk_id) : [])
  sources.forEach((s) => near.add(s.chunk_id))
  // Chapter 6 frames the question and what it found: their middle, and how far they spread.
  const all = q ? [q, ...hits] : [[0, 0, 0]]
  const mid = [0, 1, 2].map((k) => all.reduce((sum, v) => sum + v[k], 0) / all.length)
  const reach = Math.max(...all.map((v) => Math.hypot(v[0] - mid[0], v[1] - mid[1], v[2] - mid[2])))
  return { q, hits, near, mid, reach }
}

// `playing` is false while another film is on screen: this one then stops drawing, and keeps its place.
export default function Stage({ stars, trace, layout, hand, playing = true }) {
  const plot = useMemo(() => plotOf(trace, stars), [trace, stars])
  const shots = useMemo(() => layout.shots(plot.mid, plot.reach), [layout, plot])
  // Where each light comes to rest at the hand-off: [chapter 7, chapter 8].
  const slots = useMemo(() => {
    const at = (pt) => toWorld(pt, layout.w, layout.h)
    return { ask: hand.ask.map(at), cards: hand.cards.map((row) => row.map(at)) }
  }, [hand, layout.w, layout.h])

  // The map chapters (5 and 6) can be turned by dragging.
  usePointer(tl, () => tl.target === 5 || tl.target === 6)

  return (
    <Canvas className="stage" flat dpr={[1, 2]} frameloop={playing ? 'always' : 'never'} camera={{ fov: FOV, near: 0.1, far: 300, position: shots[0].pos }} gl={{ antialias: false, powerPreference: 'high-performance' }}>
      <color attach="background" args={[DARK]} />
      <Driver />
      <Rig shots={shots} />
      <Passages stars={stars} layout={layout} plot={plot} />
      <Vector vector={trace?.retrieval?.query_vector} layout={layout} />
      <Lights plot={plot} layout={layout} slots={slots} />
      <Finish />
    </Canvas>
  )
}
