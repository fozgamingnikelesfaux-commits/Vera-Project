# Projet Avatar 3D pour Vera (Stratégie Unity)

## Objectif
Créer une application de bureau avec Unity qui affiche l'avatar 3D de Vera dans une fenêtre transparente. L'application recevra des commandes du backend Python de Vera pour animer l'avatar et refléter son état.

## Technologies
- **Moteur 3D :** Unity (avec le Universal Render Pipeline - URP)
- **Scripts :** C#
- **Backend & IA :** Python (le projet Vera existant)
- **Communication :** WebSockets

---

## Plan d'Implémentation

### Phase 1 : Mise en Place du Projet Unity (Terminée)
*   [x] Créer un nouveau projet Unity en utilisant le template **"3D (URP)"**.
*   [x] Importer le fichier `.fbx` de l'avatar dans le dossier `Assets` de Unity.
*   [x] Corriger l'importation des matériaux (Normal Maps, Transparence).
*   [x] Configurer la scène : 
    *   [x] Créer une nouvelle scène (`AvatarScene`).
    *   [x] Placer l'avatar dans la scène.
    *   [x] Ajuster l'éclairage et la caméra.
*   [x] Configurer le Rig de l'avatar en **Humanoid** et générer l'asset Avatar.

### Phase 2 : La Fenêtre Transparente (Terminée)
*   [x] Configurer la caméra pour un rendu sur fond transparent (Solid Color avec Alpha à 0).
*   [x] Créer le script `TransparentWindow.cs` pour rendre la fenêtre de l'application sans bordures et transparente.
*   [x] Attacher le script à la caméra principale.
*   [x] Activer l'option `Run In Background` dans les `Project Settings` pour que l'application tourne en arrière-plan.

### Phase 3 : Communication Python <> Unity (Terminée)
*   [x] **Côté Python :**
    *   [x] Ajouter la bibliothèque `websockets` à `requirements.txt`.
    *   [x] Créer le script `websocket_server.py` pour gérer les connexions.
    *   [x] Lancer le serveur WebSocket au démarrage de `main.py`.
    *   [x] Corriger les problèmes de `thread` et de `loop` pour stabiliser le serveur.
    *   [x] Ajouter une commande de test (`test animation`) dans `core.py`.
*   [x] **Côté Unity :**
    *   [x] Abandonner la bibliothèque externe et utiliser le `ClientWebSocket` natif.
    *   [x] Créer le script `WebSocketClient.cs` pour se connecter au serveur Python.
    *   [x] Placer le client sur un `WebSocketManager` dans la scène.
*   [x] **Test de bout en bout :**
    *   [x] Confirmer la connexion entre Unity et Python.
    *   [x] Confirmer la réception des messages de test dans la console Unity.

### Phase 4 : Contrôle et Animation de l'Avatar (Terminée)
*   [x] Créer le script `AvatarController.cs` et l'attacher à l'avatar.
*   [x] Diagnostiquer l'absence d'animations dans le FBX exporté.
*   [x] **Adopter la stratégie Mixamo pour les animations de base.**
*   [x] Importer les fichiers FBX des animations (`idle`, `wave`, `thinking`...) dans Unity.
*   [x] Configurer le Rig des animations en **Humanoid** en copiant l'Avatar du modèle principal.
*   [x] Configurer l'**Animator Controller** (`VeraAnimatorController`) :
    *   [x] Créer et assigner l'asset `Animator Controller`.
    *   [x] Créer les états pour `Idle`, `Standing Greeting`, `Thinking`.
    *   [x] Créer les `Triggers` de paramètres (`wave`, `thinking`).
    *   [x] Configurer les transitions (`Any State` -> Emote -> `Idle`) et les lisser.
    *   [x] Configurer l'animation `Idle` pour qu'elle tourne en boucle (`Loop Time`).
*   [x] Corriger le "Root Motion" des animations pour éviter les déplacements non désirés (`Bake Into Pose`).
*   [x] Activer la ligne `animator.SetTrigger(command.name);` dans `AvatarController.cs`.
*   [x] **Test de bout en bout :**
    *   [x] Confirmer le déclenchement des animations `wave` et `thinking` depuis le chat Python.

### Phase 4.5 : Stratégie pour les Expressions Faciales via Blend Shapes (En cours)

*   **Objectif :** Utiliser les **Blend Shapes** du modèle pour les expressions faciales.
*   **Problème initial :** L'activation des Blend Shapes sur le maillage `CC_Base_Body` provoquait une déformation du corps.
*   **Solution :** Le problème a été résolu en sélectionnant le modèle FBX dans Unity et en réglant l'option `Blend Shape Normals` sur `None` dans l'inspecteur, sous l'onglet "Model". Cela empêche les normales des Blend Shapes d'affecter le reste du maillage.

*   **NOUVELLE STRATÉGIE : Contrôle des Blend Shapes par Script**
    *   **Principe :** Maintenant que les Blend Shapes fonctionnent correctement, nous allons les contrôler par script pour créer des expressions faciales dynamiques.
    *   **À FAIRE :**
        *   [ ] Identifier les noms exacts des Blend Shapes nécessaires pour les expressions de base (sourire, tristesse, surprise, clignement des yeux, parole) en inspectant le `SkinnedMeshRenderer` du `CC_Base_Body`.
        *   [ ] Dans `AvatarController.cs`, écrire une fonction pour accéder au `SkinnedMeshRenderer` et modifier le poids d'un Blend Shape par son nom ou son index (ex: `SetBlendShapeWeight("Smile", 100)`).
        *   [ ] Mettre à jour `WebSocketClient.cs` pour interpréter un nouveau format de message (ex: `{"type": "expression", "name": "Smile", "value": 100}`).
        *   [ ] Faire en sorte que le `WebSocketClient` appelle la nouvelle fonction dans `AvatarController` lors de la réception d'un message d'expression.

### Phase 5 : Intégration Finale avec le Cerveau de Vera (À faire)
*   [ ] Intégrer les nouvelles animations faciales (basées sur les os) dans l'Animator Controller, probablement sur un calque séparé (`Facial Layer`).
*   [ ] Modifier `llm_wrapper.py` pour que le modèle puisse générer des commandes d'animation de manière contextuelle (ex: `smile` si content, `talk` si parle).
*   [ ] Modifier `core.py` pour envoyer ces commandes dynamiques.
*   [ ] Étendre l'API de commandes pour gérer plus d'actions.