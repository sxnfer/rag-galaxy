import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Scene from './Scene.jsx'
import Caption from '../ui/Caption.jsx'
import Nav from '../ui/Nav.jsx'
import { isFar, useCut, useStepping, useWindowSize } from '../ui/hooks.js'
import { makeTimeline } from '../timeline.js'
import { buildGraph, FLOORS, N, schedule, walk } from './graph.js'
import { CHAPTERS, LAST, PARTS } from './story.js'

// The search film: how a library of millions is searched without comparing
// the question with every passage (HNSW).
//
// It is a second, shorter film in the same language as the main one: a dark
// frame, one idea per chapter, a caption bottom left, and the same ways of
// moving through it. The picture is in Scene.jsx, the words in story.js and
// the small graph it walks in graph.js.

const clock = makeTimeline() // this film's own story position

// While developing, the clock can be reached from the browser's console (try: __hnsw.target = 4.5).
if (import.meta.env?.DEV && typeof window !== 'undefined') window.__hnsw = clock

export default function Hnsw({ count, back, onClose }) {
  const { w, h } = useWindowSize()
  const [chapter, setChapter] = useState(1)

  // The graph, and the two walks through it: the ground floor alone, and all three floors.
  const graph = useMemo(() => buildGraph(), [])
  const walks = useMemo(() => {
    const ground = walk(graph, [0]), floors = walk(graph, [2, 1, 0])
    const quick = { look: 0.2, hop: 0.24, appear: 0.5, rest: 0.4 } // fifteen short steps: keep them brisk
    const slow = { fall: 0.8, look: 0.6, hop: 0.7, appear: 0.7, rest: 0.5 }
    const firstDown = floors.findIndex((s) => s.floor < FLOORS - 1) // the first step below the top floor
    const sum = (steps) => ({ steps: steps.at(-1).hops, seen: steps.at(-1).seen })
    return {
      ground: { ...schedule(ground, 0, ground.length, quick), ...sum(ground) },
      top: schedule(floors, 0, firstDown, slow),
      down: schedule(floors, firstDown, floors.length, slow),
      floors: sum(floors),
    }
  }, [graph])

  // Every visit starts the film from its beginning.
  useEffect(() => {
    Object.assign(clock, { target: 1, a: 0, av: 0, p: 0, pv: 0 })
    clock.user.ty = clock.user.tp = clock.user.yaw = clock.user.pitch = 0
  }, [])
  useEffect(() => {
    clock.target = chapter
    clock.user.ty = 0; clock.user.tp = 0 // a new chapter brings its own view
  }, [chapter])

  // The next chapter or two are travelled to; a jump further than that is a cut (ui/hooks.js).
  const { dark, cutting, busy, cut } = useCut(clock)
  const go = useCallback((n) => {
    const to = Math.max(1, Math.min(LAST, n))
    if (to === chapter || busy.current) return
    if (isFar(chapter, to)) cut(to, () => setChapter(to))
    else setChapter(to)
  }, [chapter, busy, cut])
  const stepping = useRef()
  stepping.current = { on: !dark, step: (d) => go(chapter + d), escape: onClose, turning: chapter >= 4 }
  useStepping(stepping)

  const ctx = useMemo(() => ({ count, total: N, ground: walks.ground, floors: walks.floors }), [count, walks])
  const part = CHAPTERS[chapter].part

  return (
    <div className="app hnsw" data-at={chapter} data-dark={dark ? '' : undefined} data-cut={cutting ? '' : undefined}>
      <Scene graph={graph} walks={walks} clock={clock} w={w} h={h} />

      <header className="top">
        <button className="mark" onClick={onClose} aria-label={`RAG Galaxy, ${back.toLowerCase()}`}>RAG Galaxy</button>
        {/* The three words of HNSW. Each lights up when the film reaches it. */}
        <p className="parts">
          {PARTS.map((x) => <span key={x.id} className={part === x.id || part === 'all' ? 'on' : ''}>{x.label}</span>)}
        </p>
      </header>

      {/* Words that follow points in the picture: the scene moves them every frame. */}
      <div className="tag" ref={(el) => { clock.els.question = el }}><span>Your question</span></div>
      {graph.floors.map((f, L) => (
        <div className="tag floor" key={L} ref={(el) => { (clock.els.floors ??= [])[L] = el }}><span>{f.ids.length} passages</span></div>
      ))}

      <Caption
        chapter={chapter} chapters={CHAPTERS} ctx={ctx} cut={cutting}
        more={(c) => c.live && <p className="caption-note" data-kind={c.live} ref={(el) => { clock.els.count = el }} />}
      />
      <Nav chapter={chapter} last={LAST} first={1} go={go} end={{ label: back, go: onClose }} />
    </div>
  )
}
