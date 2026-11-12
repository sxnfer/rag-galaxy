// The search film, chapter by chapter: how a library of millions is searched
// without comparing the question with every passage.
//
// Same rules as the main film (src/story.js): each chapter is one idea, a
// title and one or two plain sentences, and every word a visitor reads lives here.
//
// `part` says which word of "Hierarchical Navigable Small World" the chapter
// is about; that word lights up at the top of the screen.
// `live` asks for a running count under the caption, written by the scene as
// the picture moves: 'every', 'ground' or 'floors'.
// `secs` is how long the way INTO the chapter takes: a walk needs longer than a camera move.

const many = (n) => n.toLocaleString('en')

export const LAST = 7

export const CHAPTERS = [
  null,
  {
    part: null, secs: 4.4, live: 'every',
    title: 'Comparing with everything is slow.',
    body: ({ count }) => `In the film, your question was compared with every passage, one by one. For ${count ? many(count) : 'a thousand'} that takes a moment. For a hundred million, every question would wait.`,
  },
  {
    part: 'navigable', secs: 2.6,
    title: 'Give each passage a few neighbours.',
    body: () => 'So, ahead of time, every passage is linked to the few passages closest to it in meaning. Now there are paths to walk along.',
  },
  {
    part: 'navigable', secs: 7.4, live: 'ground',
    title: 'Walk towards the question.',
    body: () => 'Start anywhere. Look only at the neighbours of where you stand, and step to the one closest to the question. When no neighbour is closer, you have arrived.',
  },
  {
    part: 'hierarchical', secs: 3.4,
    title: 'Add floors with fewer passages.',
    body: () => 'Short steps make a long walk. So a random few passages are copied to a floor above, and a few of those to a floor above that. The fewer passages a floor has, the further its links reach.',
  },
  {
    part: 'small', secs: 3.6, live: 'floors',
    title: 'Start at the top, with long strides.',
    body: () => 'The search begins on the top floor, where one step crosses half the map. It walks the same way as before: to whichever neighbour is closest to the question.',
  },
  {
    part: 'hierarchical', secs: 5.2, live: 'floors',
    title: 'Then go down, for finer steps.',
    body: () => 'When a floor has nothing closer to offer, the search drops to the same passage one floor down, where the links are shorter. The ground floor, where every passage lives, finishes the job.',
  },
  {
    part: 'all', secs: 2.6,
    title: 'This is called HNSW.',
    body: ({ total, ground, floors }) => `Hierarchical: the floors. Navigable: links you can walk. Small world: a few steps reach anywhere. The same passage was found by comparing ${floors.seen} of ${total}, where the ground floor alone needed ${ground.seen}, and the saving grows with the library.`,
    note: () => 'It is approximate: now and then the walk stops just short of the true nearest.',
    hint: 'A teaching model: 150 passages on a flat map. Drag to turn it.',
  },
]

export const PARTS = [
  { id: 'hierarchical', label: 'Hierarchical' },
  { id: 'navigable', label: 'Navigable' },
  { id: 'small', label: 'Small world' },
]

// The running count under the caption. `kind` is the chapter's `live` word.
export function count(kind, { compared, steps, total }) {
  if (kind === 'every') return `${compared} of ${total} compared`
  return `${steps === 1 ? '1 step' : `${steps} steps`} · ${compared} of ${total} compared`
}
