import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

import { evaluationAssets } from "./vite-plugin-evaluation-assets"

const repoRoot = path.resolve(__dirname, "../..")

// https://vite.dev/config/
export default defineConfig({
  // Relative URLs, so the built folder works from any path on a static host.
  base: "./",
  plugins: [
    react(),
    tailwindcss(),
    evaluationAssets({
      // The one data file and the source PDFs live in evaluation/ and are
      // served from there. Nothing is copied into this app's source tree.
      dataFile: path.join(repoRoot, "evaluation/dashboard/dashboard_data.json"),
      documentsDir: path.join(repoRoot, "evaluation/datasets/cpt316/documents"),
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
