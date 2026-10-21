import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En developpement, /api est relaye vers FastAPI (uvicorn sur le port 8010),
// comme le fait nginx en production.
export default defineConfig({
  plugins: [react()],
  // Application locale : un seul fichier JS d'environ 500 ko (graphiques compris) est acceptable.
  build: { chunkSizeWarningLimit: 800 },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8010',
        rewrite: chemin => chemin.replace(/^\/api/, ''),
      },
    },
  },
})
