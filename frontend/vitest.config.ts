/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.d.ts",
        "src/**/*.{test,spec}.{ts,tsx}",
        "src/**/__tests__/**",
        "src/main.tsx",
        "src/types/**",
        "src/styles/**",
      ],
      thresholds: {
        // Sprint 4 baseline: workflowStore (98%), chatStore (~80%),
        // apiClient interceptor, workflows api wrapper.
        // SPECIFICATION targets ≥60% on core; next ratchet (Sprint 5) adds
        // the remaining api/ wrappers, Layout, canvas renderers.
        statements: 5,
        branches: 60,
        functions: 50,
        lines: 5,
      },
    },
  },
});
