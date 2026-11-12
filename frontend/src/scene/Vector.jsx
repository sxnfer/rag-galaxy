import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Color, Object3D } from 'three'
import { INK } from './theme.js'
import { V } from '../layout.js'
import { clamp, smooth, tl } from '../timeline.js'

const SCALE = 10   // turns a small number like 0.05 into a bar you can see
const TALLEST = 1.2 // so one large number can't tower over the rest

const ease = (t) => t * t * (3 - 2 * t)

// The question's numbers, one thin bar each (chapter 2). Bars above the line
// are positive numbers, bars below are negative.
// They are written left to right as the story moves from 1 to 2, then fall
// inwards into a single point as it moves from 2 to 3.
export default function Vector({ vector, layout }) {
  const mesh = useRef()
  const dummy = useMemo(() => new Object3D(), [])
  const n = vector?.length ?? 0
  const { rows, w, gap } = layout.bars
  const perRow = Math.ceil(n / rows)
  const pitch = w / Math.max(1, perRow - 1)

  // Positive numbers in full ink, negative ones quieter.
  useEffect(() => {
    if (!mesh.current || !vector) return
    const up = new Color(INK), down = new Color(INK).multiplyScalar(0.42)
    vector.forEach((x, i) => mesh.current.setColorAt(i, x >= 0 ? up : down))
    mesh.current.instanceColor.needsUpdate = true
  }, [vector, n])

  useFrame(() => {
    const m = mesh.current
    if (!m || !vector) return
    const p = tl.p
    m.visible = p > 1.02 && p < 2.98
    if (!m.visible) return
    const write = smooth(1.28, 1.97, p)   // 0 = nothing written yet, 1 = all of them
    const fall = smooth(2.08, 2.9, p)     // 0 = a row of bars, 1 = one point

    for (let i = 0; i < n; i++) {
      const col = i % perRow, row = Math.floor(i / perRow)
      const x = col * pitch - w / 2
      const y = ((rows - 1) / 2 - row) * gap
      const along = i / n
      const shown = ease(clamp((write * 1.25 - along) / 0.25))
      // The outermost bars leave first, so the row closes in on its centre.
      const gone = ease(clamp(fall * 1.5 - (1 - Math.abs(x) / (w / 2)) * 0.5))
      const height = clamp(Math.abs(vector[i]) * SCALE, 0.03, TALLEST) * shown * (1 - gone)
      const there = height > 0.001 ? 1 : 0 // a bar that isn't written yet takes up no room at all
      dummy.position.set(V[0] + x * (1 - gone), V[1] + y * (1 - gone) + (vector[i] >= 0 ? height : -height) / 2, V[2])
      dummy.scale.set((1 - gone * 0.6) * there, height, there)
      dummy.updateMatrix()
      m.setMatrixAt(i, dummy.matrix)
    }
    m.instanceMatrix.needsUpdate = true
  })

  if (!vector) return null
  return (
    <instancedMesh ref={mesh} args={[null, null, n]} key={`${n}-${rows}`} frustumCulled={false} visible={false}>
      <boxGeometry args={[pitch * 0.5, 1, pitch * 0.5]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  )
}
