/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep modern palette (glassmorphism/dark theme)
        brand: {
          50: '#f0f5ff',
          100: '#e0eaff',
          200: '#c7d7ff',
          300: '#a3bcff',
          400: '#7a97ff',
          500: '#536dfe', // Indigo-blue accent
          600: '#3d4ff7',
          700: '#2d3ce0',
          800: '#252fb6',
          900: '#222c90',
        },
        slate: {
          950: '#0b0f19', // Sleeker black-blue
        }
      },
      fontFamily: {
        sans: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 15px rgba(83, 109, 254, 0.15)',
        'glow-lg': '0 0 25px rgba(83, 109, 254, 0.25)',
      }
    },
  },
  plugins: [],
}
