// Talking to the Python server.
//
// In development Vite forwards /api/... to localhost:8000 (vite.config.js).
// In production the frontend and API live on different addresses, so the
// build reads the API's address from VITE_API_URL (e.g. https://api.example.com).
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, { status, retryAfter } = {}) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function request(path, options) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch {
    throw new ApiError('Could not reach the server. Please try again in a moment.')
  }
  let body = null
  try { body = await res.json() } catch { /* not JSON */ }
  if (!res.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : null
    if (res.status === 429) {
      throw new ApiError(detail ?? 'Too many questions at once. Please wait a moment.', {
        status: 429, retryAfter: body?.retry_after ?? Number(res.headers.get('Retry-After')),
      })
    }
    if (res.status === 422) throw new ApiError('That question is too long. Keep it under 300 characters.', { status: 422 })
    throw new ApiError(detail ?? `The server had a problem (${res.status}). Please try again.`, { status: res.status })
  }
  return body
}

const q = (library) => `?library=${encodeURIComponent(library)}`
export const getLibraries = () => request('/api/libraries')
export const getStars = (library) => request(`/api/stars${q(library)}`)
export const getExamples = (library) => request(`/api/examples${q(library)}`)
export const askQuestion = (question, library) =>
  request('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, library }),
  })
