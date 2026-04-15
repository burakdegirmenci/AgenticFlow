// Flat ESLint config. Requires ESLint 9+.
// Rationale lives in docs/IMPLEMENTATION.md §3.
//
// Ratchet strategy:
//   Start: `recommendedTypeChecked` + `stylistic` + hand-picked sharp rules.
//   Next (Sprint 4, after CI stabilizes): promote to `strictTypeChecked`
//   and enable `noUncheckedIndexedAccess` in tsconfig.
import js from "@eslint/js";
import importPlugin from "eslint-plugin-import";
import reactPlugin from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import simpleImportSort from "eslint-plugin-simple-import-sort";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "**/*.d.ts",
      "postcss.config.js",
      "tailwind.config.js",
      "eslint.config.js",
      "vite.config.ts",
      "vitest.config.ts",
      "vitest.setup.ts",
    ],
  },

  // Base JS rules
  js.configs.recommended,

  // TypeScript rules (applied only to src/**).
  ...tseslint.configs.recommendedTypeChecked.map((cfg) => ({
    ...cfg,
    files: ["src/**/*.{ts,tsx}"],
  })),
  ...tseslint.configs.stylistic.map((cfg) => ({
    ...cfg,
    files: ["src/**/*.{ts,tsx}"],
  })),

  // React + hooks + project conventions
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
      import: importPlugin,
      "simple-import-sort": simpleImportSort,
    },
    languageOptions: {
      parserOptions: {
        project: "./tsconfig.json",
        tsconfigRootDir: import.meta.dirname,
        ecmaVersion: "latest",
        sourceType: "module",
      },
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
    },
    settings: {
      react: { version: "18" },
      "import/resolver": {
        typescript: { project: "./tsconfig.json" },
      },
    },
    rules: {
      // --- React hooks safety ------------------------------------------------
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // --- React (new JSX transform, no need for 'React in scope') ---------
      "react/react-in-jsx-scope": "off",
      "react/jsx-uses-react": "off",
      "react/prop-types": "off", // TypeScript replaces this

      // --- TypeScript — sharp edges ----------------------------------------
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          ignoreRestSiblings: true,
        },
      ],

      // --- Rules to ratchet in Sprint 4 (currently noisy with existing code)
      "@typescript-eslint/no-unsafe-assignment": "warn",
      "@typescript-eslint/no-unsafe-member-access": "warn",
      "@typescript-eslint/no-unsafe-call": "warn",
      "@typescript-eslint/no-unsafe-argument": "warn",
      "@typescript-eslint/no-unsafe-return": "warn",
      "@typescript-eslint/no-misused-promises": "warn",
      "@typescript-eslint/no-floating-promises": "warn",
      "@typescript-eslint/require-await": "warn",

      // --- Import hygiene --------------------------------------------------
      "simple-import-sort/imports": "error",
      "simple-import-sort/exports": "error",
      "import/no-duplicates": "error",
      "import/no-default-export": "off",
    },
  },

  // Test files: drop the "unsafe *" noise — tests routinely poke at unknown shapes.
  {
    files: [
      "src/**/*.test.{ts,tsx}",
      "src/**/*.spec.{ts,tsx}",
      "src/**/__tests__/**/*.{ts,tsx}",
      "vitest.setup.ts",
    ],
    rules: {
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/unbound-method": "off",
    },
  },
);
