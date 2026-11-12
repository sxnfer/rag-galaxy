import { createRoot } from 'react-dom/client'
import Site from './Site.jsx'
import './styles.css'

// StrictMode stays off: it mounts every component twice in development, which
// restarts the 3D scene and its animations on load.
createRoot(document.getElementById('root')).render(<Site />)
