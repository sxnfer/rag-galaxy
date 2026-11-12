import { nameOf } from '../story.js'
import { tl } from '../timeline.js'

// The hand-off (chapters 7 and 8): what goes into the language model, and what
// comes out.
//
//   above the line   the question and the passages that were found  (what it reads)
//   below the line   the answer, with a mark for every source       (what it writes)
//
// The question and each passage hang from a point of light in the 3D scene:
// the scene moves these elements every frame (Lights.jsx), so the words arrive
// with their light.
export default function Handoff({ trace, question, hand, hover, onPoint }) {
  const sources = trace?.sources ?? []
  const cited = new Set(trace?.check?.cited ?? [])
  const style = { '--card-w': `${hand.cardW}px`, '--answer-top': `${hand.answerTop}px` }

  return (
    <div className="handoff" style={style}>
      <div className="pin ask-pin" ref={(el) => { tl.els.ask = el }}>
        <p>{question}</p>
      </div>

      {sources.map((s, i) => {
        const { title, tag } = nameOf(s.breadcrumb)
        return (
          <div className="pin card-pin" key={s.label} ref={(el) => { tl.els.cards[i] = el }}>
            <article
              className={`card ${hover === i ? 'lit' : ''} ${hover >= 0 && hover !== i ? 'dim' : ''} ${cited.size && !cited.has(s.label) ? 'unused' : ''}`}
              style={{ '--i': i }}
              onPointerEnter={() => onPoint(i)} onPointerLeave={() => onPoint(-1)}
            >
              <span className="card-label">{s.label}{tag && <span className="tag"> · {tag}</span>}</span>
              <h3>{title}</h3>
              <p>{s.text}</p>
            </article>
          </div>
        )
      })}

      <div className="model-line"><span>Language model</span></div>
      <Answer trace={trace} sources={sources} onPoint={onPoint} />
    </div>
  )
}

// The answer, one line at a time, with each [S1]-style citation turned into a
// small mark. Pointing at a mark lights the passage it came from.
function Answer({ trace, sources, onPoint }) {
  const answer = trace?.answer
  if (!answer || trace.check?.not_found) {
    return (
      <div className="answer">
        <p className="answer-line quiet" style={{ '--i': 0 }}>
          {answer ? 'These passages don’t contain the answer.' : 'No answer was written this time.'}
        </p>
      </div>
    )
  }
  const index = (label) => sources.findIndex((s) => s.label === label)
  const lines = answer.split('\n').filter((l) => l.trim())
  return (
    <div className="answer">
      {lines.map((line, n) => (
        <p className="answer-line" key={n} style={{ '--i': n }}>
          {line.split(/(\[S\d+\])/g).map((part, k) => {
            const m = part.match(/^\[(S\d+)\]$/)
            if (!m) return part
            const i = index(m[1])
            return (
              <button
                key={k} className="cite" aria-label={`Source ${m[1]}`}
                onPointerEnter={() => onPoint(i)} onPointerLeave={() => onPoint(-1)}
                onFocus={() => onPoint(i)} onBlur={() => onPoint(-1)}
              >{m[1]}</button>
            )
          })}
        </p>
      ))}
    </div>
  )
}
