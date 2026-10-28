/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The match files, commentary, traces, recaps and commentary audio all come from FastAPI (`uvicorn app.main:app`,
// port 8000; specs/agents-backend.md). The crowd clips are static files in web/public/audio/crowd/, so the audio
// proxy key leaves /audio/crowd/ alone (a plain "/audio" key would 404 the crowd).
const api = { target: process.env.API_URL ?? "http://127.0.0.1:8000", changeOrigin: true };
const proxy = {
  "/matches": api,
  "/data": api,
  "/commentary": api,
  "/agents": api,
  "/recap": api,
  "^/audio/(?!crowd/)": api,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
  preview: { proxy },
  test: { include: ["src/**/*.test.ts"] },
});
