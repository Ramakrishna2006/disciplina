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
    rolldownOptions: {
      output: {
        // Libraries in their own files: they rarely change, so browsers keep them cached between
        // releases, and no single file grows past 500 kB.
        codeSplitting: {
          groups: [
            { name: "react", test: /node_modules[\\/](react|react-dom|scheduler|react-router)[\\/]/, priority: 3 },
            { name: "ui", test: /node_modules[\\/](radix-ui|@radix-ui|lucide-react|sonner|@floating-ui)[\\/]/, priority: 2 },
            { name: "forms", test: /node_modules[\\/](zod|react-hook-form|@hookform)[\\/]/, priority: 1 },
          ],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
})
