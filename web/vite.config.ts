import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// 开发时把 /api、/health 代理到 FastAPI，避免跨域；生产可用 VITE_API_BASE_URL 指定后端。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
        '/ready': { target, changeOrigin: true },
      },
    },
  }
})
