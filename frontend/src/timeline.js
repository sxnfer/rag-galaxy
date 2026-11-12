// The story's clock.
//
// The whole film is driven by one number, p: "how far through the story are we?"
// p = 0 is the title, p = 3 is chapter 3, and p = 3.4 is 40% of the way from
// chapter 3 to chapter 4. Everything in the 3D scene is drawn from p alone, so
// the film can play forwards, backwards, or stop anywhere, and always looks right.
//
// React decides which chapter we are heading to (target). The scene glides p
// towards it a little every frame (see Driver in scene/Rig.jsx).
//
// This is a plain object, not React state, on purpose: it changes 60 times a
// second, and re-rendering the page that often would make it stutter.
// Each film has its own clock. They all have the same parts.
export function makeTimeline() {
  return {
    target: 0,      // the chapter we are heading to
    a: 0, av: 0,    // a half-way value that follows target (it softens the start of each move)
    p: 0, pv: 0,    // the story position that follows a
    focus: 10,      // how far from the camera things are sharp
    aperture: 0,    // how quickly things blur away from that distance
    pointer: { x: 0, y: 0, tx: 0, ty: 0, px: -1, py: -1, inside: false }, // the mouse, smoothed
    user: { yaw: 0, pitch: 0, ty: 0, tp: 0, dragging: false },            // how far the visitor has turned the view
    hover: -1,      // which source the visitor is pointing at in the answer
    els: { cards: [], ask: null, probe: null }, // page elements that follow points in the 3D scene
  }
}

// The main film's clock.
export const tl = makeTimeline()

// While developing, the clock can be reached from the browser's console (try: __tl.target = 4.5).
if (import.meta.env?.DEV && typeof window !== 'undefined') window.__tl = tl

export const REDUCED = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x))
export const lerp = (a, b, t) => a + (b - a) * t

// 0 before a, 1 after b, and a gentle S-curve in between: slow, quick, slow.
export function smooth(a, b, x) {
  const t = clamp((x - a) / (b - a))
  return t * t * (3 - 2 * t)
}
// The same, with an even softer start and stop.
export function smoother(a, b, x) {
  const t = clamp((x - a) / (b - a))
  return t * t * t * (t * (t * 6 - 15) + 10)
}

// Move `cur` towards `target` like something with weight: it speeds up, then
// settles without overshooting. Returns the new value and the new speed.
export function glide(cur, target, vel, time, dt) {
  const omega = 2 / time
  const x = omega * dt
  const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x)
  const change = cur - target
  const temp = (vel + omega * change) * dt
  return [target + (change + temp) * exp, (vel - omega * temp) * exp]
}
