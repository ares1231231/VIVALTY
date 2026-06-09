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

// ── Motion preference ─────────────────────────────────────────────────────────
const prefersReducedMotion =
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ── Count-up numbers ([data-count-to]) ────────────────────────────────────────
function formatNumber(n) {
  // Group thousands with thin spaces to match the site's money styling.
  return Math.round(n).toLocaleString("en-US").replace(/,/g, " ");
}

function animateCount(el) {
  const target = parseFloat(el.getAttribute("data-count-to"));
  if (!isFinite(target)) return;
  if (prefersReducedMotion) {
    el.textContent = formatNumber(target);
    return;
  }
  const duration = 1400;
  const start = performance.now();
  function tick(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
    el.textContent = formatNumber(target * eased);
    if (t < 1) requestAnimationFrame(tick);
    else el.textContent = formatNumber(target);
  }
  requestAnimationFrame(tick);
}

function initCounters() {
  const els = document.querySelectorAll("[data-count-to]:not([data-counted])");
  if (!els.length) return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.setAttribute("data-counted", "1");
          animateCount(e.target);
          observer.unobserve(e.target);
        }
      });
    },
    { threshold: 0.6 }
  );
  els.forEach((el) => observer.observe(el));
}

// ── Rotating headline word ([data-rotate-words]) ──────────────────────────────
function initRotatingWords() {
  document.querySelectorAll("[data-rotate-words]").forEach((el) => {
    let words;
    try {
      words = JSON.parse(el.getAttribute("data-rotate-words"));
    } catch (err) {
      return;
    }
    if (!Array.isArray(words) || words.length < 2 || prefersReducedMotion) return;

    el.style.transition = "opacity 0.4s ease, transform 0.4s ease";
    el.style.display = "inline-block";
    let i = 0;
    setInterval(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-6px)";
      setTimeout(() => {
        i = (i + 1) % words.length;
        el.textContent = words[i];
        el.style.opacity = "1";
        el.style.transform = "translateY(0)";
      }, 400);
    }, 2600);
  });
}

// ── Sticky compact search bar ─────────────────────────────────────────────────
function initStickySearch() {
  const bar = document.getElementById("sticky-search");
  if (!bar) return;
  function toggle() {
    const show = window.scrollY > 560;
    bar.classList.toggle("-translate-y-full", !show);
    bar.classList.toggle("opacity-0", !show);
  }
  window.addEventListener("scroll", toggle, { passive: true });
  toggle();
}

// ── Lite simulator slider value labels ────────────────────────────────────────
function formatQuickSim(format, value) {
  const n = parseFloat(value);
  if (format === "money") return "€" + formatNumber(n);
  if (format === "pct") return Math.round(n) + "%";
  if (format === "pct1") return n.toFixed(1) + "%";
  return value;
}

function initQuickSim() {
  const form = document.getElementById("quick-sim-form");
  if (!form) return;
  form.querySelectorAll("[data-qs-format]").forEach((input) => {
    const out = form.querySelector('[data-qs-out="' + input.name + '"]');
    if (!out) return;
    const sync = () => {
      out.textContent = formatQuickSim(input.getAttribute("data-qs-format"), input.value);
    };
    input.addEventListener("input", sync);
    sync();
  });
}

// ── Hero Buy / Rent purpose tabs + price mode ─────────────────────────────────
const FILTER_PRICE_OPTIONS = {
  buy: [
    { value: "", label: "Any price" },
    { value: "250000", label: "Less than €250k" },
    { value: "500000", label: "Less than €500k" },
    { value: "1000000", label: "Less than €1M" },
    { value: "2500000", label: "Less than €2.5M" },
    { value: "5000000", label: "Less than €5M" },
    { value: "10000000", label: "Less than €10M" },
  ],
  rent: [
    { value: "", label: "Any rent" },
    { value: "800", label: "Under €800 / month" },
    { value: "1200", label: "Under €1,200 / month" },
    { value: "1600", label: "Under €1,600 / month" },
    { value: "2000", label: "Under €2,000 / month" },
    { value: "2500", label: "Under €2,500 / month" },
    { value: "3000", label: "Under €3,000 / month" },
    { value: "4000", label: "Under €4,000 / month" },
    { value: "5000", label: "Under €5,000 / month" },
    { value: "7000", label: "Under €7,000 / month" },
    { value: "10000", label: "Under €10,000 / month" },
  ],
};

