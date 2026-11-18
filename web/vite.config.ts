import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 백엔드 CORS·로그인 복귀 주소가 8081 기준이라 개발 서버도 8081에 띄움 (backend/app/main.py)
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  server: { port: 8081, strictPort: true },
  preview: { port: 8081, strictPort: true },
});
