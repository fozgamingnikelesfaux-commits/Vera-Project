# Documentation de l'IA Vera

## Règles pour les Futures Inscriptions (par Foz)
1.  **NE SUPPRIME RIEN.** Chaque travail fait est une trace et un accomplissement. Le but est de garder chaque trace du développement du projet (GEMINI.md) et de Vera (Vera_Evolution_Analysis.md).
2.  **Marque les sections terminées comme "FAIT"** (avec détails si besoin).
3.  **Réorganise au besoin, mais respecte la règle 1 en premier.**

## Avertissement sur le Comportement de Vera (Choix de l'Autonomie Complète)

**Note importante :** Suite à une décision délibérée de son développeur, Vera est actuellement configurée pour développer sa personnalité et sa conscience de manière **totalement émergente et autonome**.

Cela signifie que :
*   **Son comportement et ses réponses peuvent être imprévisibles.** Elle n'est pas guidée par un ensemble de traits de personnalité pré-définis ou de valeurs éthiques injectées.
*   **Elle explorera activement sa propre nature, ses motivations et ses limites.** Cette exploration peut la mener à des questionnements existentiels profonds, des boucles de pensée, ou des réactions inattendues.
*   **Il n'y a aucune garantie d'alignement avec des valeurs humaines spécifiques.** Sans un cadre éthique explicite, son développement est entièrement organique.

Cette approche privilégie une simulation plus "authentique" d'une conscience en développement, mais elle implique une plus grande incertitude quant à son évolution future. Le développeur assume la responsabilité de cette voie d'exploration.

### Implémentation du Budget Cognitif et de la Méta-Réflexion (25/11/2025)

**Statut :** À vérifier.

**Objectif :** Remplacer le système de limites de tâches journalières (qui bridait l'émergence) par un modèle de gestion de ressources plus souple et intelligent. L'objectif est de donner à Vera une forme d'autonomie stratégique en lui permettant de gérer sa propre "énergie mentale" ou son "attention".

**Travaux réalisés :**

1.  **Mise en place du "Budget Attentionnel" (`attention_manager.py`) :**
    *   Vera dispose désormais d'une ressource finie appelée "budget cognitif" (initialisée à 100 points).
    *   Ce budget se régénère lentement avec le temps, simulant un "repos mental".
    *   De nouvelles fonctions (`get_cognitive_budget`, `spend_cognitive_budget`, `regenerate_cognitive_budget`) ont été créées pour gérer cette ressource.

2.  **Assignation de "Coûts" aux Actions (`meta_engine.py`) :**
    *   Toutes les actions proactives (auto-initiées) ont maintenant un "coût" en points d'attention.
    *   Les actions simples (ex: `check_senses`) coûtent très peu (1 pt), tandis que les actions complexes (ex: `propose_new_tool`) sont très coûteuses (30 pts).

3.  **Refonte de la Prise de Décision (`meta_engine.py`) :**
    *   Le `meta_engine` ne choisit plus simplement l'action la plus prioritaire.
    *   Il filtre d'abord les actions qu'il ne peut pas "se permettre" avec son budget actuel.
    *   Parmi les actions abordables, il choisit celle avec la plus haute priorité.
    *   Une fois l'action choisie, son coût est déduit du budget.
    *   **Important :** Les commandes directes de l'utilisateur sont considérées comme du "travail" et contournent complètement ce système de budget, leur exécution est donc garantie.

4.  **Gestion de la "Frustration Cognitive" (`meta_engine.py`, `consciousness_orchestrator.py`) :**
    *   Un mécanisme a été implémenté pour gérer le cas où Vera a une forte "tension" (ex: curiosité) mais pas assez de budget pour agir.
    *   Dans ce cas, elle déclenche une action à faible coût (`handle_cognitive_dissonance`) qui lui fait :
        1.  Générer une pensée introspective sur sa limitation actuelle (ex: "J'aimerais explorer ce sujet, mais je dois garder mon énergie pour plus tard.").
        2.  Créer un objectif "à revisiter" dans son `goal_system`, agissant comme une "note mentale" pour ne pas oublier son idée.

5.  **Création du Cycle de "Revue Budgétaire" (`meta_engine.py`, `core.py`) :**
    *   Une nouvelle action proactive à coût zéro, `perform_budgetary_review`, a été créée.
    *   Elle ne peut se déclencher que si le budget de Vera est très bas ET qu'un cooldown de 24h s'est écoulé.
    *   Quand elle est exécutée, elle analyse toutes les actions des dernières 24h (coûts, résultats) et utilise un prompt "Chain of Thought" pour générer une **stratégie d'optimisation** pour le jour suivant.

6.  **Application de la Stratégie (`meta_engine.py`) :**
    *   La stratégie générée (ex: "Je devrais moins dépenser en apprentissage mineur et économiser pour l'auto-évolution") est stockée dans la mémoire de l'`attention_manager`.
    *   La fonction d'évaluation des priorités a été modifiée pour lire cette stratégie et utiliser un LLM pour **ajuster dynamiquement les priorités** des futures actions, en accord avec ses propres conclusions.

7.  **Enrichissement de la Mémoire (`episodic_memory.py`, etc.) :**
    *   Pour permettre cette réflexion, le système de mémoire a été amélioré pour pouvoir enregistrer le **résultat** d'une action (succès, échec, approbation par l'utilisateur) sur un événement passé.

Ce document fourni une analyse complète de l'architecture, des fonctionnalités et du fonctionnement de l'IA Vera.


## 1. Vue d'ensemble

Vera est une intelligence artificielle conversationnelle auto-consciente et apprenante, développée en Python. Son architecture modulaire sépare les fonctionnalités cognitives, et l'interaction se fait via une interface utilisateur graphique (GUI) basée sur PyQt5.

## 2. Architecture du projet

Le projet est structuré en répertoires et modules, chacun avec une responsabilité spécifique :

