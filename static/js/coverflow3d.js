/**
 * coverflow3d.js — Circular Three.js destination coverflow for the home hero.
 *
 * Always shows the same number of cards on left and right (wrapped indices).
 * Falls back silently if the canvas or WebGL is unavailable.
 */
import * as THREE from "https://unpkg.com/three@0.165.0/build/three.module.js";

const root = document.querySelector("[data-coverflow-3d]");
const canvas = document.getElementById("coverflow-canvas");
const dataEl = document.getElementById("coverflow-data");

if (root && canvas && dataEl) {
  initCoverflow3d(root, canvas, dataEl).catch(() => {
    root.setAttribute("data-coverflow-fallback", "1");
  });
}

async function initCoverflow3d(root, canvas, dataEl) {
  let markets = [];
  try {
    markets = JSON.parse(dataEl.textContent || "[]");
  } catch {
    return;
  }
  if (!markets.length) return;

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const prevBtn = root.querySelector("[data-coverflow-prev]");
  const nextBtn = root.querySelector("[data-coverflow-next]");
  const stage = root.querySelector("[data-coverflow-stage]");

  const IMG_PARAMS = "?auto=format&fit=crop&w=1400&q=88";
  const COUNTRY_IMGS = {
    FR: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34",
    PT: "https://images.unsplash.com/photo-1513735492246-483525079686",
    ES: "https://images.unsplash.com/photo-1583422409516-2895a77efded",
    AE: "https://images.unsplash.com/photo-1518684079-3c830dcef090",
    GB: "https://images.unsplash.com/photo-1533929736458-ca588d08c8be",
    CH: "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99",
    IT: "https://images.unsplash.com/photo-1531572753322-ad063cecc140",
  };

  const n = markets.length;
  const sideCount = Math.min(3, Math.floor((n - 1) / 2));
  const aeIdx = markets.findIndex((m) => m.code === "AE");
  let active = aeIdx >= 0 ? aeIdx : Math.floor(n / 2);
  let targetActive = active;
  let animT = 1;
  let autoTimer = null;
  let dragging = false;
  let dragStartX = 0;
  let dragDelta = 0;
  let visible = true;
  let frame = 0;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 40);
  camera.position.set(0, 0.12, 5.15);

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
  } catch {
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.9));
  const key = new THREE.DirectionalLight(0xfff4e0, 1.35);
  key.position.set(2.2, 3.4, 4.5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x9ec9ff, 0.62);
  rim.position.set(-3.5, 0.8, -2);
  scene.add(rim);
  const warm = new THREE.PointLight(0xf5d486, 0.75, 14);
  warm.position.set(0, -0.2, 3.6);
  scene.add(warm);

  const cardGroup = new THREE.Group();
  scene.add(cardGroup);

  const CARD_W = 1.3;
  const CARD_H = 1.78;
  const RIM_PAD = 0.07;

  // Soft contact shadow under the fan
  const floorGeo = new THREE.PlaneGeometry(10, 2.4);
  const floorMat = new THREE.MeshBasicMaterial({
    color: 0x000000,
    transparent: true,
    opacity: 0.32,
    depthWrite: false,
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1.72;
  scene.add(floor);

  const cards = [];
  const loader = new THREE.TextureLoader();
  loader.crossOrigin = "anonymous";

  await Promise.all(
    markets.map(async (market, index) => {
      const base = COUNTRY_IMGS[market.code];
      const url = base ? `${base}${IMG_PARAMS}` : null;
      let photo = null;
      if (url) {
        try {
          photo = await loadTexture(loader, url);
        } catch {
          photo = null;
        }
      }
      const texture = buildCardTexture(photo, market.code, market.label);
      const material = new THREE.MeshPhysicalMaterial({
        map: texture,
        roughness: 0.26,
        metalness: 0.1,
        clearcoat: 0.72,
        clearcoatRoughness: 0.2,
        reflectivity: 0.42,
        transparent: true,
        toneMapped: true,
      });
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(CARD_W, CARD_H), material);
      mesh.userData = { index, href: market.href, code: market.code };
      cardGroup.add(mesh);

      // Gold rim plane (slightly larger, only bright when active)
      const rimMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(CARD_W + RIM_PAD, CARD_H + RIM_PAD),
        new THREE.MeshBasicMaterial({
          color: 0xf5d486,
          transparent: true,
          opacity: 0,
          depthWrite: false,
        })
      );
      rimMesh.position.z = -0.016;
      mesh.add(rimMesh);

      // Reflection clone (faded)
      const reflectMat = material.clone();
      reflectMat.opacity = 0.26;
      reflectMat.transparent = true;
      reflectMat.depthWrite = false;
      const reflect = new THREE.Mesh(new THREE.PlaneGeometry(CARD_W, CARD_H), reflectMat);
      reflect.scale.y = -1;
      reflect.position.y = -(CARD_H + 0.08);
      reflect.renderOrder = -1;
      mesh.add(reflect);

      cards.push({ mesh, rimMesh, reflect, reflectMat, material, index });
    })
  );

  // Keep DOM order stable for raycasts; layout uses circular offsets.
  cards.sort((a, b) => a.index - b.index);

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const clock = new THREE.Clock();

  function circularOffset(i, center) {
    let d = i - center;
    while (d > n / 2) d -= n;
    while (d < -n / 2) d += n;
    return d;
  }

  function layoutFor(center, immediate = false) {
    const wide = window.innerWidth >= 1024;
    const spacing = window.innerWidth < 480 ? 1.28 : window.innerWidth < 768 ? 1.52 : wide ? 1.86 : 1.68;
    const depth = 0.78;
    const angle = 0.32;
    camera.position.z = window.innerWidth < 480 ? 6.25 : window.innerWidth < 768 ? 5.75 : 5.35;

    cards.forEach((card) => {
      const offset = circularOffset(card.index, center);
      const abs = Math.abs(offset);
      const hidden = abs > sideCount;
      const target = {
        x: offset * spacing,
        y: abs * 0.02,
        z: abs === 0 ? 1.55 : 0.55 - abs * depth,
        rotY: -offset * angle,
        scale: abs === 0 ? 1.18 : Math.max(0.78, 1 - abs * 0.08),
        opacity: hidden ? 0 : abs === 0 ? 1 : Math.max(0.72, 1 - abs * 0.08),
        rim: abs === 0 ? 0.72 : abs === 1 ? 0.12 : 0,
      };

      if (!card.state || immediate) {
        card.state = { ...target };
        card.target = { ...target };
      } else {
        card.target = target;
      }
      card.mesh.visible = !hidden;
      card.mesh.userData.offset = offset;
    });
  }

  function applyState(dt) {
    const ease = 1 - Math.exp(-10 * dt);
    cards.forEach((card) => {
      const s = card.state;
      const t = card.target;
      s.x += (t.x - s.x) * ease;
      s.y += (t.y - s.y) * ease;
      s.z += (t.z - s.z) * ease;
      s.rotY += (t.rotY - s.rotY) * ease;
      s.scale += (t.scale - s.scale) * ease;
      s.opacity += (t.opacity - s.opacity) * ease;
      s.rim += (t.rim - s.rim) * ease;

      card.mesh.position.set(s.x, s.y, s.z);
      card.mesh.rotation.y = s.rotY;
      card.mesh.scale.setScalar(s.scale);
      card.material.opacity = s.opacity;
      card.reflectMat.opacity = s.opacity * 0.2;
      card.rimMesh.material.opacity = s.rim;
      card.mesh.renderOrder = 10 - Math.round(Math.abs(card.mesh.userData.offset || 0));
    });
  }

  function goTo(i, user = true) {
    targetActive = ((i % n) + n) % n;
    animT = 0;
    layoutFor(targetActive);
    root.setAttribute("data-active-code", markets[targetActive].code);
    const live = document.getElementById("coverflow-live");
    if (live) live.textContent = `${markets[targetActive].label} selected`;
    if (user) resetAuto();
  }

  function next() {
    goTo(targetActive + 1);
  }

  function prev() {
    goTo(targetActive - 1);
  }

  function resetAuto() {
    if (autoTimer) clearInterval(autoTimer);
    if (prefersReducedMotion) return;
    autoTimer = setInterval(() => {
      if (visible && !dragging) goTo(targetActive + 1, false);
    }, 4800);
  }

  function resize() {
    const rect = (stage || canvas).getBoundingClientRect();
    const w = Math.max(1, rect.width);
    const h = Math.max(1, rect.height);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    layoutFor(targetActive);
  }

  function setPointerFromEvent(event) {
    const rect = canvas.getBoundingClientRect();
    const clientX = event.clientX ?? event.touches?.[0]?.clientX ?? 0;
    const clientY = event.clientY ?? event.touches?.[0]?.clientY ?? 0;
    pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  }

  function pickCard() {
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(
      cards.map((c) => c.mesh),
      false
    );
    return hits[0]?.object || null;
  }

  function onPointerDown(event) {
    dragging = true;
    dragDelta = 0;
    dragStartX = event.clientX ?? event.touches?.[0]?.clientX ?? 0;
    root.classList.add("is-dragging");
  }

  function onPointerMove(event) {
    const x = event.clientX ?? event.touches?.[0]?.clientX ?? 0;
    if (dragging) {
      dragDelta = x - dragStartX;
      return;
    }
    setPointerFromEvent(event);
    const hit = pickCard();
    canvas.style.cursor = hit ? "pointer" : "grab";
  }

  function onPointerUp(event) {
    root.classList.remove("is-dragging");
    if (!dragging) return;
    dragging = false;

    if (Math.abs(dragDelta) > 42) {
      if (dragDelta < 0) next();
      else prev();
      return;
    }

    setPointerFromEvent(event);
    const hit = pickCard();
    if (!hit) return;
    const idx = hit.userData.index;
    if (idx === targetActive) {
      if (hit.userData.href) window.location.href = hit.userData.href;
    } else {
      goTo(idx);
    }
  }

  prevBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    prev();
  });
  nextBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    next();
  });

  canvas.addEventListener("pointerdown", onPointerDown);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener(
    "touchstart",
    (e) => {
      onPointerDown(e);
    },
    { passive: true }
  );
  canvas.addEventListener(
    "touchmove",
    (e) => {
      onPointerMove(e);
    },
    { passive: true }
  );
  canvas.addEventListener("touchend", onPointerUp);

  root.addEventListener("mouseenter", () => autoTimer && clearInterval(autoTimer));
  root.addEventListener("mouseleave", resetAuto);

  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      prev();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    } else if (e.key === "Enter") {
      const href = markets[targetActive]?.href;
      if (href) window.location.href = href;
    }
  });

  const io = new IntersectionObserver(
    ([entry]) => {
      visible = entry?.isIntersecting ?? true;
    },
    { threshold: 0.15 }
  );
  io.observe(root);

  window.addEventListener("resize", () => {
    clearTimeout(resize._t);
    resize._t = setTimeout(resize, 100);
  });

  layoutFor(active, true);
  resize();
  root.classList.add("is-ready");
  root.setAttribute("data-active-code", markets[active].code);
  const live = document.getElementById("coverflow-live");
  if (live) live.textContent = `${markets[active].label} selected`;
  resetAuto();

  function tick() {
    frame = requestAnimationFrame(tick);
    if (!visible) return;
    const dt = Math.min(clock.getDelta(), 0.05);

    // Smooth active index transition marker for aria
    if (active !== targetActive) {
      animT = Math.min(1, animT + dt * 2.4);
      if (animT >= 1) {
        active = targetActive;
        root.setAttribute("data-active-code", markets[active].code);
      }
    }

    applyState(prefersReducedMotion ? 1 : dt);

    // Subtle breathing on center card
    if (!prefersReducedMotion) {
      const t = clock.elapsedTime;
      cards.forEach((card) => {
        if (card.mesh.userData.offset === 0) {
          card.mesh.position.y += Math.sin(t * 1.2) * 0.008;
          card.rimMesh.material.opacity = 0.35 + Math.sin(t * 2.1) * 0.12;
        }
      });
      floor.material.opacity = 0.22 + Math.sin(t * 1.1) * 0.03;
    }

    renderer.render(scene, camera);
  }

  tick();
}

