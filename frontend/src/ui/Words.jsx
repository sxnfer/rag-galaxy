import { useEffect, useRef } from 'react'

// The question, in the middle of the frame.
//
//   Chapter 0   it is being written: the same large line, but you can type in it
//   Chapter 1   it is simply shown
//   Chapter 2   it steps up and stays as a small label above its own numbers
//
// Because the line you type and the line the film shows are the same size in
// the same place, pressing Enter doesn't change the picture: the film has
// already begun. Where the line sits in each chapter is decided in styles.css.
export default function Words({ chapter, question, draft, onDraft, onAsk, placeholder, vector, show, focus = true }) {
  const box = useRef()
  const writing = chapter === 0
  const fmt = (x) => x.toFixed(3).replace('-', '−')

  // On the start page the cursor is always in the line, even after a click elsewhere.
  // (Not while another film is showing: `focus` is false then, and the line lets go of the keyboard.)
  useEffect(() => {
    if (!writing) return
    if (!focus) { box.current?.blur(); return }
    const take = () => box.current?.focus({ preventScroll: true })
    const onDown = (e) => { if (!e.target.closest?.('button, a, textarea')) setTimeout(take, 0) }
    take()
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [writing, focus])

  return (
    <div className="words" aria-live="polite">
      {writing ? (
        // A text box can't size itself to its words, so the label carries an
        // invisible copy of them (data-value) that does, and the box fills it.
        <label className={`words-q grow ${draft ? '' : 'empty'}`} data-value={draft || placeholder}>
          <textarea
            ref={box} rows={1} value={draft} placeholder={placeholder} maxLength={300}
            onChange={(e) => onDraft(e.target.value.replace(/\s*\n\s*/g, ' '))}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onAsk() } }}
            aria-label="Your question" autoComplete="off" autoCapitalize="off" spellCheck={false} enterKeyHint="go"
          />
        </label>
      ) : (
        <p className="words-q">{question}</p>
      )}
      {/* The first few of the real numbers, so the bars are not an abstraction. */}
      <p className="words-n">
        {show && vector && <>{vector.slice(0, 7).map(fmt).join('   ')}   …   <b>{vector.length} numbers</b></>}
      </p>
    </div>
  )
}
