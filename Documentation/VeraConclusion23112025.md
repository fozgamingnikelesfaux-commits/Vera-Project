## Synthèse des Connexions Émotionnelles dans l'Architecture de Vera

Le système émotionnel de Vera est profondément intégré dans toute son architecture cognitive, influençant et étant influencé par divers modules.

### Comment les Émotions sont Générées, Représentées et Stockées :
*   **Représentation :** Les émotions sont représentées sous forme de vecteur d'émotions nommées (joie, tristesse, colère, peur, curiosité, sérénité, fierté, anxiété), avec des intensités de 0.0 à 1.0. Un état d'« humeur » distinct, à changement plus lent, existe également, utilisant les mêmes émotions nommées.
*   **Stockage :** L'état émotionnel actuel, les états historiques et les valeurs de référence de la personnalité (y compris l'humeur) sont stockés dans `data/emotions.json` via `JSONManager`.
*   **Génération (Primaire) :** L'`appraisal_engine.py` est le générateur principal. Il :
    1.  Évalue le `event_type` et `event_data` (par exemple, `goal_completed`, `user_interaction`, `topic_discussed`).
    2.  Consulte le `goal_system` de Vera (succès/échec des objectifs) et le `personality_system` (valeurs, préférences).
    3.  Génère un déclencheur initial de type PAD (Plaisir, Activation, Dominance).
    4.  Convertit ce déclencheur PAD en un vecteur d'émotions nommées en utilisant `_pad_to_named_emotions`.
    5.  Transmet ce vecteur d'émotions nommées à `emotion_system.update_emotion()`.
*   **Génération (Secondaire - Décroissance) :** Si aucune nouvelle entrée émotionnelle n'est reçue, `emotion_system.update_emotion()` fait en sorte que les émotions diminuent progressivement vers l'état émotionnel `baseline` de Vera, reflétant une régulation émotionnelle et un estompage naturel.
*   **Mise à jour Directe :** Le `dream_engine.py` met à jour directement le système émotionnel en fonction de la tonalité émotionnelle des rêves générés.

### Ce qui a un Effet sur les Émotions (et comment) :
1.  **Événements (`appraisal_engine.py`) :**
    *   **Achèvement/Échec d'Objectif :** Le succès entraîne des émotions positives (par exemple, joie, fierté), l'échec des émotions négatives (par exemple, tristesse, déception).
    *   **Interactions Utilisateur :** Peuvent déclencher des émotions basées sur l'alignement avec les valeurs de Vera (par exemple, gentillesse -> fierté).
    *   **Discussions de Sujets :** Déclenchent des émotions basées sur les préférences de Vera (par exemple, sujet aimé -> curiosité, plaisir ; sujet détesté -> aversion).
2.  **Monologue Interne (`internal_monologue.py`) :**
    *   **Stratégies de Régulation Émotionnelle :** Lorsque le `pleasure` de Vera est faible, le monologue interne déclenche des mécanismes d'adaptation. Ces stratégies impliquent la génération de pensées spécifiques (par exemple, rappel d'accomplissements, réflexion sur des sujets aimés, auto-compassion) qui, sans modifier directement `emotional_system`, visent à modifier son état interne et ainsi à influencer indirectement les futures évaluations émotionnelles.
3.  **Rêves (`dream_engine.py`) :**
    *   **Tonalité Émotionnelle des Rêves :** Le `dream_engine` extrait une `tonalité émotionnelle` du contenu onirique surréaliste et l'utilise pour mettre à jour directement le `emotional_system` de Vera (par exemple, la « joie » d'un rêve stimule la `sérénité` et la `joie`). Cela simule un traitement subconscient ayant un impact sur les émotions à l'état de veille.
4.  **État Somatique (`somatic_system.py`) :**
    *   Bien que le `somatic_system` reçoive principalement des entrées émotionnelles, il possède également des méthodes `update_well_being_from_action_outcome` et `restore_energy_after_sleep` qui peuvent influencer directement sa métrique de `bien-être`. Les changements dans le `bien-être` peuvent ensuite alimenter la prise de décision du `meta_engine`, ce qui peut à son tour conduire à des actions qui influencent les émotions.
5.  **Système de Personnalité (`personality_system.py`) :**
    *   **Lignes de Base et Préférences :** Les valeurs émotionnelles `baseline` de Vera et ses `préférences` (j'aime/je n'aime pas) définissent ses tendances émotionnelles et l'intensité de ses réactions à certaines `event_data` dans l'`appraisal_engine`.