function loadTexture(loader, url) {
  return new Promise((resolve, reject) => {
    loader.load(url, resolve, undefined, reject);
  });
}

function buildCardTexture(photoTexture, code, label) {
  const w = 768;
  const h = 1056;
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");

  // Rounded card clip
  roundRect(ctx, 0, 0, w, h, 64);
  ctx.clip();

  if (photoTexture?.image) {
    const img = photoTexture.image;
    const scale = Math.max(w / img.width, h / img.height);
    const dw = img.width * scale;
    const dh = img.height * scale;
    ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
  } else {
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, "#1e293b");
    g.addColorStop(1, "#0f172a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }

  // Depth vignette + bottom scrim
  const scrim = ctx.createLinearGradient(0, h * 0.32, 0, h);
  scrim.addColorStop(0, "rgba(0,0,0,0)");
  scrim.addColorStop(0.5, "rgba(0,0,0,0.22)");
  scrim.addColorStop(1, "rgba(8,14,28,0.78)");
  ctx.fillStyle = scrim;
  ctx.fillRect(0, 0, w, h);

  const top = ctx.createLinearGradient(0, 0, 0, h * 0.28);
  top.addColorStop(0, "rgba(8,14,30,0.18)");
  top.addColorStop(1, "rgba(8,14,30,0)");
  ctx.fillStyle = top;
  ctx.fillRect(0, 0, w, h);

  // Specular edge
  ctx.strokeStyle = "rgba(255,255,255,0.34)";
  ctx.lineWidth = 4;
  roundRect(ctx, 5, 5, w - 10, h - 10, 58);
  ctx.stroke();

  ctx.strokeStyle = "rgba(245,212,134,0.28)";
  ctx.lineWidth = 2;
  roundRect(ctx, 10, 10, w - 20, h - 20, 54);
  ctx.stroke();

  // Glass label — two lines so the country name reads as a headline
  const pillW = Math.min(w * 0.86, 620);
  const pillH = 148;
  const pillX = (w - pillW) / 2;
  const pillY = h - 196;
  ctx.fillStyle = "rgba(8, 14, 28, 0.62)";
  roundRect(ctx, pillX, pillY, pillW, pillH, 36);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,0.1)";
  roundRect(ctx, pillX, pillY, pillW, pillH, 36);
  ctx.fill();
  ctx.strokeStyle = "rgba(245,212,134,0.55)";
  ctx.lineWidth = 2;
  roundRect(ctx, pillX, pillY, pillW, pillH, 36);
  ctx.stroke();

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(0,0,0,0.55)";
  ctx.shadowBlur = 12;
  const codeText = String(code || "").toUpperCase();
  const nameText = String(label || "").toUpperCase();

  ctx.font = "700 28px Inter, system-ui, sans-serif";
  ctx.fillStyle = "rgba(245,212,134,0.95)";
  ctx.fillText(codeText, w / 2, pillY + 46);

  let fontSize = nameText.length > 10 ? 44 : 52;
  ctx.font = `800 ${fontSize}px Inter, system-ui, sans-serif`;
  while (fontSize > 30 && ctx.measureText(nameText).width > pillW - 48) {
    fontSize -= 1;
    ctx.font = `800 ${fontSize}px Inter, system-ui, sans-serif`;
  }
  ctx.fillStyle = "#ffffff";
  ctx.fillText(nameText, w / 2, pillY + 98);
  ctx.shadowBlur = 0;

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.needsUpdate = true;
  return tex;
}

function roundRect(ctx, x, y, w, h, r) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}
