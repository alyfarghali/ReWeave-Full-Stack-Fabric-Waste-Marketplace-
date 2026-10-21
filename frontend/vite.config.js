import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Point at another backend with API_PROXY_TARGET=http://host:port npm run dev
      '/api': process.env.API_PROXY_TARGET || 'http://localhost:8000',
    },
    allowedHosts: ['.ngrok-free.dev'],
  },
})
