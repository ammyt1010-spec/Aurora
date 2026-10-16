import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const port = parseInt(env.VITE_PORT || process.env.VITE_PORT || '5174', 10);
  const backendTarget = env.VITE_BACKEND_URL || process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8001';

  // Explicit whitelist of allowed hostnames; never allow wildcards or unverified true
  const rawAllowedHosts = env.VITE_ALLOWED_HOSTS || process.env.VITE_ALLOWED_HOSTS || '';
  const configuredHosts = rawAllowedHosts
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean);
  const allowedHosts = Array.from(new Set(['localhost', '127.0.0.1', ...configuredHosts]));

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      allowedHosts,
      proxy: {
        '/api/v1': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      allowedHosts,
      proxy: {
        '/api/v1': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
