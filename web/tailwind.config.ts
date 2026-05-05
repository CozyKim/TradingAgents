import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Page surfaces — Toss uses a soft gray page bg with white cards on top.
        bg: {
          0: "#F2F4F6", // page background (soft gray)
          1: "#FFFFFF", // card / elevated surface
          2: "#F9FAFB", // hover / soft surface
        },
        border: {
          1: "#EAECEF",
          2: "#D1D6DB",
        },
        text: {
          1: "#191F28", // strong
          2: "#4E5968", // medium
          3: "#8B95A1", // weak / caption
        },
        accent: {
          DEFAULT: "#3182F6", // Toss blue
          muted: "#E8F2FE", // blue tinted background
        },
        // KR-style market colors: BUY/up = red, SELL/down = blue.
        signal: {
          buy: "#F04452",
          sell: "#1B64DA",
          hold: "#C0C8CF",
        },
        surface: {
          DEFAULT: "#F2F4F6",
          raised: "#FFFFFF",
          overlay: "#FFFFFF",
        },
        divider: {
          DEFAULT: "#EAECEF",
          strong: "#D1D6DB",
        },
      },
      fontFamily: {
        sans: [
          "Pretendard Variable",
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "Helvetica Neue",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Noto Sans KR",
          "sans-serif",
        ],
        mono: [
          "Pretendard Variable",
          "Pretendard",
          "SF Mono",
          "JetBrains Mono",
          "Consolas",
          "monospace",
        ],
      },
      fontSize: {
        "2xs": ["11px", { lineHeight: "16px" }],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        "2xl": "24px",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(17, 24, 28, 0.04), 0 4px 12px -2px rgba(17, 24, 28, 0.05)",
        pop: "0 8px 24px -4px rgba(17, 24, 28, 0.12), 0 2px 6px 0 rgba(17, 24, 28, 0.06)",
        nav: "0 -2px 12px -2px rgba(17, 24, 28, 0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
