import { useCallback, useEffect, useState } from 'react'
import App from './App.jsx'
import Hnsw from './hnsw/Hnsw.jsx'
import Journey from './journey/Journey.jsx'

// The site is three films in one dark frame:
//
//   (no address)   the main film: follow a question to its answer       App.jsx
//   #hnsw          the search film: how millions are searched quickly   hnsw/
//   #journey       the journey: the same trip, told by the question     journey/
//
// This file decides which one is on screen, from the end of the address, and
// fades to black between them, like a cut between scenes. The main film stays
// loaded the whole time, so coming back finds it exactly where it was left.

const ADDRESS = { film: '', hnsw: '#hnsw', journey: '#journey' }
const read = () => Object.keys(ADDRESS).find((k) => k !== 'film' && ADDRESS[k] === window.location.hash) ?? 'film'
const FADE_MS = 450

export default function Site() {
  const [page, setPage] = useState(read)   // the film the address asks for
  const [shown, setShown] = useState(page) // the film on screen (it changes once the old one has faded out)
  const [out, setOut] = useState(false)    // true while the frame is black
  const [from, setFrom] = useState('film') // where the search film was opened from, so it can go back there
  const [film, setFilm] = useState({ trace: null, count: 0 }) // what the main film has to share with the other two

  // The browser's own back and forward buttons, or an address typed by hand.
  useEffect(() => {
    const on = () => setPage(read())
    window.addEventListener('popstate', on)
    window.addEventListener('hashchange', on)
    return () => { window.removeEventListener('popstate', on); window.removeEventListener('hashchange', on) }
  }, [])

  const open = useCallback((to) => {
    const here = read()
    if (to === here) return
    if (to === 'hnsw') setFrom(here)
    window.history.pushState(null, '', `${window.location.pathname}${window.location.search}${ADDRESS[to]}`)
    setPage(to)
  }, [])

  // Fade out, swap, fade in.
  useEffect(() => {
    if (page === shown) return
    setOut(true)
    const t = setTimeout(() => setShown(page), FADE_MS)
    return () => clearTimeout(t)
  }, [page, shown])
  useEffect(() => {
    const t = setTimeout(() => setOut(false), 60) // a moment for the new film to be on the page before it fades in
    return () => clearTimeout(t)
  }, [shown])

  const back = from === 'journey' ? 'journey' : 'film'
  return (
    <div className="site" data-out={out ? '' : undefined}>
      <App active={shown === 'film'} onOpen={open} onFilm={setFilm} />
      {shown === 'hnsw' && <Hnsw count={film.count} back={`Back to the ${back}`} onClose={() => open(back)} />}
      {shown === 'journey' && <Journey film={film} onOpen={open} onClose={() => open('film')} />}
    </div>
  )
}
