// Gives the Journey a real question to follow without waiting for the server.
//
// The server sleeps when nobody is visiting and takes a while to wake. The
// Journey used to ask it for an example before drawing anything, so a visitor
// arriving first saw an empty page. Now the first saved example (the same
// record the server replays, backend/app/baked/ev.json) is copied into the
// site when it is built, and the Journey starts with it at once.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const FILE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'backend/app/baked/ev.json')
const SHOWN = 5 // how many of search's candidates the Journey lists

export function savedExample() {
  if (!fs.existsSync(FILE)) throw new Error(`the Journey needs a saved example, but ${FILE} does not exist`)
  const trace = JSON.parse(fs.readFileSync(FILE, 'utf8')).traces?.[0]
  if (!trace) throw new Error(`the Journey needs a saved example, but ${FILE} holds none`)
  // Search's full list of candidates is long, and only the first few are shown.
  const rank = trace.rank?.before ? { ...trace.rank, before: trace.rank.before.slice(0, SHOWN) } : trace.rank
  return { ...trace, rank, replay: true }
}

// A Vite plugin: `import saved from 'virtual:saved-example'` gives that trace.
export function savedExamplePlugin() {
  const id = 'virtual:saved-example'
  return {
    name: 'saved-example',
    resolveId: (source) => (source === id ? `\0${id}` : null),
    load: (loaded) => (loaded === `\0${id}` ? `export default ${JSON.stringify(savedExample())}` : null),
  }
}
