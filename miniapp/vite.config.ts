import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(), // Tailwind v4 через Vite plugin
  ],
  server: {
    host: true,
    port: 5173,
  },
})
