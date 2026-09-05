import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Vitest configuration for the Spec2Tests frontend.
 *
 * Uses a jsdom DOM environment (required for React Testing Library),
 * enables Vitest's global `describe`/`it`/`expect` APIs, and loads
 * `@testing-library/jest-dom` matchers via the shared setup file before
 * every test file runs. Shares the same `@` -> `src` path alias as
 * `vite.config.ts` so test files can use identical import paths to the
 * application source.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
