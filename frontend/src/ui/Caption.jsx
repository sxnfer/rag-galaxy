import { useEffect, useState } from 'react'
import { CHAPTERS } from '../story.js'

const LEAVE_MS = 320 // the old words fade out before the new ones are swapped in

// The caption, bottom left: the chapter's number, its title, and one or two sentences.
// When the chapter changes, the old caption fades out first, then the new one
// drifts in a moment later, so the words arrive while the picture is moving.
//
// Every film on the site uses it. `chapters` is that film's list of chapters,
// and `ctx` holds the figures its sentences ask for.
//   intro      what to show for chapter 0, if the film has a start page
//   hold(n)    true while chapter n's words can't be written yet
//   onLink     called when a chapter's link (a way into another film) is pressed
//   more(c)    anything else a film wants under a chapter's words
//   cut        true during a cut between far-apart chapters (ui/hooks.js): the words change at once
export default function Caption({ chapter, chapters = CHAPTERS, ctx, intro, hold, onLink, more, cut = false }) {
  const [shown, setShown] = useState(chapter)
  const [on, setOn] = useState(true)

  useEffect(() => {
    if (chapter === shown) { setOn(true); return }
    if (cut) { setShown(chapter); setOn(true); return } // the frame is black: no need to fade the old words out first
    setOn(false)
    const t = setTimeout(() => { setShown(chapter); setOn(true) }, LEAVE_MS)
    return () => clearTimeout(t)
  }, [chapter, shown, cut])

  // Chapter 0, the start page, has its own caption with things to press (Intro.jsx).
  if (shown === 0 && intro) return <section className={`caption intro ${on ? 'on' : ''}`}><div key={0}>{intro}</div></section>

  const c = chapters[shown]
  if (!c || hold?.(shown)) return <section className="caption" />
  const text = (x) => (typeof x === 'function' ? x(ctx) : x)
  const note = text(c.note)

  return (
    <section className={`caption ${on ? 'on' : ''}`} aria-live="polite">
      {/* A new key per chapter makes the lines start their entrance again. */}
      <div key={shown}>
        <p className="caption-n">{String(shown).padStart(2, '0')}</p>
        <h2>{text(c.title)}</h2>
        <p className="caption-body">{text(c.body)}</p>
        {note && <p className="caption-note">{note}</p>}
        {c.hint && <p className="caption-note hint">{c.hint}</p>}
        {more?.(c)}
        {c.link && onLink && (
          <button type="button" className="caption-link" onClick={() => onLink(c.link.to)}>
            {text(c.link.label)}
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
          </button>
        )}
      </div>
    </section>
  )
}
