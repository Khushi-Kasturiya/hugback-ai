import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand colors sampled directly from public/logo.png and public/hugback.png.
        // Existing semantic utility names are remapped so every current surface
        // follows the Hugback palette without weakening status/error semantics.
        stone: {
          50: "#F8F9FF",
          100: "#F1F3FA",
          200: "#E2E6F2",
          300: "#CDD3E3",
          400: "#9BA4C0",
          500: "#737D9E",
          600: "#56617F",
          700: "#414A67",
          800: "#2D344E",
          900: "#1F253B",
          950: "#15192A",
        },
        emerald: {
          50: "#F4F1FF",
          100: "#E9E2FF",
          200: "#D8CBFF",
          300: "#C0ADF8",
          400: "#B69CF2",
          500: "#A18BE9",
          600: "#8172D3",
          700: "#6C68BC",
          800: "#56619C",
          900: "#404A7E",
          950: "#293052",
        },
        amber: {
          50: "#F2F8FF",
          100: "#E5F2FF",
          200: "#CDE8FF",
          300: "#A9D6FF",
          400: "#86C2FE",
          500: "#71B4FD",
          600: "#5599E6",
          700: "#447DC3",
          800: "#3B669B",
          900: "#35577E",
          950: "#233956",
        },
        teal: {
          300: "#B69CF2",
          400: "#9BA5FC",
          500: "#8D91E9",
        },
        blue: {
          700: "#56619C",
        },
        violet: {
          100: "#E9E2FF",
          600: "#8172D3",
          700: "#6C68BC",
          800: "#56619C",
        },
        hugback: {
          sky: "#72B5FE",
          periwinkle: "#9BA5FC",
          violet: "#B69CF2",
          indigo: "#56619C",
        },
      },
    },
  },
  plugins: [],
};
export default config;
