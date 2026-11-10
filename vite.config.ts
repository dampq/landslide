import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { codespacesHost } from "./scripts/codespaces.mjs";
const forwardedHost = codespacesHost();
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: forwardedHost ? [forwardedHost] : [],
    ...(forwardedHost
      ? { hmr: { protocol: "wss", host: forwardedHost, clientPort: 443 } }
      : {}),
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  preview: {
    allowedHosts: forwardedHost ? [forwardedHost] : [],
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes("node_modules/leaflet/") ||
            id.includes("node_modules/react-leaflet/")
          )
            return "maps";
          if (id.includes("node_modules/recharts/")) return "charts";
        },
      },
    },
  },
});
