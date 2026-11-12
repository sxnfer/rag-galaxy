import { useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Color, Vector3 } from 'three'
import Finish from '../scene/Finish.jsx'
import { Driver, Rig, usePointer } from '../scene/Rig.jsx'
import { makeDots, makeLines } from '../scene/marks.js'
import { DARK, GLOW, INK } from '../scene/theme.js'
import { FOV, TAN, pixelsPerUnit, shot } from '../layout.js'
import { REDUCED, clamp, smooth } from '../timeline.js'

// The Journey's picture: a line of stops, and the question as a point of light
// travelling along it. The camera travels with the light, so the light stays
// in one place on screen and the line slides past, like a view from a train.
//
// One stop is off the line: the aside ("before I arrived"). The light rises
// up to it and comes back down. (Up, not down: what the question looks like
// hangs below the line, and must stay clear.)
//
// As everywhere on the site, the picture is worked out from the story
// position alone (clock.p): chapter n is the light resting on stop n.

const STEP = 1.7     // how far apart the stops are
const RISE = 0.5     // how far above the line the aside sits
const DIST = 9       // how far away the camera stands
const BRIGHT = new Color(INK).multiplyScalar(GLOW)

// Where the light sits on screen, as shares of the window: a little right of
// centre on a wide screen (the caption is bottom left), and near the top, so
// what the question looks like can hang beneath it.
export const lightAt = (w, h) => (w / h < 0.9 ? { x: 0.5, y: 0.17 } : { x: 0.56, y: 0.2 })

// Where each stop is. spots[0] is where the light waits before the first stop.
function place(stops) {
  const spots = [[-STEP, 0, 0]]
  let x = 0
  for (const s of stops) {
    if (s.aside) spots.push([x - STEP / 2, RISE, 0]) // half-way between the stops either side of it, above the line
    else { spots.push([x, 0, 0]); x += STEP }
  }
  return spots
}

function Line({ stops, spots, clock }) {
  const light = useRef()
  const dots = useMemo(() => makeDots(stops.length), [stops.length])
  const lines = useMemo(() => makeLines(stops.length + 4), [stops.length])
  useEffect(() => () => { dots.geometry.dispose(); dots.material.dispose(); lines.geometry.dispose(); lines.material.dispose() }, [dots, lines])
  const v = useMemo(() => [new Vector3(), new Vector3(), new Vector3()], [])
  const intro = useRef(0)

  useFrame((state, dt) => {
    const p = clamp(clock.p, 0, stops.length)
    const time = REDUCED ? 0 : state.clock.elapsedTime
    intro.current = Math.min(1, intro.current + dt / (REDUCED ? 0.3 : 1.4))
    dots.material.uniforms.uPixels.value = pixelsPerUnit(state.size.height * state.viewport.dpr)

    // The light: it leaves a stop a little before the camera does, and arrives a little before it.
    const i = Math.min(Math.floor(p), stops.length - 1)
    const here = v[0].fromArray(spots[i]).lerp(v[1].fromArray(spots[i + 1]), smooth(0, 0.86, p - i))
    light.current.position.copy(here)
    light.current.scale.setScalar(Math.max(0.0001, smooth(0.1, 0.7, p) * (1 + Math.sin(time * 1.7) * 0.08)))

    // The stops: the ones behind the light stay lit, the ones ahead wait.
    stops.forEach((s, n) => {
      dots.position.set(spots[n + 1], n * 3)
      dots.light[n] = (0.26 + 0.5 * smooth(n + 0.55, n + 1, p)) * intro.current
      dots.size[n] = 0.05
    })
    dots.touch()

    // The line through the stops on the main line, and the two short lines up to the aside.
    lines.begin()
    const main = stops.map((s, n) => (s.aside ? null : spots[n + 1])).filter(Boolean)
    lines.add(v[1].fromArray(main[0]), v[2].fromArray(main[main.length - 1]), 0.13 * intro.current)
    stops.forEach((s, n) => {
      if (!s.aside) return
      const went = smooth(n + 0.05, n + 0.9, p) // lit once the light has been along it
      lines.add(v[1].fromArray(spots[n]), v[2].fromArray(spots[n + 1]), (0.09 + 0.2 * went) * intro.current)
      if (spots[n + 2]) lines.add(v[1].fromArray(spots[n + 1]), v[2].fromArray(spots[n + 2]), (0.09 + 0.2 * smooth(n + 1.05, n + 1.9, p)) * intro.current)
    })
    // The way already travelled is a little brighter. (While the light is up at the aside, it waits at the stop before.)
    const along = (k) => (stops[k - 1]?.aside ? spots[k - 1][0] : spots[k][0])
    const reached = clamp(along(i) + (along(i + 1) - along(i)) * smooth(0, 0.86, p - i), main[0][0], main[main.length - 1][0])
    lines.add(v[1].fromArray(main[0]), v[2].set(reached, 0, 0), 0.34 * intro.current)
    lines.end()
  })

  return (
    <>
      <lineSegments geometry={lines.geometry} material={lines.material} frustumCulled={false} />
      <points geometry={dots.geometry} material={dots.material} frustumCulled={false} />
      <mesh ref={light} scale={0.0001}>
        <sphereGeometry args={[0.05, 24, 24]} />
        <meshBasicMaterial color={BRIGHT} toneMapped={false} />
      </mesh>
    </>
  )
}

export default function Track({ stops, clock, w, h }) {
  const spots = useMemo(() => place(stops), [stops])
  // One camera position per stop: straight on, with the line where the light belongs on screen.
  const shots = useMemo(() => {
    const aspect = w / h
    const at = lightAt(w, h)
    const across = (at.x - 0.5) * 2 * DIST * TAN * aspect
    return spots.map(([x]) => shot([x - across, 0, 0], [0, 0, 1], [1, 1], aspect, { dist: DIST, lift: 0.5 - at.y, parallax: 0.5 }))
  }, [spots, w, h])
  usePointer(clock, () => false)

  return (
    <Canvas className="stage" flat dpr={[1, 2]} camera={{ fov: FOV, near: 0.1, far: 300, position: shots[0].pos }} gl={{ antialias: false, powerPreference: 'high-performance' }}>
      <color attach="background" args={[DARK]} />
      <Driver clock={clock} />
      <Rig shots={shots} clock={clock} />
      {stops.length > 0 && <Line stops={stops} spots={spots} clock={clock} />}
      <Finish />
    </Canvas>
  )
}