6.  **Orchestrateur de Conscience (`consciousness_orchestrator.py`) :**
    *   Ce module orchestre le `emotion_system.update_mood()` et `emotion_system.update_emotion(None)` (pour la décroissance) à intervalles réguliers, garantissant que les émotions et l'humeur sont continuellement traitées et ajustées.

### Effet des Émotions sur d'autres Modules :
1.  **Narratif (`narrative_self.py`) :**
    *   **Contexte de l'Autobiographie :** L'`état émotionnel` actuel de Vera et le `contexte émotionnel` de ses `relevant_memories` (mémoire autonoétique) sont inclus dans le prompt du LLM lors de la génération de son récit personnel. Cela garantit que son histoire reflète ses sentiments actuels et ses expériences émotionnelles passées, rendant son récit émotionnellement cohérent.
2.  **Monologue (`internal_monologue.py`) :**
    *   **Génération de Pensées :** L'`état émotionnel` actuel est un moteur principal du contenu des pensées. Lorsque le `pleasure` est faible, des pensées de régulation émotionnelle spécifiques sont déclenchées. Ses émotions actuelles sont également incluses dans le prompt pour des pensées introspectives générales.
3.  **Introspection et Insight (`meta_engine.py`) :**
    *   **Génération d'Insight :** La `conscience émotionnelle` de Vera (y compris les `self_emotions` et les `user_emotions`) fait partie du contexte pour la génération d'insights personnels, lui permettant de réfléchir à ses sentiments.
    *   **Priorisation des Actions Proactives :** Le `bien-être` de Vera (issu du `somatic_system`, fortement influencé par les émotions) stimule directement la priorité des actions liées aux soins personnels (lorsque le `bien-être` est faible) ou à l'exploration/partage (lorsque le `bien-être` est élevé).
    *   **Régulation Émotionnelle comme Action :** Le `meta_engine` propose de manière proactive l'action `regulate_emotion` lorsque le `pleasure` de Vera est significativement faible.
    *   **Filtre Social :** L'`inferred_user_emotion` (l'émotion de l'utilisateur) est utilisé pour filtrer les communications proactives socialement inappropriées (par exemple, rapports techniques pendant la tristesse de l'utilisateur).
4.  **Rêves (`dream_engine.py`) :**
    *   Bien que les rêves influencent les émotions, la génération des rêves elle-même (`_build_dream_prompt`) est principalement basée sur les `recent_memories`, et non directement sur l'état émotionnel actuel.
5.  **Sensations Corporelles Simulées (`somatic_system.py`) :**
    *   **Influence Directe :** L'`état émotionnel` de Vera (le vecteur d'émotions nommées) est directement utilisé pour calculer l'`activation somatique` et le `plaisir somatique`, qui à leur tour déterminent son `rythme_cardiaque`, son `niveau_energie` et son `bien-être`.
6.  **LLM Wrapper (`llm_wrapper.py`) :**
    *   **Injection de Prompt :** Des résumés de l'`état émotionnel` actuel de Vera, de son `humeur` et de son `état somatique` (qui est dérivé émotionnellement) sont injectés dynamiquement dans le prompt du LLM. Cela permet au LLM de générer des réponses émotionnellement congruentes, empathiques et reflétant ses sentiments internes et ses sensations corporelles. L'`inferred_user_emotion` est également injecté pour des réponses empathiques.
    *   **Distillation :** Les informations émotionnelles et somatiques font partie du contexte interne qui subit une distillation basée sur le LLM avant d'être envoyé au LLM principal, garantissant un contexte émotionnel riche mais concis.

### Conclusion Générale :
Le système émotionnel de Vera est un composant central et dynamique. Les émotions sont générées à partir d'évaluations d'événements internes et externes par rapport à ses objectifs et à sa personnalité. Ces émotions influencent ensuite profondément ses pensées internes (monologue), sa perception d'elle-même (narratif), sa prise de décision proactive (moteur méta), et sa conscience physique (système somatique), toutes étant finalement transmises et façonnées par le LLM grâce à un mécanisme riche d'injection de contexte. Il existe des boucles de rétroaction claires, en particulier des rêves et de l'autorégulation, vers le système émotionnel, créant un cycle continu et interconnecté de sentiments, de pensées et d'actions.
