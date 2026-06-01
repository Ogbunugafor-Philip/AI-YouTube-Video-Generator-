import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development the API + media are served by FastAPI on :8000.
// In production Nginx serves the built frontend and proxies /api and /media.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
