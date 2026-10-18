import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/controls/OrbitControls.js";

const FACE_COLORS = { U: "#f8f7f0", R: "#d94d43", F: "#239a69", D: "#f0c928", L: "#ed873d", B: "#3478c7" };
const FACE_NAMES = ["U", "R", "F", "D", "L", "B"];
const FACE_INDEX = Object.fromEntries(FACE_NAMES.map((face, i) => [face, i]));
const GRID = [-1, 0, 1];

function faceletIndex(face, x, y, z) {
  let row, col;
  switch (face) {
    case "U": row = z + 1; col = x + 1; break;
    case "R": row = 1 - y; col = 1 - z; break;
    case "F": row = 1 - y; col = x + 1; break;
    case "D": row = 1 - z; col = x + 1; break;
    case "L": row = 1 - y; col = z + 1; break;
    case "B": row = 1 - y; col = 1 - x; break;
    default: throw new Error(`Unknown face ${face}`);
  }
  return FACE_INDEX[face] * 9 + row * 3 + col;
}

function normalForFace(face) {
  return ({
    U: new THREE.Vector3(0, 1, 0), R: new THREE.Vector3(1, 0, 0),
    F: new THREE.Vector3(0, 0, 1), D: new THREE.Vector3(0, -1, 0),
    L: new THREE.Vector3(-1, 0, 0), B: new THREE.Vector3(0, 0, -1)
  })[face];
}