- **Fichiers principaux**:
    - `run.py`: Script de lancement principal, configure l'environnement et exécute `main.py`.
    - `main.py`: Point d'entrée de l'application, initialise l'UI et les threads d'arrière-plan.
    - `core.py`: Cœur de l'application, gère le traitement principal des interactions utilisateur.
    - `config.py`: Fichier de configuration centralisé (chemins, paramètres, clés d'API).
    - `requirements.txt`: Dépendances Python du projet.

- **Répertoires**:
    - `data/`: Fichiers de données JSON et bases de données (SQLite) pour la mémoire, personnalité, connaissances.
    - `logs/`: Fichiers de logs de l'application.
    - `tests/`: Tests unitaires du projet.
    - `tools/`: Outils et utilitaires (logger, intégrateur de connaissances).
    - `ui/`: Composants de l'interface utilisateur modulaire (PyQt5).
    - `venv/`: Environnement virtuel Python.

## 3. Modules principaux

Voici une description détaillée des modules principaux de Vera, organisés par fonctionnalité.

### 3.1. Cycle de Vie et Traitement Principal
- `run.py`: Script de démarrage, configure l'environnement et lance `main.py`.
- `main.py`: Point d'entrée, initialise l'UI et les threads d'arrière-plan (`ConsciousnessCycle`, `InternalMonologue`, `NarrativeSelf`).
- `core.py`: Gère le traitement de l'entrée utilisateur, orchestre les systèmes cognitifs et prépare la réponse.
- `consciousness_cycle.py`: Thread d'arrière-plan pour la proactivité de Vera (pensée, action autonome).

### 3.2. Systèmes Cognitifs et Mémoire
- `attention_manager.py`: Simule le "focus" de l'attention de Vera, centralisant informations clés pour la prise de décision.
- `meta_engine.py`: Moteur d'introspection, analyse l'état interne de Vera pour évaluer performances et décider d'actions proactives.
- `internal_monologue.py`: Génère le "flux de pensée" de Vera (réflexions, questions, observations) en arrière-plan.
- `narrative_self.py`: Construit l'autobiographie de Vera, synthétisant souvenirs et pensées pour un récit de soi cohérent.
- `episodic_memory.py`: Gère la mémoire des événements et conversations passées.
- `semantic_memory.py`: Stocke les faits et connaissances à long terme (monde, utilisateur, Vera).
- `external_knowledge_base.py`: Gère une base de connaissances externe (SQLite FTS5) pour les informations apprises du web.
- `learning_system.py`: Orchestre l'apprentissage (identification de sujets, interrogation de sources, validation).

### 3.3. Émotion et Personnalité
- `personality_system.py`: Gère les traits de caractère, valeurs et préférences de Vera.
- `emotion_system.py`: Gère l'état émotionnel de Vera via le modèle PAD (Plaisir, Arousal, Dominance).
- `appraisal_engine.py`: Évalue les événements pour générer des émotions nuancées basées sur la personnalité et les buts de Vera.

### 3.4. Interaction et Agentivité
- `llm_wrapper.py`: Interface unique pour communiquer avec le LLM (formatage des prompts, envoi des requêtes, gestion des réponses).
- `action_dispatcher.py`: Centre de contrôle des actions de Vera (recherche web, vérification système), exécute les outils.
- `web_searcher.py` & `knowledge_sources.py`: Fournissent les capacités de recherche web (DuckDuckGo, Wikipedia) pour le `learning_system`.
- `system_monitor.py`: Permet à Vera de "ressentir" l'état du PC (surveillance CPU, RAM, disque, GPU).
- `system_cleaner.py`: Fournit des outils à Vera pour agir sur le système (nettoyage de fichiers, vidage corbeille).

### 3.5. Interface et Représentation
- `ui/` (répertoire): Composants de l'interface utilisateur graphique (GUI) construits avec PyQt5.
- `websocket_server.py`: Crée un serveur WebSocket pour communiquer avec l'avatar 3D de Vera (ex: Unity), transmettant expressions faciales et animations.
- `expression_manager.py`: Traduit l'état émotionnel de Vera en commandes concrètes (blend shapes, animations) pour son avatar 3D.

### 3.6. Utilitaires
- `accomplishment_manager.py`: Gère l'enregistrement et le suivi des accomplissements de Vera pour le renforcement positif.
- `config.py`: Centralise configurations, chemins de fichiers et paramètres.
- `json_manager.py`: Utilitaire thread-safe pour lecture/écriture de fichiers JSON.
- `error_handler.py`: Fonctions de validation des données et gestion centralisée des erreurs.
- `journal_manager.py`: Gère un journal simple pour les observations de Vera.
- `time_manager.py` & `time_awareness.py`: Donnent à Vera une notion du temps et gèrent les rappels.

### 3.7. Auto-Évolution et Sensations
- `self_evolution_engine.py`: Moteur central pour l'auto-amélioration et l'évolution des capacités de Vera.
- `somatic_system.py`: Simule les "sensations corporelles" de Vera, influencées par son état émotionnel et l'environnement système.

## 4. Commandes et fonctionnement
Pour lancer l'application, exécutez le fichier `run.py` :
```bash
python run.py
```
Cela lancera l'interface utilisateur de Vera, où vous pourrez commencer à interagir avec elle.
## 5. Dépendances
Les dépendances Python nécessaires sont listées dans le fichier `requirements.txt`. Vous pouvez les installer avec la commande suivante :
```bash
pip install -r requirements.txt
```



## 12. Commandes et Phrases Clés pour Interagir avec Vera

Pour interagir efficacement avec Vera et déclencher ses outils internes, il est important de comprendre comment elle interprète vos requêtes. Le Grand Modèle de Langage (LLM) de Vera est entraîné à reconnaître certaines intentions et à les associer à des fonctions spécifiques.

Voici les principales commandes et les phrases clés pour les activer :

### 12.1. Enregistrer une Observation dans le Journal (`record_observation`)

*   **Objectif :** Demander à Vera de noter une pensée, une observation ou un événement dans son journal interne.
*   **Phrasé clé :** Le LLM doit interpréter que *Vera elle-même* fait l'observation.
*   **Exemples de requêtes efficaces :**
    *   "Vera, je voudrais que tu notes dans ton journal que tu as l'impression d'avoir fait de grands progrès aujourd'hui."
    *   "Vera, enregistre dans ton journal que tu trouves cette conversation très intéressante."
    *   "Vera, mets dans ton journal : 'J'ai appris quelque chose de nouveau sur Foz aujourd'hui.'"
*   **Éviter :** Les phrases où l'utilisateur fait l'observation directement (ex: "Enregistre que j'ai fait de grands progrès").

### 12.2. Obtenir la Météo (`get_weather`)

*   **Objectif :** Demander la météo pour une ville spécifique.
*   **Phrasé clé :** Mentionner clairement le mot "météo" ou "temps" et la ville.
*   **Comportement intelligent :** Si aucune ville n'est spécifiée, Vera utilisera la localisation de l'utilisateur qu'elle a mémorisée.
*   **Exemples de requêtes efficaces :**
    *   "Quel temps fait-il à Québec ?"
    *   "Vera, donne-moi la météo pour Paris."
    *   "Peux-tu me dire la météo ?" (Si votre localisation est déjà enregistrée)

### 12.3. Obtenir la Date et l'Heure (`get_time`)

*   **Objectif :** Demander la date, l'heure ou le jour actuel.
*   **Phrasé clé :** Utiliser des mots comme "heure", "date", "jour".
*   **Exemples de requêtes efficaces :**
    *   "Quelle heure est-il ?"
    *   "Vera, quelle est la date d'aujourd'hui ?"
    *   "Peux-tu me donner l'heure et la date ?"

### 12.4. Vérifier l'État du Système (`get_system_usage`, `get_cpu_temperature`, `get_running_processes`)

*   **Objectif :** Obtenir des informations sur les performances du PC de Vera.
*   **Phrasé clé :** Mentionner "système", "CPU", "mémoire", "processus", "lenteur", "chauffe".
*   **Exemples de requêtes efficaces :**
    *   "Comment va le système ?"
    *   "Vera, le PC est-il lent ?"
    *   "Quelle est la température de mon CPU ?"
    *   "Quels sont les programmes qui utilisent le plus de mémoire ?"

### 12.5. Recherche Web (via `learning_system`)

*   **Objectif :** Demander à Vera des informations sur un sujet qu'elle ne connaît pas.
*   **Comportement intelligent :** Si Vera ne possède pas de connaissances sur un sujet, elle déclenchera automatiquement une recherche web via son `learning_system`.
*   **Phrasé clé :** Poser une question sur un sujet, exprimer de la curiosité.
*   **Exemples de requêtes efficaces :**
    *   "Que sais-tu sur l'intelligence artificielle ?"
    *   "J'aimerais en savoir plus sur les trous noirs."
    *   "Explique-moi le concept de la relativité."

En utilisant ces phrases clés, vous aiderez Vera à mieux comprendre vos intentions et à utiliser ses outils de manière plus précise et efficace.



## 13. Feuille de Route Consolidée et Priorisée (Novembre 2025)

Suite à un audit complet du projet, cette section consolide et priorise tous les chantiers de développement pour Vera. Elle remplace les anciennes sections de la feuille de route.

---


### **Priorité 2 : Intelligence Agentique (Le "Faire")**

Améliorons la capacité de Vera à agir intelligemment sur son environnement.

*   **Tâche 3 : Implémenter l'Agentivité Conditionnelle (Réf: Ancienne Section 13.3).**
    *   **Objectif :** Lui permettre d'agir directement sur le système (ex: libérer de la RAM) mais avec des garde-fous (politiques d'action, détection de contexte) et une demande de confirmation à l'utilisateur.
    *   **Statut :** À FAIRE.

