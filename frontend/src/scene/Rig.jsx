import { useEffect, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import { Spherical, Vector3 } from 'three'
import { REDUCED, clamp, glide, lerp, smoother, tl } from '../timeline.js'

// The three things every film needs to move: something that advances the
// story position, a camera that follows it, and the visitor's mouse.
// Each takes a clock (timeline.js), so each film runs on its own.

const EASE = REDUCED ? 0.1 : 0.44 // how unhurried each move between chapters is, in seconds
const REWIND = 1.1                // going back is quick, however long the way forward took

// Moves the story position (clock.p) towards the chapter we are heading to.
//
// Without `pace`, it follows a half-way value rather than the target itself,
// which gives every move a soft start as well as a soft landing, like a camera
// on a dolly.
//
// With `pace`, each move takes a set number of seconds at a steady speed:
// pace(n) is how long the way from chapter n to n + 1 takes. The search film
// uses this, because a walk of fifteen steps needs longer than a camera move.
export function Driver({ clock = tl, pace }) {
  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05) // a long pause (a hidden tab) must not become a jump
    if (!pace) {
      ;[clock.a, clock.av] = glide(clock.a, clock.target, clock.av, EASE, dt)
      ;[clock.p, clock.pv] = glide(clock.p, clock.a, clock.pv, EASE, dt)
    } else {
      const gap = clock.target - clock.a
      if (gap !== 0) {
        const dir = Math.sign(gap)
        const from = dir > 0 ? Math.floor(clock.a + 1e-6) : Math.ceil(clock.a - 1e-6) - 1
        const seconds = REDUCED ? 0.4 : dir > 0 ? pace(from) : REWIND
        const hurry = 1 + 3 * Math.max(0, Math.abs(gap) - 1) // skipping several chapters doesn't play each in full
        const step = (dt / seconds) * hurry
        clock.a = Math.abs(gap) <= step ? clock.target : clock.a + dir * step
      }
      ;[clock.p, clock.pv] = glide(clock.p, clock.a, clock.pv, 0.2, dt)
    }
    if (Math.abs(clock.p - clock.target) < 0.0004 && Math.abs(clock.pv) < 0.001) { clock.p = clock.a = clock.target; clock.pv = clock.av = 0 }
  }, -2)
  return null
}

// The camera. Each chapter has a shot (layout.js): where to stand and what to
// look at. Between chapters the camera travels in a straight line from one shot
// to the next, at the pace of the story position.
// On top of that it drifts a little by itself, leans slightly with the mouse,
// and where a shot allows it the visitor can drag to turn the view.
// `soft` makes each move start and stop gently by itself, for a clock that runs at a steady speed.
export function Rig({ shots, clock = tl, soft = false }) {
  const look = useMemo(() => new Vector3(), [])
  const off = useMemo(() => new Vector3(), [])
  const sph = useMemo(() => new Spherical(), [])

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05)
    const p = clamp(clock.p, 0, shots.length - 1)
    const i = Math.min(Math.floor(p), shots.length - 2)
    const f = soft ? smoother(0, 1, p - i) : p - i
    const A = shots[i], B = shots[i + 1]
    const mix = (k) => lerp(A[k], B[k], f)

    look.set(lerp(A.look[0], B.look[0], f), lerp(A.look[1], B.look[1], f), lerp(A.look[2], B.look[2], f))
    off.set(lerp(A.pos[0], B.pos[0], f), lerp(A.pos[1], B.pos[1], f), lerp(A.pos[2], B.pos[2], f)).sub(look)

    // Smooth the mouse and the visitor's dragging, so nothing ever snaps.
    const k = 1 - Math.exp(-4 * dt)
    const ptr = clock.pointer, user = clock.user
    ptr.x += (ptr.tx - ptr.x) * k
    ptr.y += (ptr.ty - ptr.y) * k
    user.yaw += (user.ty - user.yaw) * k * 1.6
    user.pitch += (user.tp - user.pitch) * k * 1.6

    const t = REDUCED ? 0 : state.clock.elapsedTime
    const yaw = Math.sin(t * 0.06) * 0.5 * mix('sway') - ptr.x * 0.045 * mix('parallax') - user.yaw * mix('orbit')
    const pitch = Math.sin(t * 0.045 + 1) * 0.05 * mix('sway') + ptr.y * 0.03 * mix('parallax') + user.pitch * mix('orbit')
    sph.setFromVector3(off)
    sph.theta += yaw
    sph.phi = clamp(sph.phi - pitch, 0.3, Math.PI - 0.3)
    off.setFromSpherical(sph)

    state.camera.position.copy(look).add(off)
    state.camera.lookAt(look)
    state.camera.updateMatrixWorld()
    clock.focus = mix('focus')
    clock.aperture = mix('aperture')
  }, -1)
  return null
}

// The mouse: where it is (for the lean and for reading dots), and dragging.
// `canDrag()` says whether the picture on screen right now may be turned.
export function usePointer(clock, canDrag) {
  useEffect(() => {
    const ptr = clock.pointer, user = clock.user
    let last = null
    const move = (e) => {
      ptr.inside = true
      ptr.px = e.clientX; ptr.py = e.clientY
      ptr.tx = (e.clientX / window.innerWidth) * 2 - 1
      ptr.ty = (e.clientY / window.innerHeight) * 2 - 1
      if (last && user.dragging) {
        user.ty = clamp(user.ty + (e.clientX - last.x) * 0.005, -1.4, 1.4)
        user.tp = clamp(user.tp + (e.clientY - last.y) * 0.004, -0.5, 0.5)
        last = { x: e.clientX, y: e.clientY }
      }
    }
    const down = (e) => {
      if (e.target.closest?.('button, a, input, .answer')) return
      if (canDrag()) { user.dragging = true; last = { x: e.clientX, y: e.clientY } }
    }
    const up = () => { user.dragging = false; last = null }
    const leave = () => { ptr.inside = false; ptr.tx = 0; ptr.ty = 0 }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerdown', down)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    document.documentElement.addEventListener('pointerleave', leave)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
      document.documentElement.removeEventListener('pointerleave', leave)
    }
  }, [clock]) // eslint-disable-line react-hooks/exhaustive-deps
}
