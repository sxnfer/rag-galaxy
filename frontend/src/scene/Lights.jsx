import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { BufferAttribute, BufferGeometry, Color, Vector3 } from 'three'
import { GLOW, INK } from './theme.js'
import { V } from '../layout.js'
import { REDUCED, smooth, smoother, tl } from '../timeline.js'

const BRIGHT = new Color(INK).multiplyScalar(GLOW)

// The points of light: your question, and the passages it found.
// They are the only things in the film that glow, and they are what the story
// follows: the question travels into the library, finds its nearest passages,
// and then all of them leave together to be handed to the language model.
//
// Each light's position is worked out from the story position alone (tl.p),
// so the film can run in either direction.
export default function Lights({ plot, layout, slots }) {
  const question = useRef()
  const hits = useRef([])
  const threads = useRef()
  const a = useMemo(() => new Vector3(), [])
  const b = useMemo(() => new Vector3(), [])
  const pos = useMemo(() => new Vector3(), [])
  const qPos = useMemo(() => new Vector3(), [])
  const n = plot.hits.length

  // The threads from the question to each passage it found: one straight line each.
  const lines = useMemo(() => {
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(new Float32Array(Math.max(1, n) * 6), 3))
    return g
  }, [n])

  // Place a page element on top of a point in the scene.
  function pin(el, point, state) {
    if (!el) return
    a.copy(point).project(state.camera)
    el.style.transform = `translate3d(${((a.x * 0.5 + 0.5) * state.size.width).toFixed(1)}px, ${((-a.y * 0.5 + 0.5) * state.size.height).toFixed(1)}px, 0)`
  }

  useFrame((state) => {
    const p = tl.p
    const t = REDUCED ? 0 : state.clock.elapsedTime
    const q = question.current
    if (!q || !plot.q) return

    // ---- The question ----
    // Born where its numbers fall together (2 to 3), carried to the library (3 to 4),
    // dropped into its place on the map (4 to 5), then taken to the hand-off (6 to 7).
    if (p <= 3) {
      qPos.fromArray(V)
    } else if (p <= 4) {
      const e = smoother(3.04, 3.94, p)
      qPos.fromArray(V).lerp(a.fromArray(layout.wait), e)
      qPos.y += Math.sin(Math.PI * e) * 0.9
    } else if (p <= 6) {
      const e = smoother(4.3, 4.97, p)
      qPos.fromArray(layout.wait).lerp(a.fromArray(plot.q), e)
      qPos.z += Math.sin(Math.PI * e) * 1.6
    } else {
      const e = smoother(6.05, 6.88, p)
      const s = smooth(7.04, 7.85, p)
      b.fromArray(slots.ask[0]).lerp(a.fromArray(slots.ask[1]), s)
      qPos.fromArray(plot.q).lerp(b, e)
      qPos.z += Math.sin(Math.PI * e) * 2.2
    }
    q.position.copy(qPos)
    // At the hand-off the lights sit beside words, so they become a little finer.
    const fine = 1 - 0.32 * smooth(6.2, 6.9, p)
    q.scale.setScalar(Math.max(0.0001, smooth(2.3, 2.92, p) * fine * (1 + Math.sin(t * 1.7) * 0.08)))
    pin(tl.els.ask, qPos, state)

    // ---- The passages it found ----
    const arr = lines.getAttribute('position').array
    for (let i = 0; i < n; i++) {
      const m = hits.current[i]
      if (!m) continue
      const fly = smoother(6.08 + i * 0.035, 6.9 + i * 0.015, p)
      const s = smooth(7.04, 7.85, p)
      b.fromArray(slots.cards[0][i]).lerp(a.fromArray(slots.cards[1][i]), s)
      pos.fromArray(plot.hits[i]).lerp(b, fly)
      pos.y += Math.sin(Math.PI * fly) * 0.9
      pos.z += Math.sin(Math.PI * fly) * 2.0
      m.position.copy(pos)
      const lit = smooth(5.5 + i * 0.06, 5.85 + i * 0.06, p)
      const pointed = tl.hover === i ? 1.7 : 1
      m.scale.setScalar(Math.max(0.0001, m.scale.x + (lit * pointed * fine - m.scale.x) * 0.2))
      pin(tl.els.cards[i], pos, state)

      // Its thread grows out from the question, best match first.
      const grow = smooth(5.55 + i * 0.07, 5.95 + i * 0.07, p)
      a.fromArray(plot.q)
      b.fromArray(plot.hits[i]).sub(a).multiplyScalar(grow).add(a)
      arr.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6)
    }
    lines.getAttribute('position').needsUpdate = true
    threads.current.material.opacity = 0.42 * smooth(5.5, 5.7, p) * (1 - smooth(6.0, 6.25, p))
    threads.current.visible = p > 5.5 && p < 6.25
  })

  if (!plot.q) return null
  return (
    <>
      <mesh ref={question} scale={0.0001}>
        <sphereGeometry args={[0.062, 24, 24]} />
        <meshBasicMaterial color={BRIGHT} toneMapped={false} />
      </mesh>
      {plot.hits.map((_, i) => (
        <mesh key={i} ref={(m) => { hits.current[i] = m }} scale={0.0001}>
          <sphereGeometry args={[0.044, 20, 20]} />
          <meshBasicMaterial color={BRIGHT} toneMapped={false} />
        </mesh>
      ))}
      <lineSegments ref={threads} geometry={lines} frustumCulled={false} visible={false}>
        <lineBasicMaterial color={INK} transparent opacity={0} depthWrite={false} toneMapped={false} />
      </lineSegments>
    </>
  )
}
