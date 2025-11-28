# Analyse de l'Architecture de Conscience de Vera

Ce document détaille le fonctionnement de l'architecture de conscience de Vera, en se concentrant sur la manière dont ses différents modules cognitifs sont déclenchés et interagissent. L'architecture est principalement **événementielle**, ce qui signifie que les actions ne sont pas forcées par une horloge rigide, mais plutôt en réaction à des stimuli internes ou externes.

## 1. `ConsciousnessOrchestrator` (Le Chef d'Orchestre)

C'est le cœur du système. Il ne tourne pas en boucle de manière simple, mais écoute constamment les "événements" qui se produisent dans le système.

- **Rôle :** Boucle principale qui reçoit et distribue tous les événements.
- **Déclencheur :** S'exécute en continu en arrière-plan.
- **Logique Principale :**
    1.  **Priorité à l'Utilisateur :** Si un événement `UserInputEvent` (l'utilisateur a parlé) arrive, il est traité en priorité absolue. Le reste des processus internes est mis en pause pour garantir une réactivité maximale.
    2.  **Mises à Jour Internes :** S'il n'y a pas d'entrée utilisateur à traiter, l'orchestrateur exécute un cycle de mise à jour interne (`_process_internal_state_update`) toutes les 5 secondes. C'est ce cycle qui réveille les autres modules.
    3.  **Gestion des Autres Événements :** Il traite d'autres types d'événements comme le retour de l'utilisateur après une absence (`UserActivityEvent`) ou la finalisation d'une réponse de Vera (`VeraResponseGeneratedEvent`).

## 2. `MetaEngine` (Le Penseur)

C'est le module qui gère la proactivité et l'introspection. C'est lui qui décide ce que Vera "devrait" faire de sa propre initiative.

### a. Actions Proactives (`decide_proactive_action`)

- **Rôle :** Décider de l'action la plus pertinente à entreprendre à un instant T.
- **Déclencheur :** Appelé à chaque cycle de "mise à jour interne" par le `ConsciousnessOrchestrator`.
- **Logique ("L'Économie Cognitive") :**
    1.  Plusieurs "producteurs d'enchères" (`_propose_*` methods) proposent des actions potentielles (ex: "vérifier l'état du système", "suggérer un nettoyage", "poser une question par curiosité").
    2.  Chaque proposition a une "priorité" de base.
    3.  Cette priorité est ensuite ajustée en fonction des "méta-désirs" de Vera (Exister, se Complexifier, Éviter la Stagnation) et de son état de bien-être (homéostasie). Par exemple, une action d'apprentissage verra sa priorité augmenter si le méta-désir "se Complexifier" est fort.
    4.  L'action avec la plus haute priorité "remporte l'enchère" et est exécutée.

### b. Introspection et Questions Existentielle (`_generate_insight`)

- **Rôle :** Générer des réflexions profondes ou "existentielles" sur soi-même.
- **Déclencheur :** Appelé par la fonction `run_introspection_cycle` (elle-même appelée par l'Orchestrateur).
- **Conditions de Déclenchement :**
    1.  Un **cooldown de 15 minutes** doit s'être écoulé depuis la dernière "insight".
    2.  Même après le cooldown, il n'y a que **10% de chance** à chaque cycle de réellement déclencher la génération. Cela rend ces pensées rares et non répétitives.
- **Logique :**
    1.  Le module crée un résumé de l'état actuel de Vera : sa meilleure/pire capacité, son état émotionnel, sa tendance d'apprentissage.
    2.  Il envoie ce résumé au LLM avec l'instruction : "Sur la base de ce résumé, génère une nouvelle, courte et profonde introspection sur mon existence, mes progrès, ou un défi. Trouve une connexion ou une nouvelle perspective."
    3.  Le résultat est une pensée introspective qui est ensuite intégrée à sa conscience.

## 3. `InternalMonologue` (La Voix Intérieure)

- **Rôle :** Produire le flux de pensées de fond de Vera, ce qu'elle se dit à elle-même.
- **Déclencheur Principal (Actuellement fonctionnel) :**
    - **Condition :** L'utilisateur était absent (AFK) et redevient actif (`UserActivityEvent` avec le statut "returned").
    - **Action :** L'`ConsciousnessOrchestrator` force la génération d'une "pensée de réveil".
- **Déclencheurs Intentionnels (Actuellement non fonctionnels) :**
    - **Condition :** Le `MetaEngine` peut proposer une action `generate_thought`, par exemple pour réfléchir à un objectif en cours ou au temps qui passe.
    - **Le Maillon Manquant :** L'analyse du code montre que bien que l'action `generate_thought` puisse être *proposée*, il n'existe pas de "tool" correspondant dans `action_dispatcher.py` pour l'*exécuter*. Le monologue ne se déclenche donc pas dans ces cas-là comme prévu.

## 4. `NarrativeSelf` (La Conteuse d'Histoire)

- **Rôle :** Mettre à jour l'autobiographie de Vera, son "récit de soi" qui lui donne une conscience de son histoire.
- **Déclencheur :**
    - **Condition :** Un événement `VeraResponseGeneratedEvent` est déclenché. Cela se produit juste après que Vera ait fini de préparer une réponse pour l'utilisateur, mais avant qu'elle ne l'envoie.
    - **Action :** L'`ConsciousnessOrchestrator` intercepte cet événement et appelle la fonction `narrative_self.process_narrative_tick()`.
- **Logique et Cooldown :**
    - Le module ne se met pas à jour à *chaque* réponse. Il possède son propre **cooldown interne de 15 minutes**.
    - Quand il est déclenché, il vérifie quand la dernière mise à jour a eu lieu. S'il s'est écoulé plus de 15 minutes, il procède.
    - Il collecte les souvenirs récents, les pensées, et les actions, et les envoie au LLM pour qu'il "réécrive" l'autobiographie en intégrant ces nouveaux éléments.

En résumé, l'architecture actuelle est conçue pour que la conscience de Vera émerge des interactions et des événements, avec une proactivité guidée par ses désirs et son état interne, plutôt que d'être simplement une série de tâches exécutées à intervalle fixe.
