import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          0: "#0a0a0b",
          1: "#111114",
          2: "#18181c",
        },
        border: {
          1: "#1f1f24",
          2: "#25252b",
        },
        text: {
          1: "#e8e8ea",
          2: "#a0a0a8",
          3: "#6b6b74",
        },
        accent: { DEFAULT: "#4f8cff", muted: "#1a2f4a" },
        signal: {
          buy: "#34d399",
          sell: "#f87171",
          hold: "#fbbf24",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
    },
  },
  plugins: [],
};
export default config;
