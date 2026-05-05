/**
 * vivalty.js — Global interactivity helpers.
 *
 * 1. Scroll-reveal: adds .revealed class to .reveal elements as they enter viewport.
 * 2. HTMX afterSettle: re-runs scroll-reveal on dynamically swapped content.
 * 3. Active nav highlighting on HTMX navigation.
 */

// ── Scroll reveal ─────────────────────────────────────────────────────────────
function initReveal(root = document) {
  const els = root.querySelectorAll(".reveal:not(.revealed)");
  if (!els.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add("revealed");
          observer.unobserve(e.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );

  els.forEach(el => observer.observe(el));
}

// Run on initial load
document.addEventListener("DOMContentLoaded", () => initReveal());

// Re-run after every HTMX content swap
document.addEventListener("htmx:afterSettle", (e) => {
  initReveal(e.detail.elt || document);
});

// ── Stagger grids ─────────────────────────────────────────────────────────────
// Auto-add stagger-children to saas-grid containers that hold cards
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".saas-grid").forEach(grid => {
    grid.classList.add("stagger-children");
  });
});

// ── HTMX page transition hook ─────────────────────────────────────────────────
document.addEventListener("htmx:beforeSwap", () => {
  document.querySelector("main")?.classList.add("opacity-50", "transition-opacity", "duration-150");
});
document.addEventListener("htmx:afterSettle", () => {
  document.querySelector("main")?.classList.remove("opacity-50");
});
