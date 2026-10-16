import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5177,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 5177,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8003',
        changeOrigin: true,
      },
    },
  },
});
