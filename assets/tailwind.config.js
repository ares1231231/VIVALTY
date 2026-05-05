/**
 * Tailwind config for the Django-rendered website.
 *
 * Content scanning:
 *   - All Django HTML templates (every app's templates/ dir)
 *   - Python template-tag files (so dynamic class strings returned by filters
 *     such as `score_color` / `risk_color` / `trend_color` are seen by Tailwind)
 *
 * Output is minified to ../static/css/tailwind.css and served by WhiteNoise.
 */
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "../apps/**/templates/**/*.html",
    "../apps/**/templatetags/*.py",
    "../apps/**/forms.py",
    "../apps/**/views.py",
    "../assets/node_modules/flowbite/**/*.js",
  ],
  // Belt-and-braces: catch dynamic class strings used in templates like
  // `bg-{{ tag.color }}-50` for investment tags.
  safelist: [
    {
      pattern: /^(bg|text|border)-(emerald|amber|sky|rose|indigo|lime|cyan|brand|ink|slate|orange)-(50|100|200|300|400|500|600|700|900)$/,
    },
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#ecfdf5",
          100: "#d1fae5",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          900: "#064e3b",
        },
        ink: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          900: "#0f172a",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,.06), 0 4px 16px rgba(15,23,42,.04)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [require("flowbite/plugin")],
};
