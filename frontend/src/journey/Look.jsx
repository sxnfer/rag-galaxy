import { useEffect, useState } from 'react'
import { nameOf } from '../story.js'

const LEAVE_MS = 320 // the old picture fades out before the new one is swapped in, in step with the caption

// What the question looks like at each stop of the Journey, drawn from the
// real trace: words, then 384 numbers, then a list of passages, then a
// prompt, then an answer.
//
// It hangs from the question's point of light (Track.jsx), the way the
// question and its passages do at the end of the main film.
export default function Look({ id, trace }) {
  const [shown, setShown] = useState(id)
  const [on, setOn] = useState(true)

  useEffect(() => {
    if (id === shown) { setOn(true); return }
    setOn(false)
    const t = setTimeout(() => { setShown(id); setOn(true) }, LEAVE_MS)
    return () => clearTimeout(t)
  }, [id, shown])

  const Form = FORMS[shown]
  return (
    <div className={`look ${on ? 'on' : ''}`} aria-live="polite">
      {/* A new key per stop makes the lines start their entrance again. */}
      <div key={shown}>{Form && <Form trace={trace} />}</div>
    </div>
  )
}

const fmt = (x, places = 3) => x.toFixed(places).replace('-', '−')
const short = (text, n) => (text.length > n ? `${text.slice(0, n).trimEnd()}…` : text)
const Fine = ({ children }) => <p className="look-fine">{children}</p>

// One row of a short list: a small label, a name, and a figure.
function Rows({ rows }) {
  return (
    <ol className="look-rows">
      {rows.map((r) => (
        <li key={r.key}><span className="k">{r.k}</span><span className="name">{r.name}{r.dim && <i> · {r.dim}</i>}</span><span className="v">{r.v}</span></li>
      ))}
    </ol>
  )
}

// The stat columns in the order the table has them (the database doesn't keep the order of a card's numbers).
const COLUMNS = ['range_mi', 'range_city_mi', 'range_hwy_mi', 'mpge', 'kwh_per_100mi', 'charge_240v_h', 'annual_cost_usd']

