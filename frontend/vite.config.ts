import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Day 0: 로컬에서는 proxy로 /api → 백엔드 (VITE_API_URL 비우면 상대 경로)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
