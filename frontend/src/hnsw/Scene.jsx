import { useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Color, Vector3 } from 'three'
import Finish from '../scene/Finish.jsx'
import { Driver, Rig, usePointer } from '../scene/Rig.jsx'
import { makeDots, makeLines } from '../scene/marks.js'
import { DARK, GLOW, INK } from '../scene/theme.js'
import { FOV, pixelsPerUnit, shot } from '../layout.js'
import { REDUCED, clamp, lerp, smooth, smoother } from '../timeline.js'
import { FLOORS, N, QUERY } from './graph.js'
import { CHAPTERS, count } from './story.js'

// The search film's picture: 150 passages on a flat map, the links between
// them, two more floors above, and a point of light that walks to the question.
//
// As in the main film, everything is worked out from the story position alone
// (clock.p), so the film can run in either direction:
//
//   0 to 1   every passage is compared with the question, nearest first
//   1 to 2   the links are drawn
//   2 to 3   the walk on the ground floor alone
//   3 to 4   a few passages rise to make two more floors
//   4 to 5   the walk on the top floor
//   5 to 6   down through the middle floor to the ground
//   6 to 7   both walks side by side

const SIZE = 8    // how wide a floor is
const GAP = 2.5   // how far apart the floors are
const BRIGHT = new Color(INK).multiplyScalar(GLOW)
const LABEL_GAP = 20 // pixels between a point and its label (.tag span in styles.css)
const ease = (t) => t * t * (3 - 2 * t)

// Where the camera stands in each chapter. A phone held upright gets its own arrangement.
function buildShots(aspect) {
  const tall = aspect < 0.9
  const aside = tall ? 0 : -1.3 // on a wide screen the caption sits bottom left, so the map sits right of centre
  const lift = tall ? 0.15 : 0.05
  const map = shot([aside, 0, 0.3], [0, 1.2, 1], tall ? [9.2, 9.2] : [12.6, 9.2], aspect, { lift })
  // The three floors, seen from above and to one side. They sit a little right of centre and high in the frame.
  const stack = (y, dir, fit) => shot([tall ? 0 : -1.1, y, 0], dir, fit, aspect, { lift: tall ? 0.14 : 0.1, sway: 0.22, orbit: 1 })
  const wide = tall ? [15.5, 19] : [18.5, 14]
  return [
    map, map, map, map,
    /* 4 floors   */ stack(GAP * 0.95, [0.55, 0.5, 1], wide),
    /* 5 top      */ stack(GAP * 1.15, [0.5, 0.44, 1], wide.map((x) => x * 0.94)),
    /* 6 down     */ stack(GAP * 0.8, [0.52, 0.5, 1], wide.map((x) => x * 0.94)),
    /* 7 both     */ stack(GAP * 0.9, [0.36, 0.6, 1], wide.map((x) => x * 1.04)),
  ]
}

