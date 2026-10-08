/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        aurora: {
          50: '#f0f4ff', 
          100: '#e0e9ff', 
          200: '#c7d6fe', 
          300: '#a4b8fc', 
          400: '#818cf8', 
          500: '#6366f1', 
          600: '#4f46e5', 
          700: '#4338ca', 
          800: '#3730a3', 
          900: '#312e81', 
          950: '#1e1b4b',
        },
        background: "#F8F9FB",
        surface: "#FFFFFF",
        surfaceSoft: "#FFFCF5",
        colmena: {
          yellow: "#F5B21A",
          orange: "#FF6A2A",
          teal: "#11B7B2",
          graphite: "#1C1F24",
          bg: "#FAFAF8",
          border: "#E6E8EB",
        },
        amber: "#F5B21A",
        honey: "#FF6A2A",
        orange: "#FF6A2A",
        yellowSoft: "#FFF8E7",
        yellowMid: "#FDE7AB",
        yellowDark: "#D99712",
        turquoise: "#11B7B2",
        turquoiseSoft: "#E8FAF9",
        turquoiseMid: "#B8F0ED",
        turquoiseDark: "#0C9897",
        graphite: "#1C1F24",
        dark: "#111111",
        muted: "#6B7280",
        border: "#E6E8EB",
        success: "#059669",
        warning: "#D97706",
        danger: "#DC2626",
        info: "#2563EB",
      },
      boxShadow: {
        soft: "0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)",
        card: "0 1px 3px rgba(0,0,0,0.04), 0 6px 16px rgba(0,0,0,0.03)",
        glass: "0 4px 24px rgba(0,0,0,0.06), 0 16px 40px rgba(0,0,0,0.04)",
        glow: "0 0 24px rgba(245, 178, 26, 0.15)",
      },
      borderRadius: {
        "2xl": "14px",
        "3xl": "20px",
      },
      fontFamily: {
        sans: ["'Inter'", "system-ui", "-apple-system", "sans-serif"],
      },
      backgroundImage: {
        "hero-glow":
          "radial-gradient(ellipse at 10% 0%, rgba(245, 178, 26, 0.08) 0%, transparent 50%), radial-gradient(ellipse at 90% 0%, rgba(17, 183, 178, 0.06) 0%, transparent 50%)",
      },
      animation: {
        "fade-in": "colmena-fade-in 0.35s ease-out",
        'counter-up': 'counter-up 1s ease-out',
        'slide-up': 'slide-up 0.5s ease-out',
        'slide-down': 'slide-down 0.5s ease-out',
        'glow-pulse': 'glow-pulse 2s infinite',
      },
      keyframes: {
        'counter-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'slide-down': {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
};
