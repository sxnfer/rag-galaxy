import { LAST } from '../story.js'

const Arrow = ({ back }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" style={back ? { transform: 'scaleX(-1)' } : undefined}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
)

// Where you are in a film, and the way onwards: one mark per chapter, and
// two arrows. Scrolling and the arrow keys do the same thing (ui/hooks.js).
//
// The main film begins at chapter 0, its start page: there the same arrow, in
// the same place, sends the question. The two smaller films begin at chapter 1
// (first = 1) and say what their last button does with `end`.
export default function Nav({ chapter, last = LAST, first = 0, go, waiting, ready = true, canAsk, onAsk, end }) {
  const home = first === 0 && chapter === 0
  const start = chapter === first
  const held = first === 0 && chapter === 1 && !ready // the server is still working on the question
  return (
    <nav className="nav" aria-label="Chapters">
      <button className={`nav-arrow ${start ? 'gone' : ''}`} onClick={() => go(chapter - 1)} disabled={start} aria-label="Previous chapter"><Arrow back /></button>
      <ol className="ticks">
        {Array.from({ length: last }, (_, i) => i + 1).map((n) => (
          <li key={n}>
            <button
              className={n === chapter ? 'on' : n < chapter ? 'past' : ''}
              onClick={() => go(n)} disabled={home || (n >= 2 && !ready)}
              aria-label={`Chapter ${n}`} aria-current={n === chapter ? 'step' : undefined}
            />
          </li>
        ))}
      </ol>
      {chapter === last
        ? <button className="nav-next again" onClick={end ? end.go : () => go(0)}>{end ? end.label : 'Ask another'}</button>
        : home
          ? <button className="nav-next" onClick={onAsk} disabled={!canAsk} aria-label="Follow this question"><Arrow /></button>
          : (
          <button className={`nav-next ${held && waiting ? 'held' : ''}`} onClick={() => go(chapter + 1)} disabled={held} aria-label={held ? 'Searching the library' : 'Next chapter'}>
            <Arrow />
          </button>
        )}
    </nav>
  )
}