export class CubeView {
  constructor(canvas, onReady) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#f8f6ef");
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    this.camera.position.set(5.8, 5.2, 7.2);
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x888477, 2.1));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(5, 8, 7);
    key.castShadow = true;
    this.scene.add(key);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 5;
    this.controls.maxDistance = 11;
    this.controls.target.set(0, 0, 0);
    this.cubies = [];
    this.animationRunning = false;
    this.disposed = false;
    this.buildCubies();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas.parentElement);
    this.resize();
    this.renderLoop();
    onReady?.();
  }

  buildCubies() {
    const bodyGeometry = new THREE.BoxGeometry(0.96, 0.96, 0.96);
    const bodyMaterial = new THREE.MeshStandardMaterial({ color: "#22252a", roughness: 0.48, metalness: 0.02 });
    const stickerGeometry = new THREE.PlaneGeometry(0.82, 0.82);
    for (const x of GRID) for (const y of GRID) for (const z of GRID) {
      const cubie = new THREE.Mesh(bodyGeometry, bodyMaterial);
      cubie.position.set(x * 1.02, y * 1.02, z * 1.02);
      cubie.userData.homeGrid = { x, y, z };
      cubie.userData.grid = { x, y, z };
      cubie.castShadow = true;
      cubie.receiveShadow = true;
      cubie.userData.stickers = {};
      for (const face of FACE_NAMES) {
        const isOuter = (face === "U" && y === 1) || (face === "D" && y === -1) ||
          (face === "R" && x === 1) || (face === "L" && x === -1) ||
          (face === "F" && z === 1) || (face === "B" && z === -1);
        if (!isOuter) continue;
        const sticker = new THREE.Mesh(stickerGeometry, new THREE.MeshBasicMaterial({ color: FACE_COLORS[face], side: THREE.DoubleSide }));
        const n = normalForFace(face);
        sticker.position.copy(n.clone().multiplyScalar(0.486));
        if (face === "U") sticker.rotation.x = -Math.PI / 2;
        if (face === "D") sticker.rotation.x = Math.PI / 2;
        if (face === "R") sticker.rotation.y = Math.PI / 2;
        if (face === "L") sticker.rotation.y = -Math.PI / 2;
        if (face === "B") sticker.rotation.y = Math.PI;
        sticker.userData.face = face;
        sticker.userData.faceletIndex = faceletIndex(face, x, y, z);
        cubie.userData.stickers[face] = sticker;
        cubie.add(sticker);
      }
      this.cubies.push(cubie);
      this.scene.add(cubie);
    }
  }

  setState(facelets) {
    if (typeof facelets !== "string" || facelets.length !== 54 || /[^URFDLB]/.test(facelets)) {
      throw new Error("Backend cube state must contain exactly 54 URFDLB facelets.");
    }
    for (const cubie of this.cubies) {
      const { x, y, z } = cubie.userData.homeGrid;
      cubie.position.set(x * 1.02, y * 1.02, z * 1.02);
      cubie.quaternion.identity();
      cubie.rotation.set(0, 0, 0);
      cubie.userData.grid = { x, y, z };
      for (const [face, sticker] of Object.entries(cubie.userData.stickers)) {
        const letter = facelets[sticker.userData.faceletIndex];
        sticker.userData.color = letter;
        sticker.material.color.set(FACE_COLORS[letter]);
      }
    }
  }

  serializeVisibleState() {
    const result = Array(54).fill("?");
    const normal = new THREE.Vector3();
    const position = new THREE.Vector3();
    this.scene.updateMatrixWorld(true);
    for (const cubie of this.cubies) {
      for (const sticker of Object.values(cubie.userData.stickers)) {
        sticker.getWorldPosition(position);
        sticker.getWorldDirection(normal);
        const x = Math.round(position.x / 1.02), y = Math.round(position.y / 1.02), z = Math.round(position.z / 1.02);
        let face = null;
        if (normal.y > 0.9) face = "U";
        else if (normal.x > 0.9) face = "R";
        else if (normal.z > 0.9) face = "F";
        else if (normal.y < -0.9) face = "D";
        else if (normal.x < -0.9) face = "L";
        else if (normal.z < -0.9) face = "B";
        if (face && Math.abs(x) <= 1 && Math.abs(y) <= 1 && Math.abs(z) <= 1) {
          result[faceletIndex(face, x, y, z)] = sticker.userData.color || "?";
        }
      }
    }
    return result.join("");
  }

  async animateMove(token, duration = 260) {
    if (this.animationRunning) throw new Error("A cube animation is already running.");
    const parsed = parseMove(token);
    if (!parsed) throw new Error(`Unsupported move notation: ${token}`);
    this.animationRunning = true;
    const pivot = new THREE.Group();
    this.scene.add(pivot);
    const selected = this.cubies.filter(cubie => parsed.layers.includes(cubie.userData.grid[parsed.axis]));
    for (const cubie of selected) pivot.attach(cubie);
    const start = performance.now();
    const ease = t => 1 - Math.pow(1 - t, 3);
    await new Promise(resolve => {
      const frame = now => {
        const progress = Math.min(1, (now - start) / duration);
        pivot.rotation[parsed.axis] = parsed.angle * ease(progress);
        if (progress < 1) requestAnimationFrame(frame);
        else resolve();
      };
      requestAnimationFrame(frame);
    });
    pivot.updateMatrixWorld(true);
    for (const cubie of selected) {
      this.scene.attach(cubie);
      cubie.position.set(
        Math.round(cubie.position.x / 1.02) * 1.02,
        Math.round(cubie.position.y / 1.02) * 1.02,
        Math.round(cubie.position.z / 1.02) * 1.02
      );
      const euler = new THREE.Euler().setFromQuaternion(cubie.quaternion, "XYZ");
      euler.set(Math.round(euler.x / (Math.PI / 2)) * Math.PI / 2,
        Math.round(euler.y / (Math.PI / 2)) * Math.PI / 2,
        Math.round(euler.z / (Math.PI / 2)) * Math.PI / 2);
      cubie.quaternion.setFromEuler(euler);
      cubie.userData.grid = { x: Math.round(cubie.position.x / 1.02), y: Math.round(cubie.position.y / 1.02), z: Math.round(cubie.position.z / 1.02) };
    }
    this.scene.remove(pivot);
    this.animationRunning = false;
  }

  resize() {
    const width = Math.max(1, this.canvas.parentElement.clientWidth);
    const height = Math.max(1, this.canvas.parentElement.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  renderLoop() {
    if (this.disposed) return;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(() => this.renderLoop());
  }

  dispose() {
    this.disposed = true;
    this.resizeObserver.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
  }
}

function parseMove(token) {
  const match = /^([URFDLBMESxyzurfdlb])([2']?)$/.exec(token);
  if (!match) return null;
  const face = match[1];
  const suffix = match[2];
  const turns = suffix === "2" ? 2 : suffix === "'" ? -1 : 1;
  const table = {
    R: ["x", 1, [1]], L: ["x", -1, [-1]], U: ["y", 1, [1]], D: ["y", -1, [-1]],
    F: ["z", 1, [1]], B: ["z", -1, [-1]],
    r: ["x", 1, [0, 1]], l: ["x", -1, [-1, 0]], u: ["y", 1, [0, 1]],
    d: ["y", -1, [-1, 0]], f: ["z", 1, [0, 1]], b: ["z", -1, [-1, 0]],
    M: ["x", -1, [0]], E: ["y", -1, [0]], S: ["z", 1, [0]],
    x: ["x", 1, [-1, 0, 1]], y: ["y", 1, [-1, 0, 1]], z: ["z", 1, [-1, 0, 1]]
  };
  const [axis, outwardSign, layers] = table[face];
  return { axis, layers, angle: -outwardSign * turns * Math.PI / 2 };
}
