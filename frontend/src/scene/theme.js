// Two colours, both neutral: the dark, and the ink drawn on it.
// Nothing in the scene has a hue. What matters is shown by light alone:
// the brighter something is, the more it matters to your question.
export const DARK = '#0a0a0b'
export const INK = '#edebe6'

// Brighter than full white. The screen can't show it, but the glow effect
// (Stage.jsx) picks up anything over 1 and lets it bleed light, so only the
// question and the passages it found ever glow.
export const GLOW = 2.6
