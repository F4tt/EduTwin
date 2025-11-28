import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Optimize production build
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,      // Remove console.log in production
        drop_debugger: true,
      },
    },
    rollupOptions: {
      output: {
        // Manual chunks for better caching
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['axios'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,  // Increase warning limit
    sourcemap: false,             // Disable sourcemap for faster build
  },
  server: {
    // Dev server settings
    host: true,
    port: 5173,
  },
})
