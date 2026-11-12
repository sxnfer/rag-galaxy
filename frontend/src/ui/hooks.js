import { useCallback, useEffect, useRef, useState } from 'react'

// Three things the films on the site need from the page.

// The size of the window, kept up to date.
export function useWindowSize() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight })
  useEffect(() => {
    const on = () => setSize({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return size
}

// Scrolling, the arrow keys and swipes all mean the same two things: onwards, or back.
//
// `ref.current` holds what the film wants right now:
//   on        false while the film should not react (another film is showing, or a question is being typed)
//   step(d)   move one chapter onwards (d = 1) or back (d = -1)
//   escape()  what the Esc key does
//   turning   true where a sideways drag turns the picture, so it must not also change chapter
export function useStepping(ref) {
  useEffect(() => {
    const cur = () => ref.current
    const typing = (e) => /^(INPUT|TEXTAREA)$/.test(e.target.tagName)

    function onKey(e) {
      if (!cur().on || typing(e) || e.metaKey || e.ctrlKey || e.altKey) return
      if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(e.key)) {
        if (/^(BUTTON|A)$/.test(e.target.tagName) && (e.key === ' ' || e.key === 'Enter')) return // let the button do its own thing
        e.preventDefault(); cur().step(1)
      }
      if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); cur().step(-1) }
      if (e.key === 'Escape') cur().escape()
    }

    // One scroll gesture = one chapter. A trackpad keeps sending small scroll
    // events for a second after the fingers lift, so after each step the film
    // ignores scrolling for a moment, and tiny movements never count.
    let sum = 0, lockedUntil = 0, lastAt = 0
    function onWheel(e) {
      if (!cur().on) return
      const box = e.target.closest?.('.answer')
      if (box && box.scrollHeight > box.clientHeight + 1) return // a long answer scrolls by itself
      const now = performance.now()
      if (now < lockedUntil) { lockedUntil = Math.max(lockedUntil, now + 120); return }
      if (now - lastAt > 200) sum = 0
      lastAt = now
      if (Math.abs(e.deltaY) < 4) return
      sum += e.deltaY
      if (Math.abs(sum) > 50) { cur().step(sum > 0 ? 1 : -1); sum = 0; lockedUntil = now + 900 }
    }

    let touch = null
    const onTouchStart = (e) => { touch = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null }
    function onTouchEnd(e) {
      if (!touch || !cur().on || e.target.closest?.('.answer, button, a')) return
      const dx = e.changedTouches[0].clientX - touch.x, dy = e.changedTouches[0].clientY - touch.y
      touch = null
      // A swipe up or to the left goes onwards. Where the picture can be turned, sideways drags turn it instead.
      if (Math.abs(dy) > 50 && Math.abs(dy) > Math.abs(dx)) cur().step(dy < 0 ? 1 : -1)
      else if (!cur().turning && Math.abs(dx) > 60) cur().step(dx < 0 ? 1 : -1)
    }

    window.addEventListener('keydown', onKey)
    window.addEventListener('wheel', onWheel, { passive: true })
    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchend', onTouchEnd, { passive: true })
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('wheel', onWheel)
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [ref])
}

const DIP_MS = 420 // how long the frame takes to go dark
const HOLD_MS = 90 // how long it stays dark while everything changes

// How many chapters apart counts as far. One or two are travelled; more are cut.
export const isFar = (from, to) => Math.abs(to - from) > 2

// A jump between chapters that are far apart is shown as a cut, not a journey:
// the frame dips to black, the film moves to the new chapter all at once, and
// the frame comes back. (Travelling there would play every chapter in between
// in a fraction of a second: a blur of half-finished pictures.)
//
// cut(to, apply) starts one: `apply` is called at the dark moment and should
// change the chapter. Until the frame is back, `busy.current` is true and
// further jumps should be ignored.
//   dark      the frame is fading to black, or black
//   cutting   the dark moment itself: everything on the page changes without easing
export function useCut(clock) {
  const [dark, setDark] = useState(false)
  const [cutting, setCutting] = useState(false)
  const busy = useRef(false)
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])

  const cut = useCallback((to, apply) => {
    if (busy.current) return
    busy.current = true
    setDark(true)
    timer.current = setTimeout(() => {
      // The story position goes straight there, at rest: nothing in between is drawn.
      Object.assign(clock, { target: to, a: to, av: 0, p: to, pv: 0 })
      setCutting(true)
      apply()
      timer.current = setTimeout(() => { setCutting(false); setDark(false); busy.current = false }, HOLD_MS)
    }, DIP_MS)
  }, [clock])

  return { dark, cutting, busy, cut }
}
