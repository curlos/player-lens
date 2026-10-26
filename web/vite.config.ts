/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { matchDataPlugin } from "./scripts/match-data-plugin";

// The match files stay in the repo-root data/ folder; the plugin serves them in dev and preview,
// the same URLs FastAPI serves in production (specs/agents-backend.md, "Backend endpoints").
export default defineConfig({
  plugins: [react(), tailwindcss(), matchDataPlugin()],
  server: { port: 5173 },
  test: { include: ["src/**/*.test.ts"] },
});