function Film({ graph, walks, clock }) {
  const { pts, floors } = graph
  const question = useRef()
  const walker = useRef()
  const intro = useRef(0)

  // One dot for every passage on every floor it lives on, and two for where the question sits on the upper floors.
  const slot = useMemo(() => {
    let n = 0
    return floors.map((f) => new Map(f.ids.map((id) => [id, n++])))
  }, [floors])
  const total = floors.reduce((sum, f) => sum + f.ids.length, 0)
  const dots = useMemo(() => makeDots(total + FLOORS - 1), [total])
  const edgeCount = floors.reduce((sum, f) => sum + f.edges.length, 0)
  const lines = useMemo(() => makeLines(edgeCount + N + 80), [edgeCount])
  useEffect(() => () => { dots.geometry.dispose(); dots.material.dispose(); lines.geometry.dispose(); lines.material.dispose() }, [dots, lines])

  // How far each ground-floor passage is from the question, and the furthest of them.
  const far = useMemo(() => pts.map((_, i) => graph.toQuery(i) * SIZE), [pts, graph])
  const reach = useMemo(() => Math.max(...far), [far])
  // A random number per link, so they are not all drawn at once.
  const edgeSeed = useMemo(() => floors.map((f) => f.edges.map(([i, j]) => (pts[i].seed + pts[j].seed * 7) % 1)), [floors, pts])

  const v = useMemo(() => [new Vector3(), new Vector3(), new Vector3()], [])
  const spot = useMemo(() => [new Vector3(), new Vector3()], []) // where each walk's light is
  const em = useMemo(() => [1, 1, 1], [])              // how lit each floor is

  useFrame((state, dt) => {
    const p = clock.p
    const time = REDUCED ? 0 : state.clock.elapsedTime
    intro.current = Math.min(1, intro.current + dt / (REDUCED ? 0.3 : 1.6))
    dots.material.uniforms.uPixels.value = pixelsPerUnit(state.size.height * state.viewport.dpr)

    // ---- The floors ----
    // Each passage chosen for an upper floor lifts off at its own moment.
    const lifting = smooth(3.1, 3.72, p)
    const riseOf = (i) => smoother(0, 1, clamp(lifting * 1.35 - pts[i].seed * 0.35))
    const yOf = (L, i) => (L === 0 ? 0 : L * GAP * riseOf(i))
    const at = (out, i, L) => out.set((pts[i].x - 0.5) * SIZE, yOf(L, i), (pts[i].y - 0.5) * SIZE)
    const qAt = (out, L) => out.set((QUERY.x - 0.5) * SIZE, L * GAP * smoother(0, 1, lifting), (QUERY.y - 0.5) * SIZE)

    // ---- The walks: where each has got to ----
    const flat = walks.ground, sA = walks.top, sB = walks.down
    const tFlat = flat.total * clamp((p - 2.06) / 0.91)
    const tA = sA.total * clamp((p - 4.06) / 0.9)
    const tB = sB.total * clamp((p - 5.04) / 0.93)
    // The ground-floor walk is shown in chapter 3, put away for the floors, and returns faintly at the end to compare.
    const flatLight = p < 3 ? smooth(2.02, 2.08, p) : Math.max(1 - smooth(3.0, 3.25, p), 0.42 * smooth(6.2, 6.8, p))
    const floorsLight = smooth(4.02, 4.08, p)

    // Which floor the search is on. That floor is lit; the others step back.
    const walkerY = p < 5.04 ? 2 : heightOf(sB, tB)
    const walking = smooth(4.02, 4.25, p)
    const ending = smooth(6.1, 6.6, p)
    for (let L = 0; L < FLOORS; L++) {
      const mine = lerp(0.3, 1, clamp(1 - Math.abs(walkerY - L)))
      em[L] = lerp(lerp(1, mine, walking), 0.6, ending)
    }

    // ---- The passages ----
    const glint = smooth(2.98, 3.16, p) * (1 - smooth(3.3, 3.75, p)) // the chosen few brighten just before they rise
    const wave = p < 1.6 ? (reach + 2.6) * clamp((p - 0.22) / 0.76) : -1  // how far the comparing has reached
    const checked = 1 - smooth(1.0, 1.45, p)
    let compared = 0
    for (let L = 0; L < FLOORS; L++) {
      for (const [id, n] of slot[L]) {
        at(v[0], id, L)
        dots.position.set([v[0].x, v[0].y, v[0].z], n * 3)
        let light = 0.5, size = L === 0 ? 0.07 : 0.085
        if (L === 0) {
          if (pts[id].level > 0) light += 0.9 * glint
          if (wave >= far[id]) {
            const flash = Math.exp(-(wave - far[id]) / 0.5)
            light += (1.7 * flash + 0.3) * checked
            size *= 1 + 0.7 * flash * checked
            compared++
          }
        }
        const there = L === 0 ? intro.current : clamp(riseOf(id) * 4)
        dots.light[n] = light * em[L] * there
        dots.size[n] = size
      }
    }
    // The question is in the same place on every floor.
    for (let L = 1; L < FLOORS; L++) {
      const n = total + L - 1
      qAt(v[0], L)
      dots.position.set([v[0].x, v[0].y, v[0].z], n * 3)
      dots.light[n] = 1.5 * smooth(3.5, 3.9, p)
      dots.size[n] = 0.08
    }

    // ---- The lines ----
    lines.begin()
    // The links on each floor, drawn outwards from one end.
    const drawn = [smooth(1.08, 1.92, p), smooth(3.62, 3.9, p), smooth(3.74, 3.98, p)]
    for (let L = 0; L < FLOORS; L++) {
      if (drawn[L] <= 0) continue
      floors[L].edges.forEach(([i, j], k) => {
        const grow = ease(clamp(drawn[L] * 1.4 - edgeSeed[L][k] * 0.4))
        if (grow <= 0) return
        at(v[0], i, L); at(v[1], j, L).sub(v[0]).multiplyScalar(grow).add(v[0])
        lines.add(v[0], v[1], 0.19 * em[L] * Math.min(1, grow * 2))
      })
    }
    // The edge of each floor, and the line that joins the question's place on all of them.
    const frame = 0.1 * smooth(3.2, 3.8, p)
    const half = SIZE / 2 + 0.35
    for (let L = 0; L < FLOORS && frame > 0; L++) {
      const y = L * GAP * smoother(0, 1, lifting)
      const corner = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
      for (let c = 0; c < 4; c++) {
        const [ax, az] = corner[c], [bx, bz] = corner[(c + 1) % 4]
        lines.add(v[0].set(ax * half, y, az * half), v[1].set(bx * half, y, bz * half), frame * (0.5 + 0.5 * em[L]))
      }
    }
    lines.add(qAt(v[0], 0), qAt(v[1], FLOORS - 1), 0.3 * smooth(3.5, 3.9, p))
    // Comparing with everything: a thread flicks from the question to each passage in turn.
    if (wave >= 0 && checked > 0) {
      qAt(v[0], 0)
      for (let id = 0; id < N; id++) {
        if (wave < far[id]) continue
        lines.add(v[0], at(v[1], id, 0), 0.6 * Math.exp(-(wave - far[id]) / 0.4) * checked)
      }
    }

    // A walk, up to the moment t. Draws its route and what it is looking at, and
    // says where the light is, how many steps it has taken and how many passages it has compared.
    function play(sched, t, light, out) {
      let steps = 0, seen = 0, here = null
      for (const s of sched.list) {
        if (t < s.t0) break
        const from = s.from ?? s.at
        const fall = s.t1 > s.t0 ? ease(clamp((t - s.t0) / (s.t1 - s.t0))) : 1
        const look = clamp((t - s.t1) / (s.t2 - s.t1))
        const after = s.t3 > s.t2 ? clamp((t - s.t2) / (s.t3 - s.t2)) : t >= s.t2 ? 1 : 0
        const hop = s.type === 'hop' ? ease(after) : 0
        steps = s.type === 'hop' && hop < 0.5 ? s.hops - 1 : s.hops
        seen = s.seenBefore + (t >= s.t1 ? Math.round(s.fresh.length * clamp(look * 1.2)) : 0)

        // Down from the floor above.
        const top = v[0].copy(at(v[2], from, s.fromFloor))
        const low = at(v[1], from, s.floor)
        here = v[2].copy(top).lerp(low, fall)
        if (s.fromFloor !== s.floor) lines.add(top, here, 0.55 * light)
        if (t < s.t1) break

        // Looking: a line reaches out to each neighbour, and each is compared with the question.
        if (t < s.t3 && s.asked.length) {
          const reachOut = ease(look), fade = 1 - after
          for (const n of s.asked) {
            at(v[1], n, s.floor).sub(here).multiplyScalar(reachOut).add(here)
            lines.add(here, v[1], 0.6 * fade * light)
            const k = slot[s.floor].get(n)
            dots.light[k] += 1.1 * reachOut * fade * light
            dots.size[k] *= 1 + 0.45 * reachOut * fade
          }
        }
        // Stepping to the closest one.
        const k = slot[s.floor].get(from)
        dots.light[k] = Math.max(dots.light[k], 0.95 * light)
        if (s.type === 'hop') {
          v[0].copy(here)
          at(v[1], s.at, s.floor).sub(v[0]).multiplyScalar(hop).add(v[0])
          lines.add(v[0], v[1], 1.35 * light)
          here.copy(v[1])
          here.y += Math.sin(Math.PI * hop) * 0.14 // a small leap
        }
      }
      return { here: here && out.copy(here), steps, seen }
    }

    // The walk on the ground floor alone, then the walk through the floors.
    const ground = flatLight > 0 ? play(flat, p > 3.3 ? flat.total : tFlat, flatLight, spot[0]) : null
    let through = null
    if (floorsLight > 0) {
      through = play(sA, tA, floorsLight, spot[1])
      if (p > 5.04) through = play(sB, tB, floorsLight, spot[1])
    }
    lines.end()
    dots.touch()

    // ---- The two lights ----
    const q = question.current, w = walker.current
    qAt(q.position, 0).y = 0
    q.scale.setScalar(Math.max(0.0001, smooth(0.04, 0.2, p) * (1 + Math.sin(time * 1.7) * 0.08)))
    const showGround = p < 3.4 && ground
    const lit = showGround ? smooth(2.03, 2.1, p) * (1 - smooth(3.0, 3.22, p)) : through ? floorsLight * clamp(tA / 0.5) : 0
    const where = showGround ? ground.here : through?.here
    if (where) w.position.copy(where)
    w.scale.setScalar(Math.max(0.0001, lit))

    // ---- The words that follow the picture ----
    const { els } = clock
    pin(els.question, q.position, state, smooth(0.1, 0.3, p) * (1 - 0.6 * ending))
    // Each floor's label hangs off its far right corner. An upright phone has no room there,
    // so the label is tucked inside the left corner instead, where a floor has no passages.
    const side = state.size.width / state.size.height < 0.9 ? -1 : 1
    for (let L = 0; L < FLOORS; L++) {
      const y = L * GAP * smoother(0, 1, lifting)
      pin(els.floors?.[L], v[0].set(side * half, y, -side * half), state, smooth(3.7, 3.98, p) * (0.35 + 0.65 * em[L]))
    }
    const el = els.count
    if (el) {
      const kind = el.dataset.kind
      const text = kind === 'every' ? count(kind, { compared: p >= 1 ? N : compared, total: N })
        : kind === 'ground' ? count(kind, { steps: p >= 3 ? flat.steps : ground?.steps ?? 0, compared: p >= 3 ? flat.seen : ground?.seen ?? 0, total: N })
          : count(kind, { steps: through?.steps ?? 0, compared: through?.seen ?? 0, total: N })
      if (el.textContent !== text) el.textContent = text
    }
  })

  // Place a page element on top of a point in the scene, and set how visible it is.
  function pin(el, point, state, opacity) {
    if (!el) return
    v[1].copy(point).project(state.camera)
    el.style.transform = `translate3d(${((v[1].x * 0.5 + 0.5) * state.size.width).toFixed(1)}px, ${((-v[1].y * 0.5 + 0.5) * state.size.height).toFixed(1)}px, 0)`
    el.style.opacity = opacity.toFixed(3)
    // A label sits to the right of its point. Where that would run off the screen (a phone), it sits to the left.
    const x = (v[1].x * 0.5 + 0.5) * state.size.width
    el.classList.toggle('left', x + LABEL_GAP + el.firstChild.offsetWidth > state.size.width - 12)
  }

  return (
    <>
      <lineSegments geometry={lines.geometry} material={lines.material} frustumCulled={false} />
      <points geometry={dots.geometry} material={dots.material} frustumCulled={false} />
      <mesh ref={question} scale={0.0001}>
        <sphereGeometry args={[0.085, 24, 24]} />
        <meshBasicMaterial color={BRIGHT} toneMapped={false} />
      </mesh>
      <mesh ref={walker} scale={0.0001}>
        <sphereGeometry args={[0.066, 24, 24]} />
        <meshBasicMaterial color={BRIGHT} toneMapped={false} />
      </mesh>
    </>
  )
}

// Which floor a walk's light is on at the moment t: 2 is the top, 0 the ground, and in between while it falls.
function heightOf(sched, t) {
  let y = sched.list[0]?.fromFloor ?? 0
  for (const s of sched.list) {
    if (t < s.t0) break
    const fall = s.t1 > s.t0 ? ease(clamp((t - s.t0) / (s.t1 - s.t0))) : 1
    y = lerp(s.fromFloor, s.floor, fall)
  }
  return y
}

export default function Scene({ graph, walks, clock, w, h }) {
  const shots = useMemo(() => buildShots(w / h), [w, h])
  // From chapter 4 on, the floors can be turned by dragging.
  usePointer(clock, () => clock.target >= 4)
  return (
    <Canvas className="stage" flat dpr={[1, 2]} camera={{ fov: FOV, near: 0.1, far: 300, position: shots[0].pos }} gl={{ antialias: false, powerPreference: 'high-performance' }}>
      <color attach="background" args={[DARK]} />
      <Driver clock={clock} pace={(n) => CHAPTERS[n + 1]?.secs ?? 2} />
      <Rig shots={shots} clock={clock} soft />
      <Film graph={graph} walks={walks} clock={clock} />
      <Finish />
    </Canvas>
  )
}
