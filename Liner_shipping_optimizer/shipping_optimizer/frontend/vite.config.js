import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend port: 8000 by default; set API_PORT where 8000 is reserved
// (Windows Hyper-V can reserve 7961-8060).
const API_TARGET = `http://127.0.0.1:${process.env.API_PORT || 8000}`

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/data': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: API_TARGET.replace('http', 'ws'),
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
