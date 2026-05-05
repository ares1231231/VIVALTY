/**
 * property-detail.js
 * - Image lightbox (keyboard + click nav)
 * - Score ring SVG animation on scroll (IntersectionObserver)
 */

// ── Lightbox ─────────────────────────────────────────────────────────────────
(function initLightbox() {
  const thumbs = document.querySelectorAll("[data-lightbox-src]");
  if (!thumbs.length) return;

  const overlay = document.createElement("div");
  overlay.id = "lb-overlay";
  overlay.innerHTML = `
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/95 backdrop-blur-sm" id="lb-bg">
      <button id="lb-prev" class="absolute left-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-2xl">‹</button>
      <button id="lb-close" class="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-lg">✕</button>
      <button id="lb-next" class="absolute right-4 top-1/2 -translate-y-1/2 flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/25 transition text-2xl">›</button>
      <img id="lb-img" src="" alt="" class="max-h-[90vh] max-w-[90vw] rounded-2xl shadow-2xl object-contain transition-opacity duration-200" />
      <div id="lb-counter" class="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-4 py-1.5 text-xs text-white font-medium"></div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.style.display = "none";

  const srcs = Array.from(thumbs).map(t => t.dataset.lightboxSrc);
  let current = 0;

  function show(idx) {
    current = (idx + srcs.length) % srcs.length;
    const img = overlay.querySelector("#lb-img");
    img.style.opacity = "0";
    img.src = srcs[current];
    img.onload = () => { img.style.opacity = "1"; };
    overlay.querySelector("#lb-counter").textContent = `${current + 1} / ${srcs.length}`;
    overlay.style.display = "block";
    document.body.style.overflow = "hidden";
  }
  function close() {
    overlay.style.display = "none";
    document.body.style.overflow = "";
  }

  thumbs.forEach((t, i) => { t.style.cursor = "zoom-in"; t.addEventListener("click", () => show(i)); });
  overlay.querySelector("#lb-prev").onclick = () => show(current - 1);
  overlay.querySelector("#lb-next").onclick = () => show(current + 1);
  overlay.querySelector("#lb-close").onclick = close;
  overlay.querySelector("#lb-bg").addEventListener("click", e => { if (e.target.id === "lb-bg") close(); });
  document.addEventListener("keydown", e => {
    if (overlay.style.display === "none") return;
    if (e.key === "ArrowRight") show(current + 1);
    if (e.key === "ArrowLeft")  show(current - 1);
    if (e.key === "Escape")     close();
  });
})();

// ── Score ring scroll animation ───────────────────────────────────────────────
(function initScoreRing() {
  const ring = document.querySelector("[data-score-ring]");
  if (!ring) return;

  const score = parseInt(ring.dataset.scoreRing, 10) || 0;
  const circumference = 2 * Math.PI * 15.9; // matches r=15.9 in SVG

  // Start at 0
  ring.style.strokeDasharray = `0 100`;
  ring.style.transition = "stroke-dasharray 1.4s cubic-bezier(0.4, 0, 0.2, 1)";

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          ring.style.strokeDasharray = `${score} 100`;
        }, 150);
        observer.unobserve(ring);
      }
    });
  }, { threshold: 0.3 });

  observer.observe(ring);
})();
