import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      // The API. Proxied so the session cookie is same-origin in development.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      // So <a href="/auth/google"> works from the SPA. Google still redirects
      // back to http://localhost:8000/auth/google/callback directly, which then
      // bounces here — that is what FRONTEND_URL is for.
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      // Convenience only. Links inside real emails always point at :8000.
      '/u': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
