import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { BufferAttribute, BufferGeometry, Color, Vector3 } from 'three'
import { INK } from './theme.js'
import { pixelsPerUnit } from '../layout.js'
import { REDUCED, smooth, smoother, tl } from '../timeline.js'

// Every passage in the library, as one dot each.
//
// All the dots are drawn in a single go by the graphics card. The two small
// programs below (called shaders) run on the graphics card itself: the first
// decides where each dot goes and how big it is, the second colours it in.
// Doing the work there is what keeps a thousand moving dots smooth.
//
// Each dot knows two homes: its place on the sheet (the order it was written)
// and its place on the map (what it means). uMorph slides between the two.
const VERTEX = /* glsl */ `
  attribute vec3 aSheet;   // home on the sheet
  attribute float aSeed;   // a random number per dot, so they don't all move in step
  attribute float aTier;   // 0 = an ordinary passage, 1 = one of the closest to the question
  attribute float aIndex;
  uniform float uMorph, uTime, uPixels, uFocus, uAperture, uBright, uDim, uRipple, uSize, uHover, uIntro;
  uniform vec3 uOrigin;    // where the question sits on the map
  varying float vLight;
  varying float vPixels;
  varying float vBlur;

  void main() {
    // Sheet to map. Each dot leaves at its own moment and takes its own curve.
    float m = clamp(uMorph * 1.5 - aSeed * 0.5, 0.0, 1.0);
    m = m * m * m * (m * (m * 6.0 - 15.0) + 10.0);
    vec3 pos = mix(aSheet, position, m);
    pos.z += sin(m * 3.14159265) * (aSeed - 0.35) * 2.6;
    // On the map the dots drift a hair, so the picture is never quite still.
    pos += 0.025 * m * vec3(sin(uTime * 0.5 + aSeed * 40.0), cos(uTime * 0.43 + aSeed * 61.0), sin(uTime * 0.37 + aSeed * 17.0));

    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    float depth = max(0.1, -mv.z);
    float hovered = 1.0 - step(0.5, abs(aIndex - uHover));

    // Like a camera lens: dots away from the focus distance spread into soft discs.
    // On the map many passages almost share a place, so the dots there are a little finer.
    // The search: a wave leaves the question and touches every passage in turn.
    float wave = uRipple < 0.0 ? 0.0 : exp(-pow((distance(position, uOrigin) - uRipple) / 0.42, 2.0));
    float size = uSize * (1.0 - 0.22 * m) * (1.0 + hovered * 1.5 + wave * 0.9);
    float spread = size + uAperture * abs(depth - uFocus);
    gl_PointSize = clamp(spread * uPixels / depth, 1.5, 110.0);
    vPixels = gl_PointSize;
    vBlur = 1.0 - size / spread; // 0 = sharp, towards 1 = far out of focus

    // Afterwards only the closest stay lit.
    float light = uBright * (1.0 - 0.3 * m) * mix(1.0, mix(0.16, 0.95, step(0.5, aTier)), uDim);
    light += wave * 2.2 + hovered * 1.6;
    float arrive = clamp(uIntro * 1.4 - aSeed * 0.4, 0.0, 1.0);
    // A disc that spreads wider gets fainter, as real light would.
    vLight = light * arrive * pow(size / spread, 1.2);
    gl_Position = projectionMatrix * mv;
  }
`

const FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  varying float vLight;
  varying float vPixels;
  varying float vBlur;

  void main() {
    // In focus: a round dot with a clean edge, whatever its size.
    // Out of focus: a soft glow that fades towards its rim.
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float edge = clamp(2.5 / vPixels, 0.02, 0.9);
    float crisp = 1.0 - smoothstep(1.0 - edge, 1.0, r);
    float soft = pow(max(0.0, 1.0 - r * r), 2.0);
    float disc = mix(crisp, soft, smoothstep(0.0, 0.6, vBlur));
    if (disc <= 0.0) discard;
    // Anything brighter than full is passed on as extra light, which the glow picks up.
    gl_FragColor = vec4(uColor * max(1.0, vLight), min(1.0, vLight) * disc);
  }
