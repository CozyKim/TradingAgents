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
          2: "#2d2d34",
        },
        text: {
          1: "#e8e8ea",
          2: "#a0a0a8",
          3: "#8a8a93",
        },
        accent: { DEFAULT: "#4f8cff", muted: "#1a2f4a" },
        signal: {
          buy: "#34d399",
          sell: "#f87171",
          hold: "#fbbf24",
        },
        surface: {
          DEFAULT: "#0a0a0b",
          raised: "#111114",
          overlay: "#18181c",
        },
        divider: {
          DEFAULT: "#1f1f24",
          strong: "#2d2d34",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px" }],
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
