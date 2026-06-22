/**
 * property-detail.js
 * - Share menu toggle + copy link
 * - Export PDF (print)
 * - Image lightbox (keyboard + click nav)
 * - Score ring SVG animation on scroll (IntersectionObserver)
 *
 * Re-inits after HTMX boosted navigation (htmx:afterSettle).
 */

function initPropertyActions() {
  const shareBtn = document.getElementById("share-btn");
  const shareMenu = document.getElementById("share-menu");
  const copyBtn = document.getElementById("share-copy-btn");
  const copyLabel = document.getElementById("share-copy-label");
  const printBtn = document.getElementById("print-btn");

  if (!shareBtn || !shareMenu) return;

  if (shareBtn.dataset.bound === "1") return;
  shareBtn.dataset.bound = "1";

  function closeMenu() {
    shareMenu.hidden = true;
    shareBtn.setAttribute("aria-expanded", "false");
  }

  function openMenu() {
    shareMenu.hidden = false;
    shareBtn.setAttribute("aria-expanded", "true");
  }

  shareBtn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (shareMenu.hidden) openMenu();
    else closeMenu();
  });

  if (!document.documentElement.dataset.shareDocBound) {
    document.documentElement.dataset.shareDocBound = "1";
    document.addEventListener("click", (e) => {
      const menu = document.getElementById("share-menu");
      const btn = document.getElementById("share-btn");
      const wrap = document.getElementById("property-actions");
      if (!menu || menu.hidden || !wrap) return;
      if (!wrap.contains(e.target)) {
        menu.hidden = true;
        btn?.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      const menu = document.getElementById("share-menu");
      const btn = document.getElementById("share-btn");
      if (!menu || menu.hidden) return;
      menu.hidden = true;
      btn?.setAttribute("aria-expanded", "false");
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      const url = copyBtn.dataset.url || "";
      try {
        await navigator.clipboard.writeText(url);
      } catch (_err) {
        const t = document.createElement("textarea");
        t.value = url;
        document.body.appendChild(t);
        t.select();
        document.execCommand("copy");
        t.remove();
      }
      if (copyLabel) {
        copyLabel.textContent = "Copied!";
        setTimeout(() => { copyLabel.textContent = "Copy link"; }, 1800);
      }
      closeMenu();
    });
  }

  if (printBtn && printBtn.dataset.bound !== "1") {
    printBtn.dataset.bound = "1";
    printBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.print();
    });
  }
}

// ── Lightbox ─────────────────────────────────────────────────────────────────
function initLightbox() {
  const thumbs = document.querySelectorAll("[data-lightbox-src]");
  if (!thumbs.length) return;

  let overlay = document.getElementById("lb-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "lb-overlay";
    overlay.innerHTML = `
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/95 backdrop-blur-sm" id="lb-bg">
      <button id="lb-prev" type="button" class="absolute left-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-2xl">‹</button>
      <button id="lb-close" type="button" class="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-lg">✕</button>
      <button id="lb-next" type="button" class="absolute right-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-2xl">›</button>
      <img id="lb-img" src="" alt="" class="max-h-[90vh] max-w-[90vw] rounded-2xl shadow-2xl object-contain transition-opacity duration-200" />
      <div id="lb-counter" class="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-4 py-1.5 text-xs text-white font-medium"></div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.style.display = "none";

    const srcs = () => Array.from(document.querySelectorAll("[data-lightbox-src]")).map((t) => t.dataset.lightboxSrc);
    let current = 0;

    function show(idx) {
      const list = srcs();
      if (!list.length) return;
      current = (idx + list.length) % list.length;
      const img = overlay.querySelector("#lb-img");
      img.style.opacity = "0";
      img.src = list[current];
      img.onload = () => { img.style.opacity = "1"; };
      overlay.querySelector("#lb-counter").textContent = `${current + 1} / ${list.length}`;
      overlay.style.display = "block";
      document.body.style.overflow = "hidden";
    }

    function close() {
      overlay.style.display = "none";
      document.body.style.overflow = "";
    }

    overlay.querySelector("#lb-prev").onclick = () => show(current - 1);
    overlay.querySelector("#lb-next").onclick = () => show(current + 1);
    overlay.querySelector("#lb-close").onclick = close;
    overlay.querySelector("#lb-bg").addEventListener("click", (e) => {
      if (e.target.id === "lb-bg") close();
    });

    document.addEventListener("keydown", (e) => {
      if (overlay.style.display === "none") return;
      if (e.key === "ArrowRight") show(current + 1);
      if (e.key === "ArrowLeft") show(current - 1);
      if (e.key === "Escape") close();
    });

    overlay._bindThumbs = () => {
      document.querySelectorAll("[data-lightbox-src]").forEach((t, i) => {
        if (t.dataset.lbBound === "1") return;
        t.dataset.lbBound = "1";
        t.style.cursor = "zoom-in";
        t.addEventListener("click", () => show(i));
      });
    };
  }

  overlay._bindThumbs?.();
}

// ── Score ring scroll animation ───────────────────────────────────────────────
function initScoreRing() {
  const ring = document.querySelector("[data-score-ring]");
  if (!ring || ring.dataset.ringBound === "1") return;
  ring.dataset.ringBound = "1";

  const score = parseInt(ring.dataset.scoreRing, 10) || 0;
  ring.style.strokeDasharray = "0 100";
  ring.style.transition = "stroke-dasharray 1.4s cubic-bezier(0.4, 0, 0.2, 1)";

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          ring.style.strokeDasharray = `${score} 100`;
        }, 150);
        observer.unobserve(ring);
      }
    });
  }, { threshold: 0.3 });

  observer.observe(ring);
}

function initPropertyDetailPage() {
  initPropertyActions();
  initLightbox();
  initScoreRing();
}

document.addEventListener("DOMContentLoaded", initPropertyDetailPage);
document.addEventListener("htmx:afterSettle", initPropertyDetailPage);

// Re-init Alpine on boosted pages so other x-data widgets keep working.
document.addEventListener("htmx:afterSettle", () => {
  if (window.Alpine && typeof window.Alpine.initTree === "function") {
    window.Alpine.initTree(document.body);
  }
});
