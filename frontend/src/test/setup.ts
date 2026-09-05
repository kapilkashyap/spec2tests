/**
 * Global Vitest setup for the Spec2Tests frontend test suite.
 *
 * Imported automatically for every test file via `vitest.config.ts`'s
 * `test.setupFiles`. Registers `@testing-library/jest-dom`'s custom DOM
 * matchers (e.g. `toBeDisabled()`, `toBeInTheDocument()`, `toHaveTextContent()`)
 * on Vitest's `expect`.
 */
import "@testing-library/jest-dom/vitest";