const FORMS = {
  // Just words.
  typed: ({ trace }) => <p className="look-big">{trace.question}</p>,

  // Its numbers: every one as a thin bar (above the line is positive), and the first few written out.
  numbers: ({ trace }) => {
    const v = trace.retrieval.query_vector
    return (
      <>
        <svg className="look-bars" viewBox={`0 0 ${v.length} 100`} preserveAspectRatio="none" aria-hidden="true">
          {v.map((x, i) => {
            const height = Math.min(48, Math.max(1, Math.abs(x) * 420))
            return <rect key={i} x={i + 0.2} width={0.6} y={x >= 0 ? 50 - height : 50} height={height} opacity={x >= 0 ? 1 : 0.42} />
          })}
        </svg>
        <p className="look-code one">{v.slice(0, 6).map((x) => fmt(x)).join('   ')}   …</p>
      </>
    )
  },

  // The closest passages, in the order search found them, each with how close it is.
  compared: ({ trace }) => {
    const { rank, retrieval } = trace
    // With a rank stage, search's own order is kept in rank.before; without one, the hits are that order.
    const found = rank?.before?.length
      ? rank.before.map((b) => ({ key: b.chunk_id, name: b.item, dim: b.facet, v: fmt(b.score) }))
      : retrieval.hits.map((h) => ({ key: h.chunk_id, ...crumb(h.breadcrumb), v: fmt(h.score) }))
    const more = (rank?.candidates ?? found.length) - 5
    return (
      <>
        <Rows rows={found.slice(0, 5).map((f, i) => ({ ...f, k: i + 1 }))} />
        <Fine>{more > 0 ? `and ${more} more · ` : ''}1.000 would be the same meaning</Fine>
      </>
    )
  },

  // Before the question: one row of the table, and the card of words it became.
  before: ({ trace }) => {
    const h = trace.retrieval.hits[0]
    if (!h) return <p className="look-mid">No passage was found this time.</p>
    if (h.meta) {
      const numbers = COLUMNS.map((c) => h.meta.stats[c] ?? '').join(', ') // a blank stays blank, as in the table
      return (
        <>
          <p className="look-code one">row {h.meta.row}:  {h.meta.item}, {h.meta.class}, {numbers}</p>
          <Fine>became one of this car’s cards</Fine>
          <p className="look-prose">{h.text}</p>
        </>
      )
    }
    return (
      <>
        <p className="look-code one">{h.breadcrumb}</p>
        <Fine>was cut into this passage</Fine>
        <p className="look-prose">{short(h.text, 240)}</p>
      </>
    )
  },

  // What it asked for, and the candidates sorted by that.
  rank: ({ trace }) => {
    const { rank } = trace
    if (!rank.applied) return <><p className="look-mid">{rank.understood}</p><Fine>The order search gave was kept</Fine></>
    return (
      <>
        <p className="look-choice">{rank.understood.split(' · ').map((part) => <span key={part} className="on">{part}</span>)}</p>
        <Rows rows={rank.items.map((w, i) => ({ key: w.chunk_id, k: i + 1, name: w.item, v: `${w.value} ${w.unit}` }))} />
        <Fine>the best {rank.items.length} of {rank.candidates} candidates</Fine>
      </>
    )
  },

  // The passages the model will read, each with its label.
  evidence: ({ trace }) => {
    const { sources, dropped } = trace
    return (
      <>
        <Rows rows={sources.map((s) => ({ key: s.label, k: s.label, ...crumb(s.breadcrumb), v: s.pages }))} />
        {dropped.length > 0 && <Fine>{dropped.length} dropped: {[...new Set(dropped.map((d) => d.reason))].join(', ')}</Fine>}
      </>
    )
  },

  // What the model is sent: the passages, then the question.
  read: ({ trace }) => {
    const { sources, generation, question } = trace
    const first = sources[0]
    return (
      <>
        <pre className="look-code">
          {first && <>{'Sources:\n\n'}<b>[{first.label}]</b> {first.breadcrumb} ({first.pages}){'\n'}{short(first.text, 118)}{'\n\n'}</>}
          {sources.length > 1 && <>{`… ${sources.length - 1} more, `}<b>[S2]</b>{' to '}<b>[S{sources.length}]</b>{' …\n\n'}</>}
          <b>Question:</b> {question}
        </pre>
        {!generation?.input_tokens && <Fine>No answer was written: {generation?.skipped ?? 'generation failed'}</Fine>}
      </>
    )
  },

  // The answer, with every citation marked, and the verdict of the check.
  checked: ({ trace }) => {
    const { answer, check } = trace
    const found = answer && !check.not_found
    return (
      <>
        {found
          ? (
            <div className="look-answer">
              {answer.split('\n').filter((l) => l.trim()).slice(0, 6).map((line, n) => (
                <p key={n}>{line.split(/(\[S\d+\])/g).map((part, k) => {
                  const m = part.match(/^\[(S\d+)\]$/)
                  return m ? <span key={k} className="cite">{m[1]}</span> : part
                })}</p>
              ))}
            </div>
            )
          : <p className="look-mid">{answer ? 'The passages don’t contain the answer, so I say so.' : 'No answer was written this time.'}</p>}
        <Fine>
          {!answer ? 'Nothing to check'
            : check.not_found ? 'Passed: saying so is an honest answer'
              : check.passed ? `Passed: ${check.cited.join(', ')} ${check.cited.length === 1 ? 'is a passage' : 'are all passages'} that were sent`
                : `Not passed: ${check.problems.join('; ')}`}
        </Fine>
      </>
    )
  },

  // Home: its place on the map, the three numbers it is drawn from in the main film.
  // (A saved example gets its place from the server; until that arrives, it is simply the question again.)
  home: ({ trace }) => {
    const place = trace.retrieval.query_position
    return place
      ? <><p className="look-mid">{place.map((x) => fmt(x, 2)).join('   ')}</p><Fine>My place on the map</Fine></>
      : <p className="look-mid">{trace.question}</p>
  },
}

// A passage's name and kind, from its breadcrumb ("Electric cars › SUV › Lucid Gravity GT › Range").
function crumb(breadcrumb) {
  const { title, tag } = nameOf(breadcrumb)
  return { name: title, dim: tag.toLowerCase() }
}
