import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 51730,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/test/setup.ts',
    maxWorkers: 2,
  },
})
