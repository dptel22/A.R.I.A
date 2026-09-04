import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '^/(api|health|ready|uploads|intake|segments)': {
        target: process.env.ARIA_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        headers: {
          'x-api-key': process.env.ARIA_API_KEY || 'test-api-key',
        },
      },
    },
  },
});
