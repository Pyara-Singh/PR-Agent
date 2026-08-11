import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#121412",
        paper: "#f2efe5",
        acid: "#c7ff4a",
        coral: "#ff725e",
      },
      boxShadow: {
        panel: "0 20px 70px rgba(18, 20, 18, 0.09)",
      },
    },
  },
  plugins: [],
};

export default config;

