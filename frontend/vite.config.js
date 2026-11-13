import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { codeLinesPlugin } from './code-lines.js'
import { savedExamplePlugin } from './saved-example.js'

export default defineConfig({
  // codeLinesPlugin: the Journey's links to the code get their line numbers when the site is built.
  // savedExamplePlugin: the Journey gets a saved example to follow, so it never waits for the server.
  plugins: [react(), codeLinesPlugin(), savedExamplePlugin()],
  server: {
    // Any call to /api/... is forwarded to the Python server.
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    // The 3D libraries are big but change rarely: ship them as their own file,
    // so a visitor's browser keeps them cached when the app's own code changes.
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks: { three: ['three', '@react-three/fiber', '@react-three/postprocessing', 'postprocessing'] },
      },
    },
  },
})
