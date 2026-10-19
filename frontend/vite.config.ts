import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server forwards API and WebSocket calls to the FastAPI backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
