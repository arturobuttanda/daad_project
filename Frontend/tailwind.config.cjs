/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        body: ["IBM Plex Sans", "system-ui", "sans-serif"],
      },
      colors: {
        ink: "var(--color-ink)",
        sand: "var(--color-sand)",
        brass: "var(--color-brass)",
        copper: "var(--color-copper)",
        ocean: "var(--color-ocean)",
        mint: "var(--color-mint)",
        cloud: "var(--color-cloud)",
        shadow: "var(--color-shadow)",
      },
      boxShadow: {
        soft: "0 20px 45px -35px rgba(16, 24, 40, 0.5)",
        glow: "0 12px 35px -20px rgba(29, 78, 216, 0.45)",
      },
    },
  },
  plugins: [],
};
