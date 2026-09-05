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
declare const _default: import("vite").UserConfig;
export default _default;
