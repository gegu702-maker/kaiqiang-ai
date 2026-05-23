import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#070A12",
        panel: "#0C111F",
        line: "#1E293B",
        cyan: "#31D7FF",
        lime: "#B7F871",
      },
      boxShadow: {
        glow: "0 0 42px rgba(49, 215, 255, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
