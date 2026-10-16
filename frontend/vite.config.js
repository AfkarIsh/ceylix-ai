import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // Expose VITE_ prefixed env vars to the browser bundle
  envPrefix: 'VITE_',

  server: {
    port: 5173,
    host: true,
    // Proxy API calls to the FastAPI backend in dev (avoids CORS issues)
    proxy: {
      '/api': {
        target:       process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure:       false,
      },
      '/health': {
        target:       process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure:       false,
      },
    },
  },

  build: {
    outDir:    'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          react:  ['react', 'react-dom'],
          lucide: ['lucide-react'],
        },
      },
    },
  },
})
