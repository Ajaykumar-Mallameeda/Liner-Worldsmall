import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend port: 8000 by default; set API_PORT where 8000 is reserved
// (Windows Hyper-V can reserve 7961-8060).
const API_TARGET = `http://127.0.0.1:${process.env.API_PORT || 8000}`

// DASHBOARD_RUN_FROM_API=1 (set by launch_dashboard.bat): the default view's /pipeline_output.json comes from the
// backend's current run (PIPELINE_OUTPUT) instead of the public/ copy. Off, the dashboard works without a backend.
const runFromApi = process.env.DASHBOARD_RUN_FROM_API === '1'
  ? { '/pipeline_output.json': { target: API_TARGET, changeOrigin: true, rewrite: () => '/api/runs/current/pipeline_output' } }
  : {}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // next free port when 5173 is taken (a second dev server, another app) instead of refusing to start
    strictPort: false,
    proxy: {
      ...runFromApi,
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
  // MapLibre's tile worker is a module worker (GlMap.jsx bundles it with ?worker&url).
  worker: { format: 'es' },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
