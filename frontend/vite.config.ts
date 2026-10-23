/// <reference types="vitest/config" />
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // During development the React app runs on :5173 and Flask on :5000. The proxy forwards
    // every /api request to Flask, so the browser sees ONE address: cookies just work, no CORS.
    proxy: {
      "/api": "http://127.0.0.1:5000",
    },
  },
  build: {
    outDir: "dist", // Flask serves this folder in production (see backend/app/routes/frontend.py)
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
})
