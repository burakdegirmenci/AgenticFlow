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
        // Start at baseline (current: workflowStore + apiClient only ~2% of src).
        // SPECIFICATION targets ≥60% on core; ratcheted up each sprint as
        // component / page / api coverage lands (see docs/TASKS.md Sprint 4).
        statements: 2,
        branches: 45,
        functions: 20,
        lines: 2,
      },
    },
  },
});
