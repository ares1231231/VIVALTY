/**
 * globe3d.js — Animated Three.js globe for the Vivalty markets page.
 *
 * Renders a textured sphere with glowing country pins and an auto-rotation loop.
 * Clicking a pin fires a custom "globe:pin-click" event with { code, name }.
 * Gracefully does nothing if #globe-canvas is absent.
 */
import * as THREE from "https://unpkg.com/three@0.165.0/build/three.module.js";

const canvas = document.getElementById("globe-canvas");
if (!canvas) {
  // Not on markets page — nothing to do.
} else {
  // ── Country pin data (lat/lon in degrees) ────────────────────────────────
  const PINS = [
    { code: "FR", name: "France",      lat: 46.2,  lon: 2.2,   color: 0x3b82f6 },
    { code: "GB", name: "UK",          lat: 55.4,  lon: -3.4,  color: 0x6366f1 },
    { code: "ES", name: "Spain",       lat: 40.4,  lon: -3.7,  color: 0xf59e0b },
    { code: "CH", name: "Switzerland", lat: 46.8,  lon: 8.2,   color: 0x10b981 },
    { code: "IT", name: "Italy",       lat: 41.9,  lon: 12.5,  color: 0xef4444 },
    { code: "AE", name: "UAE",         lat: 23.4,  lon: 53.8,  color: 0xf97316 },
    { code: "PT", name: "Portugal",    lat: 39.4,  lon: -8.2,  color: 0x8b5cf6 },
  ];

  // ── Scene setup ──────────────────────────────────────────────────────────
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0f172a, 10, 30);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0, 3.2);

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  // ── Lighting ─────────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));
  const sun = new THREE.DirectionalLight(0x34d399, 1.6);
  sun.position.set(5, 3, 5);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x93c5fd, 0.6);
  fill.position.set(-4, -2, -4);
  scene.add(fill);

  // ── Globe sphere ─────────────────────────────────────────────────────────
  const globeGeo = new THREE.SphereGeometry(1, 64, 64);
  const globeMat = new THREE.MeshPhysicalMaterial({
    color: 0x0f2d4a,
    roughness: 0.55,
    metalness: 0.15,
    clearcoat: 0.3,
    emissive: 0x051525,
    emissiveIntensity: 0.4,
  });
  const globe = new THREE.Mesh(globeGeo, globeMat);
  scene.add(globe);

  // Wireframe overlay (lat/lon grid feel)
  const wireGeo = new THREE.SphereGeometry(1.003, 24, 24);
  const wireMat = new THREE.MeshBasicMaterial({
    color: 0x38bdf8,
    wireframe: true,
    transparent: true,
    opacity: 0.06,
  });
  scene.add(new THREE.Mesh(wireGeo, wireMat));

  // Glow halo
  const haloGeo = new THREE.SphereGeometry(1.12, 32, 32);
  const haloMat = new THREE.MeshBasicMaterial({
    color: 0x10b981,
    transparent: true,
    opacity: 0.07,
    side: THREE.BackSide,
  });
  scene.add(new THREE.Mesh(haloGeo, haloMat));

  // ── Helper: lat/lon → 3D position ────────────────────────────────────────
  function latLonToVec3(lat, lon, r = 1) {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    return new THREE.Vector3(
      -r * Math.sin(phi) * Math.cos(theta),
       r * Math.cos(phi),
       r * Math.sin(phi) * Math.sin(theta)
    );
  }

  // ── Country pins ─────────────────────────────────────────────────────────
  const pinMeshes = [];
  const tooltipEl = document.getElementById("globe-tooltip");

  PINS.forEach((pin) => {
    const pos = latLonToVec3(pin.lat, pin.lon, 1.03);

    // Glowing dot
    const dotGeo = new THREE.SphereGeometry(0.028, 12, 12);
    const dotMat = new THREE.MeshBasicMaterial({ color: pin.color });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    dot.position.copy(pos);
    dot.userData = pin;
    scene.add(dot);
    pinMeshes.push(dot);

    // Pulse ring
    const ringGeo = new THREE.RingGeometry(0.034, 0.048, 20);
    const ringMat = new THREE.MeshBasicMaterial({
      color: pin.color,
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.copy(pos);
    ring.lookAt(new THREE.Vector3(0, 0, 0));
    ring.rotateX(Math.PI / 2);
    ring.userData = { baseScale: 1, phase: Math.random() * Math.PI * 2 };
    scene.add(ring);
    dot.userData.ring = ring;
  });

  // ── Raycasting for pin hover / click ─────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let hoveredPin = null;

  function onPointerMove(e) {
    if (!tooltipEl) return;
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const hits = raycaster.intersectObjects(pinMeshes);
    if (hits.length) {
      const pin = hits[0].object.userData;
      hoveredPin = pin;
      tooltipEl.textContent = pin.name;
      tooltipEl.style.left = (e.clientX - canvas.getBoundingClientRect().left + 10) + "px";
      tooltipEl.style.top  = (e.clientY - canvas.getBoundingClientRect().top  - 28) + "px";
      tooltipEl.classList.remove("opacity-0");
      canvas.style.cursor = "pointer";
    } else {
      hoveredPin = null;
      tooltipEl.classList.add("opacity-0");
      canvas.style.cursor = "default";
    }
  }

  function onClick() {
    if (!hoveredPin) return;
    canvas.dispatchEvent(new CustomEvent("globe:pin-click", {
      bubbles: true,
      detail: { code: hoveredPin.code, name: hoveredPin.name },
    }));
    // Navigate to marketplace filtered by country
    window.location.href = `/marketplace/?country=${hoveredPin.code}`;
  }

  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("click", onClick);

  // ── Drag to rotate ────────────────────────────────────────────────────────
  let isDragging = false;
  let prevX = 0, prevY = 0;
  let velX = 0, velY = 0;
  let autoRotate = true;

  canvas.addEventListener("pointerdown", (e) => {
    isDragging = true;
    autoRotate = false;
    prevX = e.clientX;
    prevY = e.clientY;
    velX = velY = 0;
  });
  window.addEventListener("pointerup", () => {
    isDragging = false;
    // resume auto-rotate after 2 s of inactivity
    setTimeout(() => { autoRotate = true; }, 2000);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    const dx = e.clientX - prevX;
    const dy = e.clientY - prevY;
    velX = dx;
    velY = dy;
    globe.rotation.y += dx * 0.006;
    globe.rotation.x += dy * 0.004;
    globe.rotation.x = Math.max(-1.1, Math.min(1.1, globe.rotation.x));
    // Keep pins in sync with globe rotation
    pinMeshes.forEach(p => { p.parent === scene && (p.rotation.copy(globe.rotation)); });
    prevX = e.clientX;
    prevY = e.clientY;
  });

  // ── Resize ────────────────────────────────────────────────────────────────
  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const w = Math.max(20, rect.width);
    const h = Math.max(20, rect.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize);

  // ── Group everything for easy rotation ──────────────────────────────────
  const globeGroup = new THREE.Group();
  // Move globe + pins + grid into a group for unified rotation
  scene.remove(globe);
  // Re-add via group
  globeGroup.add(globe);
  globeGroup.add(...scene.children.filter(c => c instanceof THREE.Mesh && c !== globe));
  scene.add(globeGroup);

  // ── Animation loop ────────────────────────────────────────────────────────
  const clock = new THREE.Clock();
  let rafId;

  function animate() {
    const t = clock.getElapsedTime();

    if (autoRotate) {
      globeGroup.rotation.y += 0.002;
    }

    // Pulse rings
    globeGroup.children.forEach(child => {
      if (child.geometry?.type === "RingGeometry") {
        const phase = child.userData.phase || 0;
        const s = 1 + 0.35 * Math.sin(t * 2.4 + phase);
        child.scale.setScalar(s);
        child.material.opacity = 0.55 * (1 - (s - 1) / 0.35) * 0.8 + 0.1;
      }
    });

    sun.position.x = 5 * Math.cos(t * 0.2);
    sun.position.z = 5 * Math.sin(t * 0.2);

    renderer.render(scene, camera);
    rafId = requestAnimationFrame(animate);
  }

  animate();

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && rafId) { cancelAnimationFrame(rafId); rafId = null; }
    else if (!document.hidden && !rafId) { clock.start(); animate(); }
  });
}
