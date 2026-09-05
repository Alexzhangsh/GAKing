// @ai-generated
import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true
      }
    }
  },
  build: {
    // 生产构建压缩配置
    minify: 'terser',
    terserOptions: {
      compress: {
        // 移除 console.log（保留 console.error/warn 用于错误排查）
        drop_console: true,
        drop_debugger: true,
        // 移除未使用的函数和变量
        unused: true
      },
      format: {
        // 移除注释
        comments: false
      }
    },
    // CSS 代码分割
    cssCodeSplit: true,
    // chunk 大小警告阈值（KB）
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // 压缩产物
        compact: true
      }
    }
  }
})
