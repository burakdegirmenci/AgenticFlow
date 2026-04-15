/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "#2563EB",
        "accent-hover": "#1d4ed8",
        ink: "#0a0a0a",
        paper: "#ffffff",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["Geist Mono", "JetBrains Mono", "monospace"],
      },
      borderRadius: {
        none: "0",
        sm: "2px",
      },
    },
  },
  plugins: [],
};
