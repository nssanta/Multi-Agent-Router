import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// В Docker используем имя сервиса 'backend', локально - 'localhost'
// Для локальной разработки без Docker закомментируйте эту строку:
const API_TARGET = 'http://backend:8000'
// const API_TARGET = 'http://localhost:8000'  // Для локальной разработки

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