`

export default function Passages({ stars, layout, plot }) {
  const material = useRef()
  const intro = useRef(0)
  const { grid } = layout

  const geometry = useMemo(() => {
    const n = stars.length
    const map = new Float32Array(n * 3), sheet = new Float32Array(n * 3)
    const seed = new Float32Array(n), index = new Float32Array(n), tier = new Float32Array(n)
    stars.forEach((s, i) => {
      map.set(s.position, i * 3)
      const col = i % grid.cols, row = Math.floor(i / grid.cols)
      sheet.set([col * grid.sp - grid.w / 2, grid.h / 2 - row * grid.sp, 0], i * 3)
      seed[i] = Math.random()
      index[i] = i
    })
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(map, 3))
    g.setAttribute('aSheet', new BufferAttribute(sheet, 3))
    g.setAttribute('aSeed', new BufferAttribute(seed, 1))
    g.setAttribute('aIndex', new BufferAttribute(index, 1))
    g.setAttribute('aTier', new BufferAttribute(tier, 1))
    return g
  }, [stars, grid.cols, grid.sp, grid.w, grid.h])
  useEffect(() => () => geometry.dispose(), [geometry])

  // Mark the passages that came closest to this question.
  useEffect(() => {
    const tier = geometry.getAttribute('aTier')
    stars.forEach((s, i) => { tier.array[i] = plot.near.has(s.id) ? 1 : 0 })
    tier.needsUpdate = true
  }, [geometry, stars, plot])

  const uniforms = useMemo(() => ({
    uMorph: { value: 1 }, uTime: { value: 0 }, uPixels: { value: 1000 }, uFocus: { value: 10 }, uAperture: { value: 0 },
    uBright: { value: 0.92 }, uDim: { value: 0 }, uRipple: { value: -1 }, uSize: { value: 0.055 }, uHover: { value: -1 },
    uIntro: { value: 0 }, uOrigin: { value: new Vector3() }, uColor: { value: new Color(INK) },
  }), [])

  const probe = useProbe(stars, layout)

  useFrame((state, dt) => {
    const u = material.current?.uniforms
    if (!u) return
    const p = tl.p
    intro.current = Math.min(1, intro.current + dt / (REDUCED ? 0.3 : 2.6))
    u.uIntro.value = intro.current
    u.uTime.value = REDUCED ? 0 : state.clock.elapsedTime
    u.uPixels.value = pixelsPerUnit(state.size.height * state.viewport.dpr)
    u.uFocus.value = tl.focus
    u.uAperture.value = tl.aperture
    // The dots wait as the sheet (it is also the backdrop of the title) until
    // chapter 5, when each one leaves for its place on the map.
    u.uMorph.value = smoother(4.02, 4.92, p)
    u.uDim.value = smooth(5.4, 5.95, p)
    u.uRipple.value = p > 5.03 && p < 5.85 ? ((p - 5.03) / 0.82) * 9 : -1
    if (plot.q) u.uOrigin.value.fromArray(plot.q)
    u.uHover.value = probe(state)
  })

  if (!stars.length) return null
  return (
    <points geometry={geometry} frustumCulled={false}>
      <shaderMaterial ref={material} vertexShader={VERTEX} fragmentShader={FRAGMENT} uniforms={uniforms} transparent depthWrite={false} depthTest={false} />
    </points>
  )
}

// Pointing at a dot shows which passage it is. Reading a few neighbours is how
// a visitor sees for themselves that nearby dots are about similar things.
// Returns the dot under the pointer (or -1), and moves a small label to it.
function useProbe(stars, layout) {
  const v = useMemo(() => new Vector3(), [])
  const last = useRef(-1)
  const { grid } = layout

  return (state) => {
    const el = tl.els.probe
    const p = tl.p
    const chapter = Math.round(p)
    const ptr = tl.pointer
    // Only when the picture is at rest on the sheet (4), the map (5) or the search (6).
    const active = ptr.inside && !tl.user.dragging && chapter >= 4 && chapter <= 6 && Math.abs(p - chapter) < 0.03
    let best = -1
    if (active) {
      const { width, height } = state.size
      let bestD = 14 * 14 // within 14 pixels
      for (let i = 0; i < stars.length; i++) {
        if (chapter === 4) v.set((i % grid.cols) * grid.sp - grid.w / 2, grid.h / 2 - Math.floor(i / grid.cols) * grid.sp, 0)
        else v.fromArray(stars[i].position)
        v.project(state.camera)
        const dx = (v.x * 0.5 + 0.5) * width - ptr.px, dy = (-v.y * 0.5 + 0.5) * height - ptr.py
        const d = dx * dx + dy * dy
        if (d < bestD) { bestD = d; best = i }
      }
    }
    if (el) {
      if (best >= 0) {
        if (best !== last.current) el.textContent = stars[best].breadcrumb.split(' › ').slice(1).join(' › ') || stars[best].breadcrumb
        // Keep the label inside the window: flip it to the left of the pointer near the right edge.
        const flip = ptr.px > state.size.width - 280
        el.style.transform = `translate3d(${ptr.px}px, ${ptr.py}px, 0) translate(${flip ? 'calc(-100% - 14px)' : '14px'}, -50%)`
        el.style.opacity = 1
      } else if (last.current >= 0) {
        el.style.opacity = 0
      }
    }
    last.current = best
    return best
  }
}
