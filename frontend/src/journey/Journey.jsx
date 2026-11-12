import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import lines from 'virtual:code-lines'
import Track, { lightAt } from './Track.jsx'
import Look from './Look.jsx'
import Caption from '../ui/Caption.jsx'
import Nav from '../ui/Nav.jsx'
import { useStepping, useWindowSize } from '../ui/hooks.js'
import { askQuestion, getExamples, getLibraries } from '../api.js'
import { makeTimeline } from '../timeline.js'
import { PLACES, REPO, chaptersFor, context, refKey } from './stops.js'
import { SAMPLE } from './sample.js'

// The Journey: the same trip as the main film, told by the question itself.
//
// A third short film in the same language: a dark frame, one stop per
// chapter, a caption bottom left. The question is a point of light travelling
// along a line of stops (Track.jsx). Beneath it hangs what the question looks
// like at that stop, drawn from the real trace (Look.jsx). The caption says
// what is happening, in the question's own words, and names the code it is
// passing through (stops.js).

const clock = makeTimeline() // this film's own story position
// Where the visitor was, so that coming back from the search film returns to the same stop.
const kept = { id: null, chapter: 1 }

// While developing, the clock can be reached from the browser's console (try: __journey.target = 4.5).
if (import.meta.env?.DEV && typeof window !== 'undefined') window.__journey = clock

// Links point at the commit that was deployed, so the code a visitor reads is
// the code that ran. Set VITE_COMMIT when building; without it they point at main.
const COMMIT = import.meta.env.VITE_COMMIT || 'main'
const link = (r) => `${REPO}/blob/${COMMIT}/${r.file}#L${lines[refKey(r)]}`

// With no question asked yet, follow the first example (the server replays it
// at no cost). If the server can't be reached at all, follow an illustration.
async function borrow() {
  try {
    const { default: library } = await getLibraries()
    const { examples } = await getExamples(library)
    const first = examples.find((e) => e.ready)
    if (!first) throw new Error('no saved example')
    return { trace: await askQuestion(first.question, library), source: 'example' }
  } catch {
    return { trace: SAMPLE, source: 'sample' }
  }
}

export default function Journey({ film, onOpen, onClose }) {
  const { w, h } = useWindowSize()
  const [own, setOwn] = useState(null) // a trace fetched here, when the film has none to give
  const trace = film.trace ?? own?.trace ?? null
  const source = film.trace ? 'yours' : own?.source

  useEffect(() => {
    if (film.trace) return
    let wanted = true
    borrow().then((r) => { if (wanted) setOwn(r) })
    return () => { wanted = false }
  }, [film.trace])

  const chapters = useMemo(() => (trace ? chaptersFor(trace) : [null]), [trace])
  const last = chapters.length - 1
  const stops = useMemo(() => chapters.slice(1), [chapters])
  const ctx = useMemo(() => (trace ? context(trace, source) : {}), [trace, source])

  const [chapter, setChapter] = useState(1)
  // A new trace starts the journey from its beginning; the same one picks up where it was left.
  useEffect(() => {
    if (!trace) return
    const again = kept.id === trace.trace_id
    const start = again ? Math.min(kept.chapter, last) : 1
    Object.assign(kept, { id: trace.trace_id, chapter: start })
    setChapter(start)
    Object.assign(clock, { target: start, a: again ? start : 0, av: 0, p: again ? start : 0, pv: 0 })
  }, [trace, last])
  useEffect(() => { clock.target = chapter }, [chapter])

  const go = useCallback((n) => {
    const to = Math.max(1, Math.min(last, n))
    kept.chapter = to
    setChapter(to)
  }, [last])
  const stepping = useRef()
  stepping.current = { on: !!trace, step: (d) => go(chapter + d), escape: onClose, turning: false }
  useStepping(stepping)

  const stop = chapters[chapter]
  const at = lightAt(w, h)

  return (
    <div className="app journey" data-at={chapter} style={{ '--light-x': `${at.x * 100}%`, '--light-y': `${at.y * 100}%` }}>
      {trace && <Track stops={stops} clock={clock} w={w} h={h} />}

      <header className="top">
        <button className="mark" onClick={onClose} aria-label="RAG Galaxy, back to the film">RAG Galaxy</button>
        {/* Where the question is. Each place lights up while it is there. */}
        <p className="parts">
          {PLACES.map((x) => <span key={x.id} className={stop?.part === x.id ? 'on' : ''}>{x.label}</span>)}
        </p>
      </header>

      {trace && stop && <Look id={stop.id} trace={trace} />}

      <Caption
        chapter={chapter} chapters={chapters} ctx={ctx} onLink={onOpen}
        more={(c) => (
          <p className="code">
            {c.code.map((r) => (
              <a key={refKey(r)} href={link(r)} target="_blank" rel="noreferrer">{r.file} <b>{r.fn}</b></a>
            ))}
          </p>
        )}
      />
      {trace && <Nav chapter={chapter} last={last} first={1} go={go} end={{ label: 'Back to the film', go: onClose }} />}
    </div>
  )
}
