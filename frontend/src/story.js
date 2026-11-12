// The story, chapter by chapter. Every word a visitor reads during the film
// lives here, so the words can be edited without touching the 3D code.
//
// Each chapter is one idea: a title, and one or two plain sentences. Some
// sentences use real figures from this question's trace (the record of what
// the server did with it), so each is written as a small function.
//
// `part` says which word of "retrieval-augmented generation" the chapter
// belongs to; that word lights up at the top of the screen.
// `link` is a quiet way into one of the two smaller films (Site.jsx).

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
const word = (n) => WORDS[n] ?? String(n)
const many = (n) => n.toLocaleString('en')
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const passages = (n) => (n === 1 ? 'one passage' : `${word(n)} passages`)

export const LAST = 8

export const CHAPTERS = [
  null, // 0 is the title screen
  {
    part: null,
    title: 'It begins as words.',
    body: () => 'A language model answers from memory, and memory can be wrong or out of date. Retrieval-augmented generation, RAG for short, lets it look things up first.',
  },
  {
    part: 'retrieval',
    title: 'Words become numbers.',
    body: ({ dims }) => `A computer can’t compare meanings, only numbers. So a small model reads your question and writes down ${dims} of them. Each bar is one number. Together they are called an embedding.`,
  },
  {
    part: 'retrieval',
    title: 'Numbers become a place.',
    body: () => 'Read the numbers as coordinates, like latitude and longitude, and your question becomes a single point. Questions that mean similar things land close together.',
  },
  {
    part: 'retrieval',
    title: 'The library was ready long before.',
    body: ({ count }) => `Before you asked anything, the source was cut into ${many(count)} short passages, each small enough to read at a glance. Every dot is one of them, in the order it was written.`,
  },
  {
    part: 'retrieval',
    title: 'Every passage has a place too.',
    body: ({ dims }) => `The same model gave each passage its own ${dims} numbers. Passages that mean similar things settle near each other, and your question lands among them.`,
    note: ({ dims }) => `Drawn in 3 dimensions. The real map has ${dims}.`,
    hint: 'Point at a dot to read it. Drag to turn the map.',
  },
  {
    part: 'retrieval',
    title: 'The nearest are the most relevant.',
    body: ({ count, kept, rank }) => (rank?.applied
      ? `Your question is compared with all ${many(count)} passages. The ${many(rank.candidates)} closest in meaning are kept, then sorted by what you asked for: ${rank.understood.split(' · ').join(', ')}. ${cap(word(kept))} remain. This is retrieval.`
      : `Your question is compared with all ${many(count)} passages, and the ${word(kept)} closest in meaning are kept. Nothing was matched by keyword, only by meaning. This is retrieval.`),
    link: { label: 'What if there were millions?', to: 'hnsw' }, // the search film (src/hnsw/)
  },
  {
    part: 'augmented',
    title: 'Evidence, not memory.',
    body: ({ kept }) => `The ${passages(kept)} ${kept === 1 ? 'is' : 'are'} handed to the language model together with your question, and one rule: answer only from these. This is the augmentation.`,
  },
  {
    part: 'generation',
    // The ending depends on what the model did, so the title is a function too.
    title: ({ trace }) => (!trace.answer ? 'The evidence is ready.' : trace.check?.not_found ? 'An honest “I don’t know”.' : 'An answer you can check.'),
    body: ({ trace }) => {
      if (!trace.answer) return 'Answer writing is switched off on this server, so the story ends here: with the passages the model would have read.'
      if (trace.check?.not_found) return 'The passages don’t contain the answer, so the model says so instead of guessing. This is the generation.'
      return 'The model writes its answer, and every claim points to the passage it came from. This is the generation.'
    },
    note: ({ trace }) => {
      const c = trace.check
      if (!trace.answer || !c || c.not_found) return null
      if (!c.passed) return `A citation failed its check: ${c.problems.join('; ')}`
      const n = c.cited.length
      return `${n === 1 ? '1 citation' : `${n} citations`} checked against the evidence before you saw ${n === 1 ? 'it' : 'them'}.`
    },
    link: { label: 'The same trip, told by the question', to: 'journey' }, // the journey (src/journey/)
  },
]

export const PARTS = [
  { id: 'retrieval', label: 'Retrieval' },
  { id: 'augmented', label: 'Augmented' },
  { id: 'generation', label: 'Generation' },
]

// The figures the chapters above ask for, gathered from the trace.
export function context(trace, count) {
  return {
    trace,
    count,
    dims: trace?.retrieval?.query_vector?.length ?? 384,
    kept: trace?.sources?.length ?? 0,
    rank: trace?.rank,
  }
}

// A passage's name, from its breadcrumb ("Electric cars › SUV › Lucid Gravity GT › Range").
export function nameOf(breadcrumb = '') {
  const parts = breadcrumb.split(' › ')
  return parts.length >= 3
    ? { title: parts[parts.length - 2], tag: parts[parts.length - 1] }
    : { title: parts[parts.length - 1], tag: '' }
}