function initFilterPurpose() {
  const stack = document.querySelector(".vv-filter-stack");
  if (!stack) return;

  const tabs = [...stack.querySelectorAll("[data-purpose-tab]")];
  const purposeInput = stack.querySelector("[data-purpose-input]");
  const priceField = stack.querySelector("[data-price-filter]");
  if (!tabs.length || !purposeInput || !priceField) return;

  const priceLabel = priceField.querySelector("[data-price-label]");
  const priceInput = priceField.querySelector("[data-price-input]");
  const priceValue = priceField.querySelector("[data-price-value]");
  const priceMenu = priceField.querySelector("[data-price-menu]");

  function buildPriceMenu(purpose) {
    if (!priceMenu) return;
    const options = FILTER_PRICE_OPTIONS[purpose] || FILTER_PRICE_OPTIONS.buy;
    priceMenu.innerHTML = "";
    options.forEach((opt, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "vv-filter-option" + (i === 0 ? " is-selected" : "");
      btn.dataset.value = opt.value;
      btn.dataset.label = opt.label;
      btn.textContent = opt.label;
      priceMenu.appendChild(btn);
    });
  }

  function resetPrice(purpose) {
    const options = FILTER_PRICE_OPTIONS[purpose] || FILTER_PRICE_OPTIONS.buy;
    const first = options[0];
    if (priceInput) priceInput.value = first.value;
    if (priceValue) priceValue.textContent = first.label;
    if (priceLabel) {
      priceLabel.textContent = purpose === "rent" ? "Monthly rent" : "Price range";
    }
    if (priceInput) {
      priceInput.name = purpose === "rent" ? "max_rent" : "max_budget";
    }
    buildPriceMenu(purpose);
    priceField.classList.remove("is-open");
    const trigger = priceField.querySelector("[data-filter-trigger]");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }

  function activate(purpose) {
    const prev = purposeInput.value;
    tabs.forEach((tab) => {
      const on = tab.getAttribute("data-purpose-tab") === purpose;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
    });
    purposeInput.value = purpose;
    if (prev !== purpose) resetPrice(purpose);
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activate(tab.getAttribute("data-purpose-tab")));
  });

  resetPrice("buy");
}

function initHeroVideo() {
  const video = document.getElementById("hero-bg-video");
  if (!video || prefersReducedMotion) return;
  const play = () => video.play().catch(() => {});
  if (video.readyState >= 2) play();
  else video.addEventListener("loadeddata", play, { once: true });
}

// ── Hero country coverflow (3D fan) ───────────────────────────────────────────
function initHeroCountryCoverflow() {
  const root = document.querySelector("[data-coverflow]");
  if (!root) return;

  const items = [...root.querySelectorAll("[data-coverflow-item]")];
  const prevBtn = root.querySelector("[data-coverflow-prev]");
  const nextBtn = root.querySelector("[data-coverflow-next]");
  if (!items.length) return;

  const maxOffset = () => (window.innerWidth < 480 ? 1 : 3);
  const aeIdx = items.findIndex((el) => el.querySelector('[data-code="AE"]'));
  let active = aeIdx >= 0 ? aeIdx : Math.floor(items.length / 2);
  let timer = null;

  function update() {
    const limit = maxOffset();
    items.forEach((item, i) => {
      const offset = i - active;
      item.classList.remove("is-peek");
      if (Math.abs(offset) > limit) {
        item.setAttribute("data-offset", "hidden");
      } else {
        item.setAttribute("data-offset", String(offset));
      }
    });
  }

  function goTo(i) {
    active = ((i % items.length) + items.length) % items.length;
    update();
    resetAuto();
  }

  function next() {
    goTo(active + 1);
  }

  function prev() {
    goTo(active - 1);
  }

  function resetAuto() {
    if (timer) clearInterval(timer);
    if (prefersReducedMotion) return;
    timer = setInterval(next, 5500);
  }

  items.forEach((item, i) => {
    const link = item.querySelector(".vv-coverflow-card");
    if (!link) return;

    link.addEventListener("click", (e) => {
      if (i !== active) {
        e.preventDefault();
        goTo(i);
      }
    });

    if (prefersReducedMotion) return;
    item.addEventListener("mouseenter", () => {
      if (i !== active) item.classList.add("is-peek");
    });
    item.addEventListener("mouseleave", () => item.classList.remove("is-peek"));
  });

  prevBtn?.addEventListener("click", prev);
  nextBtn?.addEventListener("click", next);
  root.addEventListener("mouseenter", () => timer && clearInterval(timer));
  root.addEventListener("mouseleave", resetAuto);

  update();
  resetAuto();

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(update, 120);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initCounters();
  initRotatingWords();
  initStickySearch();
  initFilterPurpose();
  initQuickSim();
  initHeroVideo();
  initHeroCountryCoverflow();
});

// Re-init counters after HTMX swaps (e.g. boosted navigation back to home).
document.addEventListener("htmx:afterSettle", () => {
  initCounters();
});
