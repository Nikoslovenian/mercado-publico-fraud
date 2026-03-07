/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        intel: {
          bg: '#080c14',
          surface: '#0d1520',
          card: '#101825',
          border: '#1a2535',
          borderHover: '#243045',
          text: '#c8d8e8',
          muted: '#5a7090',
          green: '#00e5a0',
          cyan: '#00c8e0',
          red: '#ff3355',
          amber: '#ffaa00',
          blue: '#4080ff',
          purple: '#9060ff',
        },
        severity: {
          alta: '#ff3355',
          media: '#ffaa00',
          baja: '#00c878',
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
      },
      keyframes: {
        pulse_glow: {
          '0%, 100%': { boxShadow: '0 0 4px rgba(255,51,85,0.4)' },
          '50%': { boxShadow: '0 0 14px rgba(255,51,85,0.9)' },
        },
        fadeIn: {
          from: { opacity: 0, transform: 'translateY(6px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
      },
      animation: {
        pulse_glow: 'pulse_glow 2s ease-in-out infinite',
        fadeIn: 'fadeIn 0.3s ease-out',
      },
    }
  },
  plugins: [],
}
