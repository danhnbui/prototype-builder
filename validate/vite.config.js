import { defineConfig } from 'vite'

// Minimal scaffold produced by /pb:validate — builds the rendered prototype.html as a static app.
export default defineConfig({
  build: { outDir: 'dist', emptyOutDir: true },
})
