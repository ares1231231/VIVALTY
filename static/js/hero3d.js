import * as THREE from "https://unpkg.com/three@0.165.0/build/three.module.js";

const canvas = document.getElementById("hero-3d-canvas");

if (!canvas) {
  // Home page only.
} else {
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0f172a, 7, 18);

  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 0.8, 6.8);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const ambient = new THREE.AmbientLight(0xffffff, 0.65);
  scene.add(ambient);

  const point = new THREE.PointLight(0x34d399, 1.3, 30);
  point.position.set(3, 3, 4);
  scene.add(point);

  const orbGeometry = new THREE.IcosahedronGeometry(1.35, 1);
  const orbMaterial = new THREE.MeshPhysicalMaterial({
    color: 0x10b981,
    roughness: 0.14,
    metalness: 0.38,
    transmission: 0.35,
    thickness: 1.6,
    clearcoat: 0.4,
    emissive: 0x1f2937,
    emissiveIntensity: 0.2,
  });
  const orb = new THREE.Mesh(orbGeometry, orbMaterial);
  orb.position.set(0, 0.2, 0);
  scene.add(orb);

  const ringGroup = new THREE.Group();
  scene.add(ringGroup);

  for (let i = 0; i < 3; i += 1) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.05 + i * 0.33, 0.018, 14, 140),
      new THREE.MeshBasicMaterial({
        color: i % 2 ? 0xa7f3d0 : 0x38bdf8,
        transparent: true,
        opacity: 0.38 - i * 0.07,
      })
    );
    ring.rotation.x = 0.8 + i * 0.4;
    ring.rotation.y = i * 0.34;
    ringGroup.add(ring);
  }

  function resize() {
    const parent = canvas.parentElement || canvas;
    const width  = Math.max(20, parent.offsetWidth  || canvas.offsetWidth  || 400);
    const height = Math.max(20, parent.offsetHeight || canvas.offsetHeight || 420);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  resize();
  window.addEventListener("resize", resize);

  let rafId = null;
  const clock = new THREE.Clock();

  function animate() {
    const t = clock.getElapsedTime();
    orb.rotation.x = t * 0.26;
    orb.rotation.y = t * 0.42;
    orb.position.y = 0.2 + Math.sin(t * 0.8) * 0.11;
    ringGroup.rotation.z = t * 0.17;
    ringGroup.rotation.y = t * 0.11;
    point.position.x = 3 + Math.sin(t) * 1.2;
    renderer.render(scene, camera);
    rafId = requestAnimationFrame(animate);
  }

  animate();

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
      return;
    }
    if (!document.hidden && !rafId) {
      clock.start();
      animate();
    }
  });
}
