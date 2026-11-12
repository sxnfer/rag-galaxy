import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Stage from './scene/Stage.jsx'
import Intro from './ui/Intro.jsx'
import Words from './ui/Words.jsx'
import Handoff from './ui/Handoff.jsx'
import Caption from './ui/Caption.jsx'
import Nav from './ui/Nav.jsx'
import { isFar, useCut, useStepping, useWindowSize } from './ui/hooks.js'
import { askQuestion, getExamples, getLibraries, getStars } from './api.js'
import { buildLayout, handoff } from './layout.js'
import { CHAPTERS, LAST, PARTS, context } from './story.js'
import { tl } from './timeline.js'

// The main film: one short film about one question.
//
//   Chapter 0   the start page: the same dark frame, with a line to type a question in
//   Chapters 1 to 8   what happens to it, one idea at a time (story.js)
//
// This file holds the few facts the page needs (which chapter we are on, the
// question, and the trace: the server's record of what it did with the question)
// and listens for the ways a visitor can move through the film: scrolling,
// the arrow keys, swiping, or the buttons.
//
// The 3D scene (scene/) draws the film. The pieces in ui/ are the words on top.
//
// Two smaller films branch off it (Site.jsx): the search film from chapter 6,
// and the journey from chapter 8. While one of them is showing, `active` is
// false: this film stops drawing and listening, and keeps its place.

// Which library to open: ?library=<id> in the address wins, so a link can point at one.
const fromUrl = () => new URLSearchParams(window.location.search).get('library')

