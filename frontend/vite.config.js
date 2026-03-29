import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react-dom')) return 'vendor-react';
          if (id.includes('node_modules/react-router')) return 'vendor-react';
          if (id.includes('node_modules/recharts')) return 'vendor-charts';
          if (id.includes('node_modules/lightweight-charts')) return 'vendor-charts';
          if (id.includes('node_modules/lucide-react')) return 'vendor-icons';
        },
      },
    },
    reportCompressedSize: true,
  },
})
