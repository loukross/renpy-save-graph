import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

export default defineConfig({
  plugins: [vue()],
  root: './frontend',
  build: {
    outDir: resolve(__dirname, 'renpy_save_graph/static'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'frontend/index.html'),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/assets': 'http://localhost:5000',
    },
  },
});
