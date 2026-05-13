/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Syne'", "sans-serif"],
        body: ["'DM Sans'", "sans-serif"],
        mono: ["'DM Mono'", "monospace"],
      },
      colors: {
        ink: {
          DEFAULT: "#0D0D0F",
          soft: "#1A1A1F",
          muted: "#2A2A33",
        },
        surface: {
          DEFAULT: "#F5F3EE",
          warm: "#EDE9E0",
          card: "#FAFAF8",
        },
        accent: {
          DEFAULT: "#E8612A",
          hover: "#D4541F",
          soft: "#FBE9E0",
        },
        sage: {
          DEFAULT: "#4A7C59",
          light: "#E8F2EC",
        },
        amber: {
          qs: "#C8851C",
          light: "#FBF3E0",
        },
      },
      animation: {
        "fade-up": "fadeUp 0.4s ease forwards",
        "fade-in": "fadeIn 0.3s ease forwards",
        "slide-in": "slideIn 0.35s cubic-bezier(0.16,1,0.3,1) forwards",
        pulse2: "pulse2 1.4s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: 0, transform: "translateY(12px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: 0 },
          "100%": { opacity: 1 },
        },
        slideIn: {
          "0%": { opacity: 0, transform: "translateX(-16px)" },
          "100%": { opacity: 1, transform: "translateX(0)" },
        },
        pulse2: {
          "0%, 100%": { opacity: 0.4 },
          "50%": { opacity: 1 },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 24px rgba(0,0,0,0.10)",
        accent: "0 0 0 3px rgba(232,97,42,0.25)",
      },
    },
  },
  plugins: [],
};