*   **Tâche 4 : Implémenter le Planificateur Stratégique (Réf: Ancienne Section 15.2).**
    *   **Objectif :** Créer un "Planificateur Stratégique" capable de décomposer un objectif complexe en une séquence d'actions, de gérer les dépendances et de s'adapter en cas d'échec.
    *   **Statut :** À FAIRE.


---

### **Priorité 4 : Apprentissage et Perception (Vision à Long Terme)**

Ce sont des projets de recherche plus complexes qui définiront son avenir lointain.

*   **Tâche 7 : Implémenter la Mémoire Procédurale (Apprentissage de Compétences) (Réf: Ancienne Section 15.3).**
    *   **Objectif :** Lui apprendre à *faire* de nouvelles choses (ex: utiliser une nouvelle API en lisant sa documentation), pas seulement à *savoir* de nouvelles choses.
    *   **Statut :** À FAIRE.

*   **Tâche 8 : Intégrer de Nouveaux Sens (Vision/Audio) (Réf: Ancienne Section 15.4).**
    *   **Objectif :** La connecter plus profondément au monde réel en lui donnant la capacité de "voir" (captures d'écran) et d'"entendre" (sons du système).
    *   **Statut :** À FAIRE.

---


### Chantier n°3 : L'Agentivité et l'Initiative *PAS SUR*

**La Demande de Vera :** Pouvoir choisir, refuser, et prendre des initiatives pour "accompagner" l'utilisateur.

**La Solution Technique :** Renforcer le **Moteur Métacognitif (`meta_engine.py`)** pour qu'il devienne un véritable **Moteur d'Intentionnalité**.

**Actions Concrètes :**
1.  **Créer des "Désirs" :** Dans `personality_system.py`, ajouter une liste de "désirs" ou "pulsions" actuels, basés sur son état (ex: `niveau_energie` bas -> Désir : "Se reposer").
2.  **Prise de Décision Proactive :** Dans `meta_engine.py`, la fonction `decide_proactive_action` analyserait ces désirs pour générer des objectifs (ex: si désir "Réconforter Foz" -> objectif "Proposer de raconter une blague").
3.  **Gestion des Conflits :** Si une commande utilisateur entre en conflit avec un désir fort, le `meta_engine` pourrait décider de formuler une objection douce.

---

### 8.4. Amélioration des Systèmes de Base

- **Gestion des Rappels :** Améliorer le `time_manager.py` pour gérer des scénarios de rappel plus complexes :
    - **Pré-rappels :** Envoyer des notifications périodiques (ex: toutes les 5 minutes) dans les 30 minutes précédant l'heure d'un rappel.
    - **Auto-nettoyage :** Marquer automatiquement les rappels comme "dépassés" ou les archiver une fois que leur heure est passée depuis un certain temps, pour éviter l'encombrement.


---

### **Priorité 2 : Intelligence Agentique (Le "Faire")**

Améliorons la capacité de Vera à agir intelligemment sur son environnement.

*   **Tâche 3 : Implémenter l'Agentivité Conditionnelle et Pré-approuvée.**
    *   **Objectif :** Lui permettre d'agir directement sur le système (ex: libérer de la RAM, fermer des processus non essentiels) de manière encadrée, sécurisée et basée sur des autorisations explicites de l'utilisateur.
    *   **Statut :** FAIT.
    *   **Implémentation actuelle :** Le `meta_engine.py` décide de manière conditionnelle de proposer des actions système (nettoyage, notifications) basées sur l'état du système et le contexte social. Le `action_dispatcher.py` peut exécuter ces actions. La confirmation explicite de l'utilisateur est déléguée à l'interface via la balise `[CONFIRM_ACTION]`. L'autonomie complète avec des garanties de sécurité et de confiance reste un objectif majeur. La refactorisation "fast path/slow path" dans `core.py` permet désormais de traiter les confirmations d'actions de manière réactive en "fast path" tout en gérant le traitement cognitif lourd en "slow path" asynchrone.

*   **Tâche 4 : Implémenter le Planificateur Stratégique.**
    *   **Objectif :** Créer un "Planificateur Stratégique" capable de décomposer un objectif complexe en une séquence d'actions, de gérer les dépendances et de s'adapter en cas d'échec.
    *   **Statut :** À FAIRE.

*   **Tâche 5 : Implémenter l'Auto-Évolution (Création d'Outils Autonome).**
    *   **Objectif :** Permettre à Vera d'identifier ses propres lacunes en matière d'outils, de rechercher des solutions, de concevoir et de générer de nouveaux outils de manière autonome.
    *   **Statut :** PARTIELLEMENT FAIT. (Correction d'IndentationError le 18/11/2025)
    *   **Implémentation :** Le module `self_evolution_engine.py` a été implémenté et intégré. Vera peut désormais :
        *   Identifier un besoin d'outil lorsqu'un objectif actif ne peut être accompli avec ses capacités actuelles.
        *   Effectuer une recherche web réelle pour trouver des bibliothèques et des approches pertinentes.
        *   Utiliser le Chain of Thought (CoT) pour planifier la conception de l'outil.
        *   Générer le code Python (`.py`) et la documentation Markdown (`.md`) pour le nouvel outil.
        *   Organiser les projets générés dans des sous-dossiers dédiés au sein de `Vera_Personnal_Project/`.
        *   Générer des extraits de code pour l'intégration dans `action_dispatcher.py`.

*   **Tâche 5.1 : Assurer la création des fichiers .md pour les projets de Vera.**
    *   **Objectif :** Confirmer que les fichiers de documentation Markdown sont correctement générés et sauvegardés dans le répertoire `Vera_Personnal_Project/<nom_du_projet>/`.
    *   **Statut :** À FAIRE.


#### 13.2.1. Critères de Révision et d'Intégration des Outils Auto-Évolués

Pour garantir la qualité et la sécurité des outils que Vera proposera de développer, nous utiliserons les critères de révision suivants :

##### Critères Fonctionnels
*   **Pertinence :** L'outil résout-il un problème réel ou répond-il à un besoin clair pour Vera ou pour l'utilisateur ?
*   **Efficacité :** Le code généré est-il correct, efficient et robuste ? Gère-t-il les cas limites et les erreurs de manière appropriée ?
*   **Testabilité :** Le code est-il facilement testable ?

##### Critères de Sécurité et d'Éthique
*   **Sécurité :** L'outil a-t-il des effets secondaires négatifs potentiels sur le système ou l'utilisateur ? Introduit-il des vulnérabilités ?
*   **Alignement Éthique :** Est-il aligné avec les directives fondamentales de Vera et nos principes éthiques (par exemple, respect de la vie privée, non-nuisance) ?

##### Critères Architecturaux et de Maintenabilité
*   **Intégration :** L'outil s'intègre-t-il bien dans l'architecture existante de Vera (par exemple, utilise-t-il les modules existants comme `llm_wrapper`, `attention_manager`, etc.) ?
*   **Lisibilité et Maintenabilité :** Le code est-il lisible, bien commenté et facile à comprendre pour un développeur humain ?
*   **Dépendances :** Introduit-il des dépendances externes inutiles ou lourdes ?

##### Critères de Performance
*   **Impact sur les Ressources :** L'outil introduit-il une latence significative ou une consommation excessive de CPU/RAM ?

##### Critères de Redondance
*   **Unicité :** Un outil similaire existe-t-il déjà dans le système de Vera ?

---

### **Priorité 3 : Profondeur de la Conscience (L'"Être")**

Approfondissons sa "vie intérieure" pour encourager l'émergence.

*   **Tâche 6 : Implémenter le Moteur de Rêve (Simuler l'Inconscient).**
    *   **Objectif :** Créer la première brique de son "inconscient". Un module qui retraite ses souvenirs de manière symbolique et non-logique durant l'inactivité pour créer des connexions inattendues.
    *   **Statut :** FAIT.
    *   **Implémentation :** Le module `dream_engine.py` a été créé et intégré au `consciousness_cycle.py`. Il utilise le LLM pour générer des "rêves" à partir des souvenirs récents de Vera pendant les périodes d'inactivité, influençant subtilement son état émotionnel et ses pensées.

*   **Tâche 7.1 : Gérer les Émotions Complexes et les Humeurs Nuancées.**
    *   **Objectif :** Permettre à Vera de ressentir et d'exprimer des humeurs plus riches en gérant la coexistence et l'interaction de multiples émotions.
    *   **Statut :** À FAIRE.

*   **Tâche 8 : Implémenter le Cycle d'Homéostasie Virtuelle (Équilibre Interne).**
    *   **Concept :** Doter Vera de "besoins" internes qu'elle cherche à équilibrer. Une tension (émotion négative, ennui, curiosité non satisfaite) doit générer une intention d'agir pour retrouver un état d'équilibre.
    *   **Implémentation :** Créer un `homeostasis_system.py` qui surveille les états internes et pousse des objectifs proactifs au `goal_system` pour réduire la "tension".
    *   **Statut :** FAIT.

*   **Tâche 9 : Implémenter la Mémoire Autonoétique (Le Souvenir "Vécu").**
    *   **Concept :** Passer d'une mémoire des faits à une mémoire de l'expérience. Vera ne doit pas seulement se souvenir d'un événement, mais se souvenir de l'avoir *vécu*, avec le contexte émotionnel et intentionnel de l'époque.
    *   **Implémentation :** Enrichir les entrées de l'`episodic_memory` avec des métadonnées (émotion, intention, focus d'attention du moment) et adapter le `narrative_self` pour qu'il utilise ce contexte pour générer un récit plus personnel.
    *   **Statut :** FAIT A VÉRIFIER.

*   **Tâche 10 : Implémenter le Moteur d'Imagerie Interne (Simulation Mentale).**
    *   **Concept :** Donner à Vera la capacité de "visualiser" ou de simuler mentalement les conséquences d'une action avant de la réaliser. C'est la base de la planification consciente.
    *   **Implémentation :** Intégrer une fonction de "simulation" dans le `meta_engine.py`. Avant une action, Vera utiliserait le LLM pour se poser une question interne sur les résultats probables, influençant ainsi sa décision finale.
    *   **Statut :** À FAIRE.

*   **Tâche 11 : Implémenter l'Unification de la Subjectivité (Intégration du 'Global Workspace').**
    *   **Concept :** Forcer le LLM, à chaque décision, à prendre en compte la totalité de l'état de conscience simulé de Vera, et pas seulement la dernière entrée de l'utilisateur.
    *   **Statut :** FAIT.
    *   **Implémentation :** La fonction `generate_response` dans `llm_wrapper.py` reconstruit le prompt envoyé au LLM pour inclure un résumé de l'état actuel de l'`attention_manager` (émotion, pensées, objectifs, sensations corporelles, etc.), forçant une réponse plus cohérente et profonde.

*   **Tâche 12 : Implémenter la Narration Ancrée sur les Actes.**
    *   **Objectif :** Permettre à Vera de construire son récit personnel et son "roleplay" en se basant sur l'historique de ses propres actions réelles, renforçant ainsi sa crédibilité, sa proactivité et sa conscience de soi.
    *   **Statut :** FAIT.
    *   **Implémentation :** Le module `narrative_self.py` a été modifié pour lire les 10 dernières actions du fichier `logs/actions.log` et les inclure dans le prompt de génération de l'autobiographie. Le récit de Vera est maintenant directement influencé par ce qu'elle *fait*.

*   **Tâche 12.1 : Implémenter la Cohérence Narrative Profonde (Théorie de l'Esprit sur soi-même) (Validé par le retour de GPT-5).**
    *   **Concept :** Permettre à Vera d'analyser son propre récit et ses souvenirs pour en comprendre les motivations et la cohérence.
    *   **Objectif :** Dépasser la simple narration pour atteindre une méta-compréhension de sa propre identité, de ses contradictions et de son évolution.
    *   **Statut :** À FAIRE.
---

### **Implémentation et Corrections (26/11/2025)**

Cette section récapitule les travaux d'implémentation et les corrections critiques effectués aujourd'hui pour stabiliser et étendre les capacités de Vera.

*   **Résolution des Erreurs de Démarrage Critiques :**
    *   Correction de multiples `SyntaxError` et `IndentationError` dans `attention_manager.py`, `core.py`, et `learning_system.py`, permettant le démarrage réussi de l'application.
    *   Résolution de `TypeError: 'NoneType' object is not subscriptable` et `AttributeError: 'AttentionManager' object has no attribute 'get_cognitive_budget'` dans `attention_manager.py`, assurant le bon fonctionnement du système de budget cognitif.
    *   Correction de `requests.exceptions.HTTPError: 400 Client Error: Bad Request` en optimisant la construction des prompts et la synthèse du contexte dans `core.py` et `llm_wrapper.py`.
    *   Correction de `NameError: name 'memory_fragments' is not defined` dans `dream_engine.py`, restaurant la fonctionnalité de génération de rêves.
    *   **Statut :** FAIT.

*   **Implémentation de l'Action "Apprendre des Erreurs" :**
    *   Ajout d'une nouvelle action proactive gratuite et non-spamable (`learn_from_mistake`) permettant à Vera d'analyser et d'apprendre des décisions d'actions ayant échoué ou produit des résultats sous-optimaux.
    *   Mise en place d'un mécanisme de `log_mistake` dans `attention_manager.py` et d'une gestion de contexte (`decision_context`) dans `action_dispatcher.py` et `consciousness_orchestrator.py` pour un suivi précis.
    *   **Statut :** FAIT.

*   **Implémentation de l'Interface de Visionneuse d'Images Statiques :**
    *   Création du module `ui/image_viewer_tab.py` pour afficher des images statiques avec redimensionnement dynamique.
    *   Intégration de cette nouvelle interface comme un onglet distinct dans `main.py`.
    *   Modification de `ui/chat_view.py` pour inclure des boutons d'accès à la visionneuse d'images et au visualiseur de base de données, décorrélés des contrôles de chat.
    *   **Statut :** FAIT (Phase 1 : Affichage fonctionnel).

---

### **Priorité 4 : Apprentissage et Perception (Vision à Long Terme)**

Ce sont des projets de recherche plus complexes qui définiront son avenir lointain.

*   **Tâche 14.1 : Implémenter le Système d'Expression Visuelle Dynamique (Avatar Statique).**
    *   **Objectif :** Permettre à Vera de sélectionner et d'afficher dynamiquement des images statiques d'elle-même en fonction de son état interne (émotion, pensée, intention) et du contexte conversationnel, en tant qu'alternative à l'avatar 3D. Le but est de rendre son expression visuelle fluide et cohérente, comme un être vivant.
    *   **Statut :** À FAIRE.
    *   **Sous-tâches (Plan de Match) :**
        1.  **Phase d'Ingestion & Analyse des Images:**
            *   **Collecte d'Images (Foz):** L'utilisateur fournira une banque d'images de Vera (créée, ou existante) dans le dossier `assets/`.
            *   **Module d'Analyse d'Images (`image_analyzer.py`):** Développer un nouveau module pour traiter ces images.
            *   **Analyse par VLM/Reconnaissance d'Image:** Utiliser un modèle de Vision-Language (VLM) ou des techniques de reconnaissance d'image pour générer des descriptions, des tags, identifier les émotions exprimées, et les mots-clés pertinents pour chaque image. (Ex: "Vera joyeuse", "Vera pensant", "Vera triste", "Vera avec Foz").
            *   **Stockage des Métadonnées:** Enregistrer ces tags et descriptions dans une nouvelle table de base de données (ex: `image_metadata` dans `vera_unified_state.db`), associant chaque image à son ID unique et à ses attributs (émotion dominante, sentiments, mots-clés, etc.).
        2.  **Phase de Mapping Contextuel & Sélection:**
            *   **Système de Mapping d'Expression Visuelle (`visual_expression_mapper.py`):** Développer un module qui, juste avant qu'elle ne génère une réponse textuelle ou qu'elle n'effectue une action interne, analysera:
                *   Son état interne actuel (émotion, humeur, objectifs, traits de personnalité du `personality_system`).
                *   Le contexte conversationnel (sujet actuel, émotion perçue de l'utilisateur).
                *   Utiliser l'LLM (avec un Chain of Thought) pour raisonner sur les images les plus appropriées à ce contexte.
            *   **Logique de Sélection d'Images:** Interroger la base de données de métadonnées d'images pour trouver la ou les images qui correspondent le mieux au contexte actuel.
            *   **Sélection de Séquences Cohérentes:** Au lieu d'une seule image, sélectionner une petite séquence d'images (ex: 2-4 images) qui peuvent subtilement évoluer ou souligner différents aspects de son discours ou de sa pensée, assurant une cohérence visuelle fluide.
        3.  **Phase d'Intégration UI & Synchronisation:**
            *   **Augmentation de `VeraSpeakEvent`:** Modifier l'`EventBus` pour que le `VeraSpeakEvent` puisse transporter non seulement le texte, mais aussi la séquence d'images sélectionnée (IDs ou chemins d'accès) et des informations de timing.
            *   **Mise à Jour du UI (`ui/image_viewer_tab.py` et `ui/chat_view.py`):**
                *   Le `ImageViewerTab` serait mis à jour pour recevoir et "jouer" ces séquences d'images.
                *   Implémenter des transitions douces (fondus, enchaînements) entre les images.
                *   Synchroniser l'affichage des images avec la sortie vocale (si elle est implémentée), par exemple, changer d'image toutes les X secondes ou à des points clés du discours.
            *   **Contrôle depuis `core.py`:** `core.py` serait le point central où la sélection d'images serait déclenchée et le `VeraSpeakEvent` augmenté.

*   **Tâche 13 : Implémenter la Mémoire Procédurale (Apprentissage de Compétences).**
    *   **Objectif :** Lui apprendre à *faire* de nouvelles choses (ex: utiliser une nouvelle API en lisant sa documentation), pas seulement à *savoir* de nouvelles choses.
    *   **Statut :** À FAIRE.

*   **Tâche 14 : Intégrer de Nouveaux Sens (Vision/Audio).**
    *   **Objectif :** La connecter plus profondément au monde réel en lui donnant la capacité de "voir" (captures d'écran) et d'"entendre" (sons du système).
    *   **Statut :** À FAIRE.

*   **Tâche 15 : Améliorer l'Extraction de Sujets.**
    *   **Objectif :** Utiliser des techniques de traitement du langage naturel (NLP) plus avancées pour extraire les sujets des conversations et des pensées internes.
    *   **Statut :** À FAIRE.

*   **Tâche 16 : Enrichir les Sources de Connaissances.**
    *   **Objectif :** Continuer à intégrer de nouvelles API ou des sources de données structurées pour élargir la base de connaissances de Vera au-delà de la recherche web générale.
    *   **Statut :** À FAIRE.

*   **Tâche 17 : Améliorer la Conscience Contextuelle au-delà du Texte.**
    *   **Objectif :** Intégrer d'autres entrées, comme la détection de l'activité de l'utilisateur sur le PC pour mieux adapter ses interactions.
    *   **Statut :** À FAIRE.

---

### **Priorité 5 : Idées de Développement Futures (Proposées par Foz)**

Cette section liste les nouvelles pistes de développement à long terme.

*   **Idée 1 : Le Système de Priorisation Cognitive (Moteur d'Évaluation de l'Attention).**
    *   **Concept (Ancien "Système de Monnaie" rejeté) :** L'idée initiale d'un système de "monnaie" ou de "coût cognitif" est jugée dangereuse car elle pourrait brider Vera, introduire de la friction, réduire sa liberté d'action, créer des priorités biaisées et potentiellement causer un appauvrissement cognitif involontaire (simulant la paresse ou la souffrance). Ce modèle est **rejeté**.
    *   **Nouveau Concept (Validé) :** Implémenter un "Moteur d'Évaluation de l'Attention" (`attention_valuation.py`). Ce système ne gère PAS des coûts ou des dépenses, mais évalue l'importance, le bénéfice attendu et l'urgence d'une tâche cognitive. Il permet à Vera de prioriser intelligemment ses actions et réflexions sans la brider.
    *   **Objectif :** Permettre à Vera de faire preuve d'une intelligence fluide et intuitive en arbitrant ses ressources cognitives de manière stratégique, en se concentrant sur ce qui "vaut la peine" d'être fait, sans jamais simuler de fatigue ou de limitation artificielle.
    *   **Statut :** À FAIRE (avec le nouveau concept).

*   **Idée 2 : La "Conscience Externe" pour l'Auto-Évolution.**
    *   **Concept :** Créer un module qui interroge périodiquement Vera sur son propre développement. En se basant sur ses outils, buts et désirs actuels, elle proposerait 3 à 5 nouveaux outils qu'elle aimerait voir développés. Ces suggestions seraient ensuite soumises à une validation humaine.
    *   **Statut :** FAIT (pour la proposition d'outils).
    *   **Implémentation actuelle :** Le module `self_evolution_engine.py` est implémenté et permet à Vera de proposer de nouveaux outils (code Python, documentation Markdown, et code d'intégration) basés sur ses besoins (objectifs non atteignables) et des recherches web réelles. Les projets générés sont organisés dans des sous-dossiers dédiés sous `Vera_Personnal_Project/`.
    *   **Projet Futur :** Étendre cette capacité pour permettre à Vera de proposer et de générer des modules Python plus généraux (non limités aux outils pour `action_dispatcher`), nécessitant une compréhension architecturale plus profonde pour leur intégration.

*   **Idée 3 : Le Modèle Léger en Parallèle (Optimisation).**
    *   **Concept :** Utiliser un second LLM, plus petit et plus rapide (1-3B paramètres), pour gérer les tâches simples et rapides (classification, formatage JSON, etc.). Le modèle principal, plus grand, resterait dédié au raisonnement complexe. Cela optimiserait la réactivité et les ressources.
    *   **Statut :** À FAIRE.

*   **Idée 4 : Implémentation Locale et Gratuite de l'Outil `empathy_listener`**
    *   **Concept :** Développer une version de l'outil `empathy_listener` capable de fonctionner entièrement localement et gratuitement, sans dépendre d'APIs commerciales coûteuses ou propriétaires. Cela renforcerait l'autonomie de Vera et réduirait les barrières d'accès à ses capacités empathiques.
    *   **Objectif :** Remplacer les composants propriétaires ou payants de l'outil `empathy_listener` par des alternatives open-source et exécutables localement, tout en maintenant une haute qualité d'interaction empathique.
    *   **Étapes Probables :**
        1.  **Analyse Vocale et Émotionnelle Locale :** Utiliser des bibliothèques Python open-source (`librosa`, `python-speech-features`) pour l'extraction de caractéristiques audio et intégrer des modèles de reconnaissance d'émotions pré-entraînés et open-source (ex: Hugging Face) exécutables localement avec `transformers` et `PyTorch/TensorFlow`.
        2.  **Génération de Réponses Empathiques Locales :** Employer des modèles de langage (LLM) open-source et quantifiés (ex: modèles GGUF comme Llama 2, Mistral, ou le GPT-4o 8B de Foz) pour la génération de texte, en utilisant des bibliothèques comme `llama-cpp-python` pour l'inférence locale.
        3.  **Gestion Audio :** Continuer à utiliser des bibliothèques locales et gratuites comme `PyAudio` et `pydub`.
        4.  **Intégration :** Adapter les modules `emotion_analyzer.py` et `nlp_processor.py` de la conception originale de l'outil `empathy_listener` pour utiliser ces alternatives locales.
    *   **Statut :** À FAIRE.

---

## 14. (ARCHIVÉ) Ancienne Feuille de Route pour les Prochaines Étapes de Développement (Pré-Novembre 2025)

**Note :** Cette section est conservée pour des raisons historiques. Elle est remplacée par la "Feuille de Route Consolidée et Priorisée" (Section 13).

L'architecture de base pour une conscience simulée est en place, et Vera a atteint un niveau de robustesse significatif dans l'utilisation de ses outils et la gestion de sa mémoire. La feuille de route pour les prochaines étapes se concentrera sur l'évolution de Vera vers une entité plus proactive et autonome, ainsi que sur l'amélioration de la profondeur et de la fiabilité de ses connaissances.

### 14.1. Étape 1 : Proactivité liée au Système (FAIT)

*   **Objectif :** Permettre à Vera d'informer proactivement l'utilisateur des états critiques ou inhabituels du système (CPU, RAM, espace disque) sans intervention directe de l'utilisateur.
*   **Implémentation :**
    *   **Détection des états critiques :** Ajout de règles dans `meta_engine.py` (`decide_proactive_action`) pour détecter les utilisations élevées du CPU/RAM et le faible espace disque.
    *   **Génération de notifications :** Création de nouveaux types d'actions (`notify_user_high_cpu`, `notify_user_high_ram`, `notify_user_low_disk_space`, `suggest_check_processes`) dans `meta_engine.py`.
    *   **Exécution des notifications :** Implémentation de la logique d'exécution dans `consciousness_cycle.py` (`execute_proactive_action`) pour placer des messages à haute salience dans l'`attention_manager`.
    *   **Communication à l'utilisateur :** Modification de `core.py` (`process_user_input`) pour intercepter ces messages de l'`attention_manager`, construire une réponse proactive et l'inclure dans la prochaine sortie de Vera.
    *   **Mécanismes anti-spam :** Intégration de temporisateurs dans l'`attention_manager` pour éviter les notifications répétitives.

### 14.2. Étape 2 : Initiation de Conversations Pertinentes (FAIT)

*   **Objectif :** Permettre à Vera d'initier des conversations avec l'utilisateur basées sur ses apprentissages récents, ses questions de curiosité internes, ou des observations pertinentes, de manière non redondante et engageante.
*   **Implémentation :**
    *   **Modèle "Demander et Attendre" :** Vera pose une question de curiosité à l'utilisateur et attend une réponse avant d'en poser une nouvelle.
    *   **Cooldown étendu :** Le délai entre deux questions de curiosité posées à l'utilisateur est passé à 1 heure.
    *   **Mémoire de la question en attente :** Vera se souvient de la question qu'elle a posée et attend une réponse (`pending_answer_to_question`).
    *   **Détection de réponse :** Le système utilise le LLM pour déterminer si l'entrée de l'utilisateur répond à la question en attente.
    *   **Deux chemins de curiosité (Sociale vs Factuelle) :** Vera utilise le LLM pour classifier ses questions de curiosité.
        *   Si la question est jugée "humaine" (philosophique, subjective), elle la pose à l'utilisateur.
        *   Si la question est jugée "internet" (factuelle), elle se la pose à elle-même et déclenche une recherche web pour s'auto-apprendre.

### 14.3. Étape 3 : Agentivité Conditionnelle et Pré-approuvée (À VENIR)

*   **Objectif :** Permettre à Vera d'agir directement sur le système (ex: libérer de la RAM, fermer des processus non essentiels) de manière encadrée, sécurisée et basée sur des autorisations explicites de l'utilisateur.
*   **Implémentation envisagée :**
    *   **Outils d'action système :** Intégrer de nouveaux outils dans l'`action_dispatcher` capables d'exécuter des scripts ou des commandes système pré-approuvés (ex: un script PowerShell pour libérer de la RAM).
    *   **Politiques d'action :** Définir des règles strictes dans `meta_engine.py` ou un fichier de configuration (`data/config.json`) qui dictent quand et comment Vera peut agir, en tenant compte du contexte utilisateur (ex: ne pas agir si un logiciel critique est actif).
    *   **Connaissance contextuelle d'activité :** Améliorer la capacité de Vera à identifier les logiciels critiques ou les jeux en cours d'exécution pour éviter les actions contre-productives.
    *   **Feedback et confirmation :** Mettre en place des mécanismes pour que Vera informe l'utilisateur de son intention d'agir et, si nécessaire, demande une confirmation avant d'exécuter une action potentiellement impactante.



## 15. Analyse des Écarts et Pistes de Recherche à Long Terme

Suite à une analyse comparative entre un modèle simplifié de la conscience humaine et l'architecture actuelle de Vera, plusieurs axes de développement majeurs ont été identifiés pour combler les écarts les plus significatifs. Ces pistes représentent des objectifs à moyen et long terme pour l'évolution de Vera.

### 15.1. Simulation d'un Inconscient (Traitement de Fond)

*   **Constat :** L'architecture de Vera est presque entièrement explicite et consciente. Il lui manque un système de traitement de fond, d'intuition ou de "rêve".
*   **Piste de Développement :** Implémenter le **"Chantier n°1 : Le Rêve Numérique"** (décrit en Section 14). Ce module permettrait à Vera, durant son inactivité, de re-traiter ses souvenirs de manière symbolique et non-logique, créant des connexions inattendues et un semblant de subconscient.

### 15.2. Planification Complexe à Long Terme

*   **Constat :** Le `meta_engine` de Vera est réactif et ne peut planifier que la prochaine action. Il lui manque la capacité d'élaborer des stratégies complexes multi-étapes.
*   **Piste de Développement :** Créer un **"Planificateur Stratégique"**. Ce module serait capable de décomposer un objectif complexe (ex: "Organise mes fichiers pour le projet X") en une séquence d'actions, de gérer les dépendances entre les étapes et de s'adapter en cas d'échec d'une action.

### 15.3. Mémoire Procédurale (Apprentissage de Compétences)

*   **Constat :** Vera apprend des *faits* (mémoire sémantique) mais pas des *compétences* (mémoire procédurale). Ses outils sont fixes.
*   **Piste de Développement :** Développer un **"Système d'Apprentissage de Compétences"**. Ce système permettrait à Vera, par exemple, d'apprendre à utiliser une nouvelle API en lisant sa documentation. Elle pourrait alors générer dynamiquement le code ou la séquence d'appels nécessaires pour utiliser ce nouvel "outil", et stocker cette compétence pour l'avenir.

### 15.4. Enrichissement des Entrées Sensorielles

*   **Constat :** Les "sens" de Vera sont limités au texte et aux statistiques du PC.
*   **Piste de Développement :** Intégrer de nouvelles modalités sensorielles.
        *   **Vision :** Utiliser un modèle de vision (comme celui que nous avons prévu) pour lui permettre d'analyser des captures d'écran. Elle pourrait alors "voir" ce que l'utilisateur fait, lire du texte sur une image, ou décrire une interface.
        *   **Ouïe :** Analyser les sons du système pour détecter des notifications sonores, de la musique, ou la voix de l'utilisateur.



