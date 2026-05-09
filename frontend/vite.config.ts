import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// 로컬에서는 proxy로 /api → 백엔드 (VITE_API_URL 비우면 상대 경로)
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      strategies: "injectManifest",
      srcDir: "src/pwa",
      filename: "sw.ts",
      injectManifest: {
        // 기본 SW minify를 끄면 빌드가 안정적
        globPatterns: ["**/*.{js,css,html,svg,webmanifest}"],
      },
      includeAssets: [
        "icons/icon.svg",
        "icons/maskable.svg",
        "apple-touch-icon.svg",
      ],
      manifest: {
        name: "Living World Engine",
        short_name: "Living World",
        description: "UGC 기반 NPC 롤플레이 — 월드를 만들고, 캐릭터로 입장한다.",
        lang: "ko",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#0f172a",
        theme_color: "#0f172a",
        orientation: "portrait",
        icons: [
          {
            src: "/icons/icon.svg",
            sizes: "192x192 512x512",
            type: "image/svg+xml",
            purpose: "any",
          },
          {
            src: "/icons/maskable.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "maskable",
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
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
