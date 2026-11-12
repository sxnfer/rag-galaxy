// The Journey: the same trip as the main film, told by the question itself.
// "I am your question. Here is everything that happens to me."
//
// The main film is about the ideas. This one is about the machinery: every
// stop the question makes on its way through the system, what it looks like
// at that moment (journey/Look.jsx draws that from the real trace), and the
// code it is passing through.
//
// Every stop's words and code references live here, so they can be edited
// without touching the components. Same rules as src/story.js: one idea per
// stop, a title and one or two plain sentences.
//
// Code references name a file and a function, never a line. Line numbers are
// looked up from the function name each time the site is built (code-lines.js),
// and the build stops if a file or function named here no longer exists.
// Keep each one written as a ref(...) call.
//
// This file is also loaded by vite.config.js, so it must stay plain data:
// no JSX, no imports, no import.meta.

export const REPO = 'https://github.com/sxnfer/rag-galaxy'

const ref = (file, fn) => ({ file, fn })
const many = (n) => n.toLocaleString('en')

// Where the question is. The matching word lights up at the top of the screen.
export const PLACES = [
  { id: 'browser', label: 'Browser' },
  { id: 'server', label: 'Server' },
  { id: 'database', label: 'Database' },
  { id: 'model', label: 'Model' },
]

// id:     which picture Look.jsx draws for this stop
// part:   where the question is (PLACES)
// stage:  which entry of trace.stages timed this stop
// needs:  the stop only exists when the trace has this stage
// aside:  a step off the line: something that happened before the question arrived
export const STOPS = [
  {
    id: 'typed', part: 'browser',
    title: 'I am your question.',
    body: () => 'You typed me and pressed Enter. The page wrapped me in a small message and sent me to the server, the computer that does the work.',
    code: [ref('frontend/src/App.jsx', 'ask'), ref('frontend/src/api.js', 'askQuestion')],
  },
  {
    id: 'arrive', part: 'server',
    title: 'I arrive, and I am checked.',
    body: () => 'The server unwraps me and checks I am a sensible size: not empty, and no longer than 300 characters. I also say which library I want searched.',
    code: [ref('backend/app/main.py', 'ask'), ref('backend/app/main.py', 'AskRequest')],
  },
  {
    id: 'seen', part: 'server',
    title: 'Have I been asked before?',
    body: () => 'If I am one of the example questions, a saved answer is replayed. If someone asked me a moment ago, the answer comes from memory. Both are free. Otherwise I am new.',
    code: [ref('backend/app/baked.py', 'replay'), ref('backend/app/guard.py', 'AnswerCache.get')],
  },
  {
    id: 'allowed', part: 'server',
    title: 'Am I allowed through?',
    body: () => 'A new question costs a little money, so the server counts how many each visitor asks: a few a minute, a few dozen a day, and a limit for the whole site.',
    code: [ref('backend/app/guard.py', 'Guard.check')],
  },
  {
    id: 'numbers', part: 'server', stage: 'query',
    title: 'I become numbers.',
    body: ({ dims }) => `A small model reads me and writes down ${dims} numbers that stand for what I mean. From here on, I am those numbers.`,
    code: [ref('backend/app/embedder.py', 'Embedder.embed_query'), ref('backend/pipeline/answer/pipeline.py', 'answer')],
  },
  {
    id: 'compared', part: 'database', stage: 'retrieve',
    title: 'I am compared with every passage.',
    body: ({ found }) => `The database keeps every passage’s numbers. Mine are compared with each of them, and the ${many(found)} closest in meaning are kept.`,
    link: { label: 'What if there were millions?', to: 'hnsw' }, // the search film (src/hnsw/)
    code: [ref('backend/pipeline/chunk/search.py', 'search'), ref('backend/pipeline/chunk/search.py', 'sql_exact')],
  },
  {
    id: 'before', part: 'database', aside: true,
    title: 'Before me: how the passages were made.',
    body: ({ table }) => (table
      ? 'The passages were ready long before I arrived. Each row of the table of electric cars was written out as short cards of words, because a row of bare numbers means little to the model that reads them.'
      : 'The passages were ready long before I arrived. Each document was cut into short passages, and every passage was given numbers of its own.'),
    code: [
      ref('backend/pipeline/collect/table.py', 'parse_table'),
      ref('backend/pipeline/chunk/cards.py', 'car_cards'),
      ref('backend/pipeline/chunk/build.py', 'run_table'),
    ],
  },
  {
    id: 'rank', part: 'server', stage: 'rank', needs: 'rank',
    title: 'I am sorted by what I asked for.',
    body: ({ trace }) => (trace.rank?.applied
      ? 'Meaning found the right kind of car, but meaning can’t put things in order. So plain rules read what I asked for, and the candidates are sorted by that figure.'
      : 'I didn’t name a figure to sort by, so the order that search gave was kept.'),
    code: [ref('backend/pipeline/answer/rank.py', 'parse_intent'), ref('backend/pipeline/answer/rank.py', 'rank')],
  },
  {
    id: 'evidence', part: 'server', stage: 'assemble',
    title: 'My evidence is chosen and labelled.',
    body: () => 'The passages are trimmed to what the model should read: near-copies are dropped, a word limit is kept, and each one gets a label so it can be cited.',
    code: [ref('backend/pipeline/answer/assemble.py', 'assemble')],
  },
  {
    id: 'read', part: 'model', stage: 'generate',
    title: 'I am read by the language model.',
    body: () => 'The model reads the labelled passages, then me, under strict rules: use only these passages, cite one for every fact, and say so if the answer isn’t there.',
    code: [ref('backend/pipeline/answer/generate.py', 'generate')],
  },
  {
    id: 'checked', part: 'server', stage: 'check',
    title: 'My answer is checked.',
    body: () => 'Before anyone sees the answer, every citation in it is checked: each must point at a passage that was really sent.',
    code: [ref('backend/pipeline/answer/check.py', 'check')],
  },
  {
    id: 'home', part: 'browser', stage: 'log',
    title: 'I am saved, and sent home.',
    body: ({ dims }) => `Everything that happened to me is saved as one record, the trace. My ${dims} numbers are squeezed down to 3, so I can be drawn as a point of light, and I travel back to your browser.`,
    code: [ref('backend/pipeline/answer/pipeline.py', 'answer'), ref('backend/app/galaxy.py', 'Galaxy.project')],
  },
]

