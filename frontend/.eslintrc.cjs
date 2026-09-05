/**
 * ESLint configuration for the Spec2Tests React + TypeScript frontend.
 *
 * Uses the classic ("eslintrc") config format since the project depends on
 * ESLint 8.x (see `frontend/package.json`). Run via `npm run lint`.
 */
module.exports = {
  root: true,
  env: {
    browser: true,
    es2020: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: {
      jsx: true,
    },
    project: ["./tsconfig.json", "./tsconfig.node.json"],
    tsconfigRootDir: __dirname,
  },
  plugins: ["@typescript-eslint", "react-hooks", "react-refresh"],
  ignorePatterns: [
    "dist",
    "node_modules",
    ".eslintrc.cjs",
    "*.d.ts",
  ],
  settings: {
    react: {
      version: "18.3",
    },
  },
  rules: {
    // React 17+ / automatic JSX runtime — no need to import React in scope.
    "react-refresh/only-export-components": [
      "warn",
      { allowConstantExport: true },
    ],
    "@typescript-eslint/no-unused-vars": [
      "warn",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/consistent-type-imports": [
      "warn",
      { prefer: "type-imports", fixStyle: "inline-type-imports" },
    ],
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
  overrides: [
    {
      // Vite's own config file runs under Node, not the browser/tsconfig
      // project used for the app source — lint it with looser type-aware
      // rules disabled to avoid requiring it in the `tsconfig.json` project.
      files: ["vite.config.ts", "vitest.config.ts"],
      parserOptions: {
        project: ["./tsconfig.node.json"],
      },
    },
  ],
};
