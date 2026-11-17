/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8010'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: true,
    proxy: { '/api': { target: backend, changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
