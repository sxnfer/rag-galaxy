// Finds the line where a function is defined, so the Journey can link to it.
//
// The Journey names code by file and function (src/journey/stops.js). Line
// numbers written by hand go stale the first time someone adds a line above
// them, so they are looked up here, from the function name, each time the site
// is built. A file or function that no longer exists stops the build.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { allRefs, refKey } from './src/journey/stops.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..') // the rag-galaxy folder

// How a definition of `name` looks in each language.
function definition(name, file) {
  return file.endsWith('.py')
    ? new RegExp(`^\\s*(?:async\\s+)?(?:def|class)\\s+${name}\\b`)
    : new RegExp(`\\b(?:function\\s+${name}\\b|(?:const|let|class)\\s+${name}\\b)`)
}

// The 1-based line where `name` is defined. "Guard.check" means: find Guard, then the first check after it.
export function findLine(source, name, file) {
  const lines = source.split(/\r?\n/)
  let from = 0
  for (const part of name.split('.')) {
    const pattern = definition(part, file)
    const at = lines.findIndex((line, i) => i >= from && pattern.test(line))
    if (at < 0) return null
    from = at + 1
  }
  return from
}

export function codeLines() {
  const lines = {}
  for (const r of allRefs()) {
    const file = path.join(ROOT, r.file)
    if (!fs.existsSync(file)) throw new Error(`journey/stops.js names ${r.file}, which does not exist`)
    const line = findLine(fs.readFileSync(file, 'utf8'), r.fn, r.file)
    if (!line) throw new Error(`journey/stops.js names ${r.fn} in ${r.file}, but it is not defined there`)
    lines[refKey(r)] = line
  }
  return lines
}

// A Vite plugin: `import lines from 'virtual:code-lines'` gives { "path#function": line }.
export function codeLinesPlugin() {
  const id = 'virtual:code-lines'
  return {
    name: 'code-lines',
    resolveId: (source) => (source === id ? `\0${id}` : null),
    load: (loaded) => (loaded === `\0${id}` ? `export default ${JSON.stringify(codeLines())}` : null),
  }
}
