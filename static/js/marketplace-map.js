/**
 * marketplace-map.js
 * Leaflet map that reads property data from [data-map-props] JSON attribute
 * and renders clustered pin markers with popup cards.
 *
 * Loaded only when #marketplace-map exists.
 */

const mapEl = document.getElementById("marketplace-map");
if (!mapEl) {
  // Not on marketplace or map section hidden — nothing to do.
} else {
  // Lazy-load Leaflet CSS
  if (!document.querySelector('link[href*="leaflet"]')) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);
  }

  // Lazy-load Leaflet JS then init
  const script = document.createElement("script");
  script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  script.onload = initMap;
  document.head.appendChild(script);

  function initMap() {
    const L = window.L;
    const props = JSON.parse(mapEl.dataset.mapProps || "[]");

    const map = L.map(mapEl, {
      center: [40, 10],
      zoom: 3,
      zoomControl: true,
      scrollWheelZoom: false,
    });

    // Dark tile layer
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 18,
    }).addTo(map);

    // Score-based marker colour
    function scoreColor(score) {
      if (!score) return "#64748b";
      if (score >= 75) return "#10b981";
      if (score >= 50) return "#f59e0b";
      return "#ef4444";
    }

    function makeIcon(score) {
      const color = scoreColor(score);
      return L.divIcon({
        className: "",
        html: `<div style="
          background:${color};
          color:#fff;
          font-size:10px;
          font-weight:800;
          width:34px;height:34px;
          display:flex;align-items:center;justify-content:center;
          border-radius:50% 50% 50% 0;
          transform:rotate(-45deg);
          border:2px solid #fff;
          box-shadow:0 2px 8px rgba(0,0,0,.4);
        "><span style="transform:rotate(45deg)">${score || "?"}</span></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 34],
        popupAnchor: [0, -36],
      });
    }

    props.forEach(p => {
      if (!p.lat || !p.lon) return;
      const score = p.score;
      const marker = L.marker([p.lat, p.lon], { icon: makeIcon(score) });
      marker.bindPopup(`
        <div style="min-width:200px;font-family:system-ui,sans-serif">
          <a href="/properties/${p.id}/" style="display:block;font-weight:700;color:#0f172a;font-size:13px;text-decoration:none;margin-bottom:4px">${p.title}</a>
          <div style="font-size:11px;color:#64748b;margin-bottom:6px">${p.city}, ${p.country}</div>
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:14px;font-weight:800;color:#059669">${p.price}</span>
            <span style="background:${scoreColor(score)};color:#fff;border-radius:999px;padding:1px 8px;font-size:10px;font-weight:700">${score}/100</span>
          </div>
          <div style="font-size:11px;color:#64748b;margin-top:4px">ROI ${p.roi_min}–${p.roi_max}% · Yield ${p.yield}%</div>
          <a href="/properties/${p.id}/" style="display:inline-block;margin-top:8px;background:#059669;color:#fff;border-radius:8px;padding:4px 12px;font-size:11px;font-weight:600;text-decoration:none">View listing →</a>
        </div>
      `, { maxWidth: 260 });
      marker.addTo(map);
    });

    // Fit bounds if we have markers
    if (props.filter(p => p.lat && p.lon).length) {
      const lls = props.filter(p => p.lat && p.lon).map(p => [p.lat, p.lon]);
      if (lls.length) map.fitBounds(L.latLngBounds(lls), { padding: [30, 30], maxZoom: 7 });
    }

    // Toggle map button
    const toggleBtn = document.getElementById("map-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const wrap = document.getElementById("map-wrap");
        const isHidden = wrap.classList.contains("hidden");
        wrap.classList.toggle("hidden", !isHidden);
        toggleBtn.textContent = isHidden ? "Hide map" : "Show map";
        if (isHidden) setTimeout(() => map.invalidateSize(), 200);
      });
    }
  }
}
