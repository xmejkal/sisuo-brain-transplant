// The viewer's 3D tab: the board's own board.glb, drawn with the three.js tscircuit already
// installs. tools/build-viewer.py inlines this file and three.js through an import map, so the
// page needs no network; the model itself is the base64 in the page's #model script element.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/GLTFLoader';
import { OrbitControls } from 'three/addons/OrbitControls';

/** The page's background behind the board, matching the PCB tab's dark stage. */
const STAGE_COLOUR = 0x0c0a06;

/** Where the camera starts, as a direction scaled by the model's size: above and to one side. */
const CAMERA_DIRECTION = new THREE.Vector3(0.6, 0.9, 0.8);

function modelBytes() {
  const encoded = document.getElementById('model').textContent.trim();
  return Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
}

function frameTheModel(model, camera, controls) {
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3()).length();
  const centre = box.getCenter(new THREE.Vector3());
  controls.target.copy(centre);
  camera.position.copy(centre).add(CAMERA_DIRECTION.clone().multiplyScalar(size));
  camera.near = size / 100;
  camera.far = size * 20;
  camera.updateProjectionMatrix();
}

export function show() {
  const panel = document.getElementById('p-3d');
  const loading = panel.querySelector('.loading');
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(STAGE_COLOUR);
  panel.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 2.0);
  sun.position.set(1, 2, 1.5);
  scene.add(sun);

  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.autoRotate = true;
  controls.autoRotateSpeed = 1.2;
  controls.addEventListener('start', () => { controls.autoRotate = false; });

  new GLTFLoader().parse(modelBytes().buffer, '', (gltf) => {
    scene.add(gltf.scene);
    frameTheModel(gltf.scene, camera, controls);
    loading.remove();
  }, (error) => {
    loading.textContent = 'board.glb could not be read: ' + error.message;
  });

  function fitToPanel() {
    renderer.setSize(panel.clientWidth, panel.clientHeight, false);
    camera.aspect = panel.clientWidth / Math.max(panel.clientHeight, 1);
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(fitToPanel).observe(panel);
  fitToPanel();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
}
