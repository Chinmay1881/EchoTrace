import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite on :5173 proxies the API and WebSocket to the EchoTrace backend on :8000.
// 127.0.0.1, not localhost: Node may resolve localhost to ::1 while uvicorn listens on IPv4.
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": BACKEND,
      "/ws": { target: BACKEND.replace("http", "ws"), ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
