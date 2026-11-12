import { useState } from 'react'

// What the caption says on the start page: what this is, a few questions to
// begin with, and a way into the two smaller films. The examples were
// answered ahead of time, so they play at once.
export default function Intro({ lib, libraries, library, onLibrary, examples, onAsk, onOpen, error, ready, waking }) {
  const [open, setOpen] = useState(false) // the data credit: one quiet line until asked for
  const choices = libraries.filter((l) => l.ready)
  return (
    <>
      <h2>Follow a question to its answer.</h2>
      <p className="caption-body">See how an AI looks things up before it speaks. Type a question, or begin with one of these.</p>

      {choices.length > 1 && (
        <p className="libraries">
          {choices.map((l) => (
            <button key={l.id} type="button" className={l.id === library ? 'on' : ''} onClick={() => onLibrary(l.id)}>{l.title}</button>
          ))}
        </p>
      )}

      {/* The live server sleeps when idle: say so while it wakes, instead of showing nothing. */}
      {waking && <p className="waking" role="status">Waking the server. It sleeps when nobody is visiting, so the first visit takes a moment.</p>}

      <ul className="examples">
        {examples.map((ex) => (
          <li key={ex.question}><button type="button" disabled={!ready} onClick={() => onAsk(ex.question)}>{ex.question}</button></li>
        ))}
      </ul>

      {/* The two smaller films (Site.jsx). They need no question, so they can be opened from here. */}
      <p className="also">
        <button type="button" onClick={() => onOpen('hnsw')}>How search stays fast</button>
        <button type="button" onClick={() => onOpen('journey')}>The question’s journey</button>
      </p>

      {error && <p className="error" role="alert">{error}</p>}
      {lib?.credit && (
        <button type="button" className={`credit ${open ? 'open' : ''}`} onClick={() => setOpen(!open)} aria-expanded={open}>{lib.credit}</button>
      )}
    </>
  )
}
