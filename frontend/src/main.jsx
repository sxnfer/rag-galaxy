import { createRoot } from 'react-dom/client'
import Site from './Site.jsx'
import NoWebGL from './ui/NoWebGL.jsx'
import './styles.css'

// The films are drawn with WebGL, the browser feature for 3D graphics. If this
// browser can't provide it, say so plainly instead of showing an empty page.
function canDraw3D() {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

// StrictMode stays off: it mounts every component twice in development, which
// restarts the 3D scene and its animations on load.
createRoot(document.getElementById('root')).render(canDraw3D() ? <Site /> : <NoWebGL />)