export default function App({ active = true, onOpen, onFilm }) {
  const { w, h } = useWindowSize()
  const [libraries, setLibraries] = useState([])
  const [library, setLibrary] = useState(null)
  const [stars, setStars] = useState([])       // every passage of the library, with its place on the map
  const [examples, setExamples] = useState([])
  const [draft, setDraft] = useState('')       // the question while it is being typed
  const [question, setQuestion] = useState('') // the question once it has been asked
  const [trace, setTrace] = useState(null)     // what the server did with the question
  const [waiting, setWaiting] = useState(false) // the question is with the server
  const [chapter, setChapter] = useState(0)
  const [error, setError] = useState(null)
  const [hover, setHover] = useState(-1)       // which source is being pointed at
  const [waking, setWaking] = useState(false)  // the server is taking its time to answer the first call

  // The live server sleeps when nobody is visiting, and takes a little while to
  // wake for the first visitor. So a slow or failed first call is not an error
  // yet: the page says the server is waking, and keeps trying for a while.
  useEffect(() => {
    let wanted = true, tries = 0, again
    const slow = setTimeout(() => wanted && setWaking(true), 2500)
    function load() {
      getLibraries()
        .then((r) => {
          if (!wanted) return
          clearTimeout(slow)
          setLibraries(r.libraries)
          const asked = r.libraries.find((l) => l.id === fromUrl() && l.ready)
          setLibrary(asked?.id ?? r.default)
        })
        .catch(() => {
          if (!wanted) return
          if (++tries < 10) { setWaking(true); again = setTimeout(load, 4000) }
          else { clearTimeout(slow); setWaking(false); setError('Could not reach the server. Please refresh in a moment.') }
        })
    }
    load()
    return () => { wanted = false; clearTimeout(slow); clearTimeout(again) }
  }, [])

  // Each library brings its own passages and example questions.
  useEffect(() => {
    if (!library) return
    getStars(library).then((r) => setStars(r.stars)).catch(() => setError('Could not load the library. Please refresh in a moment.'))
    getExamples(library).then((r) => setExamples(r?.examples ?? [])).catch(() => {})
  }, [library])

  const ready = !!trace && !waiting
  const { dark, cutting, busy, cut } = useCut(tl)

  // Move to a chapter. Past chapter 1 the film needs the trace, so it waits for it.
  // The next chapter or two are travelled to. Anything further is a cut: the frame
  // dips to black and returns on the new chapter. That is how "Ask another" goes
  // from the answer back to the start, without running the whole film backwards.
  const go = useCallback((n) => {
    const to = Math.max(0, Math.min(LAST, n))
    if (to === chapter || busy.current) return
    if (to >= 2 && !ready) return
    if (to >= 1 && !question) return
    // Stepping back from the first chapters leaves the question in the line to edit; otherwise the line starts empty.
    if (to === 0) setDraft(chapter <= 2 ? question : '')
    if (isFar(chapter, to)) cut(to, () => setChapter(to))
    else setChapter(to)
  }, [ready, question, chapter, busy, cut])

  useEffect(() => {
    tl.target = chapter
    tl.user.ty = 0; tl.user.tp = 0 // a new chapter brings its own view
    tl.hover = -1
    setHover(-1)
  }, [chapter])

  const ask = useCallback(async (text) => {
    setDraft(text)
    setQuestion(text)
    setError(null)
    setWaiting(true)
    setChapter(1) // the film can begin at once: chapter 1 only needs the words
    try {
      setTrace(await askQuestion(text, library))
    } catch (e) {
      setError(e.message)
      setChapter(0)
    } finally {
      setWaiting(false)
    }
  }, [library])

  // Scrolling, keys and swipes all mean the same two things: onwards, or back.
  const stepping = useRef()
  stepping.current = {
    on: active && chapter !== 0 && !dark, // on the start page the keys are for typing
    step: (d) => go(chapter + d),
    escape: () => go(0),
    turning: chapter === 5 || chapter === 6, // on the map, sideways drags turn the view
  }
  useStepping(stepping)

  // The other two films use what this one knows: the latest trace, and the size of the library.
  useEffect(() => { onFilm?.({ trace, count: stars.length }) }, [onFilm, trace, stars.length])

  const lib = libraries.find((l) => l.id === library)
  const sources = useMemo(() => trace?.sources ?? [], [trace])
  const layout = useMemo(() => buildLayout(w, h, stars.length), [w, h, stars.length])
  const hand = useMemo(() => handoff(w, h, sources.length), [w, h, sources.length])
  const ctx = useMemo(() => context(trace, stars.length), [trace, stars.length])
  const part = CHAPTERS[chapter]?.part

  function point(i) { tl.hover = i; setHover(i) }

  // Sending the typed question: Enter in the line, or the arrow.
  const loaded = stars.length > 0
  const canAsk = loaded && draft.trim().length > 0
  function send() { if (canAsk) ask(draft.trim()) }

  return (
    <div className="app" data-ch={chapter} data-wide={hand.wide ? '' : undefined} data-off={active ? undefined : ''} data-dark={dark ? '' : undefined} data-cut={cutting ? '' : undefined}>
      <Stage stars={stars} trace={trace} layout={layout} hand={hand} playing={active} />

      <header className="top">
        <button className="mark" onClick={() => go(0)} disabled={chapter === 0} aria-label="RAG Galaxy, back to the start">RAG Galaxy</button>
        {/* The three words of RAG. Each lights up when the film reaches it. */}
        <p className="parts">
          {PARTS.map((x) => <span key={x.id} className={x.id === part ? 'on' : ''}>{x.label}</span>)}
        </p>
      </header>

      <Words
        chapter={chapter} question={question} draft={draft} onDraft={setDraft} onAsk={send}
        placeholder={lib ? `Ask about ${lib.title.toLowerCase()}` : 'Ask a question'}
        vector={trace?.retrieval?.query_vector} show={ready} focus={active}
      />
      <Handoff trace={trace} question={question} hand={hand} hover={hover} onPoint={point} />
      <div className="probe" ref={(el) => { tl.els.probe = el }} />

      <Caption
        chapter={chapter} ctx={ctx} hold={(n) => n >= 2 && !ctx.trace} onLink={onOpen} cut={cutting}
        intro={<Intro lib={lib} libraries={libraries} library={library} onLibrary={setLibrary} examples={examples} onAsk={ask} onOpen={onOpen} error={error} ready={loaded} waking={waking && !loaded && !error} />}
      />
      <Nav chapter={chapter} go={go} waiting={waiting} ready={ready} canAsk={canAsk} onAsk={send} />
    </div>
  )
}