// Every reference in one flat list, for the build step that finds the line numbers.
export const allRefs = () => STOPS.flatMap((s) => s.code)
export const refKey = ({ file, fn }) => `${file}#${fn}`

// Where the trace being followed came from, said under the first stop.
const SOURCES = {
  yours: 'Following the question you asked in the film.',
  example: 'Following an example question. Ask your own in the film, and this follows it instead.',
  sample: 'An illustration: the cars are real, the scores and timings are made up.',
}

// The stops this trace went through, as chapters for the caption (ui/Caption.jsx).
// Each gets a small note: how long that stage took on the server.
export function chaptersFor(trace) {
  const stage = (id) => trace.stages.find((x) => x.id === id)
  const stops = STOPS.filter((s) => !s.needs || stage(s.needs))
  return [null, ...stops.map((s, i) => ({
    ...s,
    note: ({ source }) => {
      if (i === 0) return SOURCES[source]
      const timed = s.stage && stage(s.stage)
      if (!timed) return null
      const again = trace.replay || trace.cached ? ', the first time I was asked' : ''
      return `${many(timed.duration_ms)} ms on the server${again}`
    },
  }))]
}

// The figures the sentences above ask for, gathered from the trace.
export function context(trace, source) {
  return {
    trace, source,
    dims: trace.retrieval.query_vector.length,
    found: trace.rank?.candidates ?? trace.retrieval.hits.length,
    table: !!trace.retrieval.hits[0]?.meta,
  }
}
