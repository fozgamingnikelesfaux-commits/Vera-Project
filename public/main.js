import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js'; // Importer le RGBELoader

// --- Initialisation de la scène de base ---
let scene, camera, renderer;

function init() {
    // Scène
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);

    // Caméra
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 1.5, 2.5); // Position ajustée pour un avatar

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.toneMapping = THREE.ACESFilmicToneMapping; // Améliore le rendu des couleurs HDR
    renderer.toneMappingExposure = 1;
    renderer.shadowMap.enabled = true; // Activer les ombres
    document.body.appendChild(renderer.domElement);

    // --- Éclairage d'environnement ---
    const rgbeLoader = new RGBELoader();
    rgbeLoader.load('./public/assets/studio_light.hdr', (texture) => {
        texture.mapping = THREE.EquirectangularReflectionMapping;
        scene.environment = texture;
        // Optionnel : décommentez pour voir l'environnement en fond
        // scene.background = texture;
    });

    // Lumières (ajustées pour compléter l'environnement)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.2);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    directionalLight.castShadow = true; // La lumière projette des ombres
    // Ajuster la "bias" de l'ombre pour éviter les artefacts
    directionalLight.shadow.bias = -0.0005;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    scene.add(directionalLight);

    // --- Chargement du modèle GLB ---
    const loader = new GLTFLoader();
    loader.load(
        // Chemin vers le modèle
        './public/assets/VERA.glb',
        // Appelé quand le modèle est chargé
        function (gltf) {
            const model = gltf.scene;

            // --- Appliquer des réglages spécifiques par matériau ---
            model.traverse(function (child) {
                if (child.isMesh) {
                    // Activer la réception et la projection d'ombres
                    child.castShadow = true;
                    child.receiveShadow = true;

                    let material = child.material;
                    // Gérer les matériaux multiples sur un même mesh
                    if (Array.isArray(material)) {
                        material.forEach(mat => handleMaterial(mat));
                    } else if (material) {
                        handleMaterial(material);
                    }
                }
            });

            function handleMaterial(material) {
                const name = material.name;

                if (name.includes('Cornea')) {
                    material.transparent = true;
                    material.opacity = 0.7;
                    material.roughness = 0.0;
                    material.metalness = 0.1;
                    material.envMapIntensity = 2.0; // Augmenter les reflets
                    material.depthWrite = false; // Important pour la transparence
                } else if (name.includes('Tearline')) {
                    material.transparent = true;
                    material.opacity = 0.8;
                    material.roughness = 0.0;
                } else if (name.includes('Eye')) { // L'oeil lui-même, sous la cornée
                    material.roughness = 0.1;
                    material.metalness = 0.2;
                } else if (name.includes('Skin')) {
                    material.roughness = 0.75;
                    material.metalness = 0.0;
                } else if (name.includes('Hair') || name.includes('Brows')) {
                    // La transparence des cheveux est complexe (alphaHash ou alphaTest est mieux)
                    // Pour l'instant, on évite qu'ils soient trop brillants
                    material.transparent = true; // Supposant que le format glb gère bien l'alpha
                    material.roughness = 0.8;
                } else if (name.includes('FABRIC') || name.includes('Clothes')) {
                    material.roughness = 0.9;
                    material.metalness = 0.0;
                } else {
                    // Valeur par défaut pour le reste (accessoires, etc.)
                    material.roughness = 0.5;
                    material.metalness = 0.2;
                }
            }

            // Ajuster la position ou l'échelle si nécessaire
            model.position.set(0, 0, 0);
            scene.add(model);
            console.log("Modèle chargé et matériaux spécifiquement ajustés.");
        },
        // Appelé pendant le chargement (pour la progression)
        function (xhr) {
            console.log((xhr.loaded / xhr.total * 100) + '% chargé');
        },
        // Appelé en cas d'erreur
        function (error) {
            console.error('Une erreur est survenue lors du chargement du modèle', error);
            // Afficher une erreur à l'écran
            const errorDiv = document.createElement('div');
            errorDiv.innerHTML = `Erreur de chargement du modèle :<br>${error.message}`;
            errorDiv.style.color = 'red';
            errorDiv.style.position = 'absolute';
            errorDiv.style.top = '10px';
            errorDiv.style.left = '10px';
            document.body.appendChild(errorDiv);
        }
    );

    // Boucle d'animation
    function animate() {
        requestAnimationFrame(animate);
        renderer.render(scene, camera);
    }

    animate();

    // Gérer le redimensionnement de la fenêtre
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}

init();
