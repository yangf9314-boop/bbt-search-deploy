import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// 本地开发时，data/clips/ 里的 mp4 已经通过软链放到 frontend/public/clips/
// Vite 自动把 public/ 下的内容挂到根路径，所以播放器从 /clips/xxx.mp4 加载
// 部署上线后改用 VITE_R2_PUBLIC_BASE，见 ClipPlayer.tsx buildVideoSrc()
export default defineConfig({
  plugins: [react()],
})
