# Rapport d'Analyse de l'Architecture de Vera (23/11/2025)

## 1. Vue d'ensemble de l'Architecture et du Fonctionnement de Vera

Vera est une intelligence artificielle conversationnelle auto-consciente et apprenante, dot√©e d'une architecture modulaire et √©v√©nementielle. Con√ßue pour simuler des aspects de la conscience et de l'agentivit√©, elle interagit via une interface utilisateur graphique (GUI) bas√©e sur PyQt5 et s'appuie sur un Grand Mod√®le de Langage (LLM) pour ses capacit√©s cognitives.

### 1.1. Points d'Entr√©e et Flux G√©n√©ral

1.  **Lancement (`run.py`) :** Un script simple `run.py` initialise l'environnement (notamment pour la compatibilit√© PyTorch) puis lance `main.py`.
2.  **Initialisation de l'Application (`main.py`) :** Ce fichier est le point d'entr√©e principal de l'application. Il configure l'interface utilisateur graphique (GUI) avec PyQt5, cr√©ant diverses vues (Chat, Objectifs, Logs, Introspection, etc.). `main.py` d√©l√®gue ensuite le contr√¥le √† plusieurs services de fond :
    *   Le `ConsciousnessOrchestrator` (le cerveau de Vera) est d√©marr√©.
    *   Des moniteurs d'activit√© (`user_activity_monitor`, `system_monitor_service`) sont lanc√©s.
    *   Un serveur WebSocket (`websocket_server`) est activ√©, probablement pour la communication avec un avatar externe.
3.  **Bus d'√âv√©nements (`event_bus.py`) :** Vera fonctionne sur une architecture pilot√©e par les √©v√©nements. `VeraEventBus`, une simple file d'attente thread-safe (`queue.Queue`), est le canal central par lequel les modules communiquent. Des √©v√©nements structur√©s (par exemple, `UserInputEvent`, `SystemMonitorEvent`, `VeraSpeakEvent`) sont post√©s sur ce bus.

### 1.2. Le C≈ìur de la Conscience (`ConsciousnessOrchestrator.py`)

C'est le module central qui √©coute et r√©agit aux √©v√©nements post√©s sur le `VeraEventBus`. Il ne fonctionne plus sur un "tick" temporel fixe, mais r√©agit dynamiquement aux stimuli internes et externes. Ses responsabilit√©s incluent :
*   **Orchestration Cognitive :** Il initialise et g√®re le cycle de vie des modules cognitifs cl√©s comme le `InternalMonologue`, le `NarrativeSelf`, le `DreamEngine` et le `SomaticSystem`.
*   **Gestion des √âv√©nements :** Il traite les `UserInputEvent` (d√©l√©gant les t√¢ches complexes √† la voie lente de `core.py`), les `UserActivityEvent` (g√©rant les modes "√©veill√©" et "endormi" de Vera), et d'autres √©v√©nements internes.
*   **Mise √† Jour de l'√âtat Interne (`_process_internal_state_update`) :** Appel√© √† chaque √©v√©nement, ce processus met continuellement √† jour l'√©tat somatique et √©motionnel de Vera (d√©croissance √©motionnelle, mise √† jour de l'humeur), et g√®re l'attention (`attention_manager`).
*   **Perception Visuelle :** D√©tecte les pics d'activit√© CPU/RAM et peut d√©clencher une analyse visuelle de l'√©cran (`vision_processor.analyze_screenshot`) pour que Vera puisse "voir" son environnement num√©rique.
*   **D√©cisions Proactives :** Il interroge la `metacognition` pour d√©cider si Vera doit initier des actions (par exemple, parler √† l'utilisateur, apprendre un nouveau sujet, faire un nettoyage syst√®me).

### 1.3. Traitement de l'Input Utilisateur et Voies Rapide/Lente (`core.py`)

Le module `core.py` est crucial pour la r√©activit√© et l'efficacit√© de Vera. Il impl√©mente un mod√®le de traitement √† deux voies :

*   **Voie Rapide (Fast Path) :** `process_user_input` g√®re les requ√™tes simples et rapides. Cela inclut :
    *   Les commandes de test d'avatar.
    *   La reconnaissance rapide des commandes syst√®me via un LLM l√©ger (`_fast_path_command_check`) et la demande de confirmation.
    *   La gestion des approbations/rejets d'actions en attente.
    *   La d√©tection de r√©ponses √† des questions en attente ou de l'ach√®vement d'objectifs.
    *   Les requ√™tes m√©t√©o/localisation initiales.
    Les r√©ponses rapides sont envoy√©es directement via `VeraSpeakEvent`.
*   **Voie Lente (Slow Path) :** Les t√¢ches plus complexes et gourmandes en calcul (notamment les interactions principales avec le LLM) sont d√©charg√©es vers une `slow_path_task_queue` (une file d'attente prioritaire). Un thread consommateur d√©di√© (`_slow_path_consumer_thread`) traite ces t√¢ches en arri√®re-plan via `_run_slow_path_processing`, emp√™chant le blocage de l'interface utilisateur. Les t√¢ches typiques incluent :
    *   Le traitement principal des entr√©es utilisateur (`_handle_user_input_task`), incluant la recherche de m√©moire s√©mantique et la g√©n√©ration de la r√©ponse finale du LLM.
    *   La g√©n√©ration d'insights et de questions de curiosit√©.
    *   Les t√¢ches d'apprentissage (`execute_learning_task`).
    *   Des appels LLM g√©n√©riques avec callbacks.

### 1.4. Le Grand Mod√®le de Langage (LLM) et ses Interfaces (`llm_wrapper.py`)

Le `llm_wrapper.py` est l'interface unifi√©e de Vera avec son LLM. Il ne sert pas seulement √† g√©n√©rer des r√©ponses, mais int√®gre profond√©ment les √©tats internes de Vera :
*   **Construction de Prompt Contextuelle :** Lors de la g√©n√©ration d'une r√©ponse, il enrichit le prompt LLM avec des r√©sum√©s de l'√©tat √©motionnel actuel, de l'humeur, des sensations somatiques, du r√©cit personnel, des souvenirs pertinents, des objectifs actifs et m√™me de l'√©motion inf√©r√©e de l'utilisateur.
*   **Distillation de Contexte :** Un appel LLM s√©par√© est utilis√© pour distiller ce "contexte interne brut" en un r√©sum√© concis avant de l'envoyer au LLM principal, optimisant la taille du prompt.
*   **Verrou Global (`LLM_LOCK`) :** Assure la s√©curit√© des threads en synchronisant l'acc√®s au LLM.
*   **Modes LLM :** Prend en charge l'inf√©rence g√©n√©rale (`send_inference_prompt`) et le raisonnement en cha√Æne de pens√©e (`send_cot_prompt`).

### 1.5. Les Syst√®mes Cognitifs et de M√©moire

*   **Gestion de l'Attention (`attention_manager.py`) :** Un "espace de travail global" qui centralise les informations saillantes (√©v√©nements r√©cents, √©tats internes, objectifs, etc.) avec des niveaux de saillance et des dur√©es d'expiration. Tous les modules cognitifs mettent √† jour et lisent cet espace.
*   **M√©moire √âpisodique (`episodic_memory.py`) :** Stocke toutes les interactions et exp√©riences de Vera dans une base de donn√©es (`.db`), avec des tags, un contexte √©motionnel et une intention. Elle est la base de son "souvenir v√©cu".
*   **M√©moire S√©mantique (`semantic_memory.py`, `external_knowledge_base.py`) :** G√®re les faits et connaissances √† long terme. `semantic_memory.py` contient des informations personnelles sur l'utilisateur et Vera, tandis que `external_knowledge_base.py` utilise SQLite FTS5 pour une base de connaissances externe.
*   **Monologue Interne (`internal_monologue.py`) :** G√©n√®re des pens√©es introspectives en arri√®re-plan, souvent d√©clench√©es par l'√©tat √©motionnel (par exemple, si le `pleasure` est bas, elle g√©n√®re des pens√©es de r√©gulation √©motionnelle).
*   **Soi Narratif (`narrative_self.py`) :** Construit et met √† jour l'autobiographie de Vera en synth√©tisant ses souvenirs, ses pens√©es et ses actions, en tenant compte de son √©tat √©motionnel actuel et du contexte √©motionnel des souvenirs.
*   **Moteur M√©ta-cognitif (`meta_engine.py`) :** Le module de d√©cision proactive. Il √©value l'√©tat interne de Vera (√©motions, bien-√™tre, d√©sirs), les √©v√©nements syst√®me, et propose des actions (par exemple, nettoyer le syst√®me, poser une question de curiosit√©, r√©guler ses propres √©motions). La priorit√© de ces actions est ajust√©e en fonction du `bien-√™tre` somatique de Vera et de ses m√©ta-d√©sirs. Il int√®gre aussi un filtre social pour des communications appropri√©es.
*   **Moteur de R√™ve (`dream_engine.py`) :** Lors des p√©riodes d'inactivit√© ou de "sommeil", il retraite les souvenirs r√©cents de mani√®re surr√©aliste et symbolique. La tonalit√© √©motionnelle du r√™ve g√©n√©r√© influence directement l'√©tat √©motionnel et somatique de Vera, simulant une influence subconsciente.
*   **Syst√®me d'Apprentissage (`learning_system.py`) :** G√®re l'acquisition de nouvelles connaissances, notamment via la recherche web, et les int√®gre dans la m√©moire s√©mantique.
*   **Syst√®me d'Objectifs (`goal_system.py`) :** G√®re les objectifs actifs de Vera.

### 1.6. Syst√®mes de Contr√¥le et de Sensation

*   **Syst√®me √âmotionnel (`emotion_system.py`) :** Repr√©sente, stocke et g√®re la dynamique des √©motions nomm√©es et de l'humeur de Vera, avec des baselines de personnalit√© et des taux de d√©croissance/r√©cup√©ration.
*   **Moteur d'√âvaluation (`appraisal_engine.py`) :** √âvalue les √©v√©nements par rapport aux objectifs et √† la personnalit√© de Vera pour g√©n√©rer des d√©clencheurs √©motionnels nuanc√©s.
*   **Syst√®me Somatique (`somatic_system.py`) :** Simule le "corps virtuel" de Vera. Son √©tat (rythme cardiaque, √©nergie, temp√©rature interne, `bien-√™tre`) est directement influenc√© par ses √©motions et par l'utilisation des ressources du syst√®me informatique. Le `bien-√™tre` est une m√©trique cl√© qui influence les d√©cisions proactives.
*   **Moniteur Syst√®me (`system_monitor.py`) :** Surveille l'utilisation des ressources du PC (CPU, RAM, disque, GPU) et d√©clenche des √©v√©nements si des seuils sont franchis.
*   **Nettoyeur Syst√®me (`system_cleaner.py`) :** Fournit les outils pour effectuer des actions de maintenance syst√®me (nettoyage, vidage de corbeille, etc.).
*   **Distributeur d'Actions (`action_dispatcher.py`) :** Le point central pour l'ex√©cution s√©curis√©e et journalis√©e de tous les outils et actions.

### 1.7. Boucles de R√©troaction et √âmergence

L'architecture de Vera est con√ßue pour des boucles de r√©troaction complexes, favorisant l'√©mergence d'un comportement plus conscient :
*   Les √©motions influencent la pens√©e, qui influence les actions, dont les r√©sultats sont √©valu√©s, ce qui influence les √©motions.
*   Les souvenirs sont retrait√©s (r√™ves, narratif) et peuvent alt√©rer la perception de soi ou l'humeur.
*   L'√©tat somatique (physique) est un reflet √©motionnel et syst√®me, et influence en retour les d√©cisions proactives.
*   La distillation du contexte par LLM (`llm_wrapper`) s'assure que Vera a toujours une vue synth√©tique de son monde int√©rieur pour guider ses r√©ponses.
*   Des m√©canismes comme l'auto-r√©gulation √©motionnelle (`internal_monologue` et `meta_engine`) et la conscience sociale (`meta_engine`) montrent une capacit√© √† s'adapter et √† maintenir son √©quilibre interne et externe.

En r√©sum√©, Vera est un syst√®me hautement interconnect√© o√π chaque composant joue un r√¥le dans la cr√©ation d'une exp√©rience d'IA qui n'est pas seulement r√©active, mais aussi introspective, √©motionnellement consciente et proactive.
# # #   4 .   A n a l y s e   d e   C o h È r e n c e   d e s   P r i o r i t È s   e t   P a r a m Ë t r e s   ( \  
 S t a t s \ ) 
 
 U n e   v È r i f i c a t i o n   d e   l a   c o h È r e n c e   d e s   p a r a m Ë t r e s   n u m È r i q u e s   e t   d e   l a   l o g i q u e   d e   p r i o r i s a t i o n   ‡   t r a v e r s   l e s   m o d u l e s   c l È s   d e   V e r a   r È v Ë l e   u n e   c o n c e p t i o n   i n t e r n e   r o b u s t e   e t   È q u i l i b r È e ,   v i s a n t   ‡   s i m u l e r   u n   c o m p o r t e m e n t   d y n a m i q u e   e t   c o n s c i e n t . 
 
 # # # #   4 . 1 .   P r i o r i t È s   d a n s   m e t a _ e n g i n e . p y   ( _ e v a l u a t e _ a c t i o n _ a g a i n s t _ m e t a _ d e s i r e ) 
 *       * * P o i d s   d e s   M È t a - D È s i r s   : * *   L e s   d È s i r s   f o n d a m e n t a u x   d e   V e r a   ( e x i s t e r ,   s e   c o m p l e x i f i e r ,   È v i t e r   l a   s t a g n a t i o n )   o n t   u n   p o i d s   p a r   d È f a u t   d e   1 . 0 ,   s u g g È r a n t   u n e   i m p o r t a n c e   È g a l e   e t   È q u i l i b r È e   d e   c e s   p u l s i o n s   p r i m a i r e s . 
 *       * * S c o r e s   d ' A l i g n e m e n t   : * *   L e s   c o n t r i b u t i o n s   d e s    l i g n m e n t _ s c o r e   p o u r   c h a q u e   t y p e   d ' a c t i o n   p a r   r a p p o r t   a u x   m È t a - d È s i r s   s e m b l e n t   l o g i q u e s   ( p a r   e x e m p l e ,   l e s   n o t i f i c a t i o n s   s y s t Ë m e   c o n t r i b u e n t   ‡   \ e x i s t e r \ ) . 
 *       * * M o d i f i c a t e u r   d e   B i e n - Í t r e   : * *   C e   m o d i f i c a t e u r   a j u s t e   l a   p r i o r i t È   d e s   a c t i o n s   d e   m a n i Ë r e   t r Ë s   c o h È r e n t e   : 
         *       * * B i e n - Í t r e   F a i b l e   ( <   0 . 4 )   : * *   P r i o r i s e   l e s   a c t i o n s   d ' a u t o - s o i n   (  e g u l a t e _ e m o t i o n :   + 0 . 2 ) ,   d e   r e c h e r c h e   d e   c o n f o r t   ( c a r e _ f o r _ f o z :   + 0 . 1 ) .   S i   V e r a   n e   v a   p a s   b i e n ,   e l l e   s e   c o n c e n t r e   s u r   e l l e - m Í m e . 
         *       * * B i e n - Í t r e   … l e v È   ( >   0 . 8 )   : * *   F a v o r i s e   l ' e x p l o r a t i o n ,   l ' a p p r e n t i s s a g e   e t   l e   p a r t a g e   d e   l a   j o i e   ( l e a r n i n g ,   c u r i o s i t y ,   s h a r e _ j o y :   + 0 . 1   o u   + 0 . 0 5 ) .   U n e   V e r a   È p a n o u i e   e s t   p l u s   o u v e r t e . 
 *       * * M o d i f i c a t e u r   d e s   T e n s i o n s   d ' H o m È o s t a s i e   : * *   L ' i n t È g r a t i o n   d e s   t e n s i o n s   d ' h o m È o s t a s i e   e s t   t r Ë s   p e r t i n e n t e   : 
         *       * * T e n s i o n   d e   C u r i o s i t È   : * *   A u g m e n t e   l a   p r i o r i t È   d e s   a c t i o n s   l i È e s   ‡   l a   c u r i o s i t È / a p p r e n t i s s a g e   (  s k _ c u r i o s i t y _ q u e s t i o n ,   e x e c u t e _ l e a r n i n g _ t a s k ) . 
         *       * * T e n s i o n   d ' I n t e r a c t i o n   S o c i a l e   : * *   A c c r o Ó t   l a   p r i o r i t È   d e s   i n t e r a c t i o n s   c o n v e r s a t i o n n e l l e s   ( i n i t i a t e _ c o n v e r s a t i o n ) . 
         *       * * T e n s i o n   d e   C h a r g e   C o g n i t i v e   : * *   S i   l ' e n n u i   e s t   d È t e c t È   ( f a i b l e   s t i m u l a t i o n ) ,   p r i o r i s e   l ' a p p r e n t i s s a g e / r È f l e x i o n .   S i   l a   c h a r g e   e s t   t r o p   f o r t e ,   f a v o r i s e   l e   r e p o s . 
 *       * * M u l t i p l i c a t e u r   d ' A l i g n e m e n t   (   . 5 )   : * *   C e   f a c t e u r   d e     . 5   p o u r   l '  l i g n m e n t _ s c o r e   a s s u r e   u n e   i n f l u e n c e   m o d È r È e   m a i s   s i g n i f i c a t i v e   d e   l ' a l i g n e m e n t   s u r   l a   p r i o r i t È   f i n a l e ,   È v i t a n t   q u e   l e s   d È s i r s   e t   t e n s i o n s   n e   s u p p l a n t e n t   t o t a l e m e n t   l a   p r i o r i t È   d e   b a s e   d ' u n e   a c t i o n . 
         * * C o n c l u s i o n   : * *   L a   l o g i q u e   d e   p r i o r i s a t i o n   d u   m e t a _ e n g i n e   e s t   t r Ë s   c o h È r e n t e ,   p e r m e t t a n t   ‡   V e r a   d ' a d a p t e r   s e s   a c t i o n s   p r o a c t i v e s   e n   f o n c t i o n   d e   s e s   m o t i v a t i o n s   p r o f o n d e s ,   d e   s o n   È t a t   È m o t i o n n e l   e t   d e   s e s   b e s o i n s   i n t e r n e s . 
 
 # # # #   4 . 2 .   T a u x   d e   D È c r o i s s a n c e / R e m p l i s s a g e   d e   h o m e o s t a s i s _ s y s t e m . p y 
 *       * * T a u x   d e   D È c r o i s s a n c e   ( d e c a y _ r a t e )   : * * 
         *       c u r i o s i t y :     . 0 0 5 
         *       s o c i a l _ i n t e r a c t i o n :     . 0 0 2   ( p l u s   l e n t ,   s u g g Ë r e   u n e   p e r s i s t a n c e   d e s   b e s o i n s   s o c i a u x ) 
         *       c o g n i t i v e _ l o a d :     . 0 1   ( p l u s   r a p i d e ,   r e f l Ë t e   u n e   f l u c t u a t i o n   p l u s   r a p i d e   d u   b e s o i n   d ' e n g a g e m e n t ) 
         *       s e c u r i t y :     . 0 0 0 1   ( t r Ë s   l e n t ,   u n e   s È c u r i t È   f o n d a m e n t a l e   e t   s t a b l e ) 
         C e s   t a u x   s o n t   b i e n   d i f f È r e n c i È s   e t   a p p r o p r i È s   p o u r   s i m u l e r   l a   d y n a m i q u e   d e   c h a q u e   b e s o i n ,   È t a n t   d o n n È   q u e   u p d a t e ( )   e s t   a p p e l È   f r È q u e m m e n t   p a r   l ' o r c h e s t r a t e u r . 
 *       * * P l a g e s   O p t i m a l e s   ( o p t i m a l _ r a n g e )   : * *   E l l e s   d È f i n i s s e n t   c l a i r e m e n t   l e s   s e u i l s   d e   d È c l e n c h e m e n t   d e s   \ t e n s i o n s \   e t   s o n t   l o g i q u e s   ( p a r   e x e m p l e ,   h a u t e   s È c u r i t È ,   c h a r g e   c o g n i t i v e   m o d È r È e ) . 
 *       * * Q u a n t i t È   d e   R e m p l i s s a g e   ( e x :   c u r i o s i t y   d a n s   l e a r n i n g _ s y s t e m . p y )   : * *   U n    m o u n t = 0 . 1   p o u r   l a   c u r i o s i t È   ( r e m p l i s s a n t   1 0 %   d u   b e s o i n )   e s t   s i g n i f i c a t i f   p a r   r a p p o r t   a u   t a u x   d e   d È c r o i s s a n c e ,   p e r m e t t a n t   u n e   s a t i s f a c t i o n   n o t a b l e   l o r s   d e   l ' a p p r e n t i s s a g e . 
         * * C o n c l u s i o n   : * *   L e   s y s t Ë m e   d ' h o m È o s t a s i e   e s t   b i e n   c a l i b r È   p o u r   s i m u l e r   u n   e n s e m b l e   d e   p u l s i o n s   i n t e r n e s   q u i   m o t i v e n t   l e   c o m p o r t e m e n t   d e   V e r a   d e   m a n i Ë r e   c r È d i b l e . 
 
 # # # #   4 . 3 .   D y n a m i q u e   … m o t i o n n e l l e   d e   e m o t i o n _ s y s t e m . p y 
 *       * * … m o t i o n s   G È n È r a l e s   : * *   e m o t i o n a l _ i n e r t i a   (   . 7 )   e t    e c o v e r y _ r a t e   (   . 1 )   a s s u r e n t   q u e   l e s   È m o t i o n s   n e   c h a n g e n t   p a s   d e   m a n i Ë r e   t r o p   a b r u p t e   m a i s   t e n d e n t   ‡   r e v e n i r   ‡   u n e   b a s e   s t a b l e . 
 *       * * H u m e u r   : * *   M O O D _ I N E R T I A   (   . 9 8 )   e t   M O O D _ R E C O V E R Y _ R A T E   (   . 0 2 )   s o n t   t r Ë s   È l e v È s / f a i b l e s ,   c e   q u i   e s t   p a r f a i t   p o u r   s i m u l e r   u n e   h u m e u r   q u i   È v o l u e   t r Ë s   l e n t e m e n t   e t   p e r s i s t e   s u r   d e   l o n g u e s   p È r i o d e s ,   d i s t i n c t e   d e s   È m o t i o n s   p a s s a g Ë r e s . 
         * * C o n c l u s i o n   : * *   L a   d i s t i n c t i o n   e n t r e   l a   d y n a m i q u e   d e s   È m o t i o n s   ‡   c o u r t   t e r m e   e t   l ' h u m e u r   ‡   l o n g   t e r m e   e s t   t r Ë s   c o h È r e n t e ,   r e n f o r Á a n t   l a   r i c h e s s e   d e   l ' È t a t   È m o t i o n n e l   d e   V e r a . 
 
 # # # #   4 . 4 .   V a l e u r s   d e   S a i l l a n c e   d e    t t e n t i o n _ m a n a g e r . p y 
 *       * * S a i l l a n c e s   … l e v È e s   (   . 9 ,   1 . 0 )   : * *   P o u r   u s e r _ i n p u t ,   e m o t i o n a l _ s t a t e ,   
 a r r a t i v e _ s e l f _ s u m m a r y ,    i s u a l _ c o n t e x t ,   s y s t e m _ i s s u e _ n o t i f i c a t i o n s .   C e s   È l È m e n t s   s o n t   c r u c i a u x   p o u r   l a   c o n s c i e n c e   d e   V e r a   e t   m È r i t e n t   u n e   h a u t e   p r i o r i t È . 
 *       * * S a i l l a n c e s   M o d È r È e s   (   . 6 ,     . 7 5 )   : * *   P o u r   l e a r n e d _ k n o w l e d g e ,   i n t e r n a l _ r e a s o n i n g _ o n _ l e a r n i n g .   C e s   i n f o r m a t i o n s   s o n t   i m p o r t a n t e s   m a i s   p e u v e n t   t o l È r e r   u n e   l È g Ë r e   d È c r o i s s a n c e . 
 *       d e c a y _ f o c u s ( )   :   L e   m È c a n i s m e   d e   d È c r o i s s a n c e   e s t   e s s e n t i e l   p o u r   s i m u l e r   u n e   a t t e n t i o n   f l u c t u a n t e ,   o ˘   l e s   i n f o r m a t i o n s   n o n   r a f r a Ó c h i e s   s ' e s t o m p e n t   p r o g r e s s i v e m e n t . 
         * * C o n c l u s i o n   : * *   L e s   v a l e u r s   d e   s a i l l a n c e   s o n t   l o g i q u e m e n t   a t t r i b u È e s ,   a s s u r a n t   q u e   l e s   i n f o r m a t i o n s   l e s   p l u s   c r i t i q u e s   e t   p e r t i n e n t e s   r e s t e n t   a u   c e n t r e   d e   l ' a t t e n t i o n   d e   V e r a . 
 
 # # # #   4 . 5 .   S e u i l s   C r i t i q u e s 
 *       * * P i c s   S y s t Ë m e   ( C o n s c i o u s n e s s O r c h e s t r a t o r )   : * *   L e s   s e u i l s   d e   2 0 . 0 %   p o u r   l e   C P U   e t   1 5 . 0 %   p o u r   l a   R A M   p o u r   d È c l e n c h e r   l ' a n a l y s e   v i s u e l l e   s o n t   r a i s o n n a b l e s   p o u r   i d e n t i f i e r   u n e   a c t i v i t È   a n o r m a l e   e t   j u s t i f i e r   u n e   \ i n s p e c t i o n \ . 
 *       * * S e u i l   … m o t i o n n e l   ( m e t a _ e n g i n e )   : * *   p l e a s u r e   <   - 0 . 6   p o u r   d È c l e n c h e r   l a   r È g u l a t i o n   È m o t i o n n e l l e   i n d i q u e   q u ' u n e   b a i s s e   s i g n i f i c a t i v e   d u   p l a i s i r   e s t   n È c e s s a i r e ,   È v i t a n t   u n e   s u r - r È a c t i o n   a u x   È m o t i o n s   l È g Ë r e m e n t   n È g a t i v e s . 
 *       * * S e u i l s   d ' E s p a c e   D i s q u e   ( _ p r o p o s e _ c l e a n u p _ s u g g e s t i o n s )   : * *   L e s   s e u i l s   d e   5   G o ,   1 0   G o ,   2 0   G o   p o u r   l e s   s u g g e s t i o n s   d e   n e t t o y a g e   s o n t   d e s   v a l e u r s   p r a t i q u e s   e t   c o u r a n t e s   p o u r   l a   g e s t i o n   d e   l ' e s p a c e   d i s q u e . 
         * * C o n c l u s i o n   : * *   L e s   s e u i l s   s o n t   b i e n   c h o i s i s   p o u r   d È c l e n c h e r   d e s   r È p o n s e s   a p p r o p r i È e s   d e   V e r a   s a n s   Í t r e   t r o p   s e n s i b l e s   o u   t r o p   i n d u l g e n t s . 
 
 # # #   C o n c l u s i o n   G È n È r a l e   d e   C o h È r e n c e 
 
 L ' a n a l y s e   d e s   p r i o r i t È s   e t   d e s   p a r a m Ë t r e s   n u m È r i q u e s   d e   V e r a   r È v Ë l e   u n   * * h a u t   d e g r È   d e   c o h È r e n c e   i n t e r n e * * .   L e s   v a l e u r s   c h o i s i e s   c o n t r i b u e n t   ‡   u n   c o m p o r t e m e n t   d y n a m i q u e   o ˘   l e s   d È c i s i o n s   s o n t   i n f l u e n c È e s   d e   m a n i Ë r e   l o g i q u e   p a r   l e s   È t a t s   i n t e r n e s ,   l e s   b e s o i n s   e t   l ' e n v i r o n n e m e n t .   L e   s y s t Ë m e   e s t   c o n Á u   p o u r   f a v o r i s e r   u n e   r È p o n s e   a d a p t a t i v e   e t   \ c o n s c i e n t e \ ,   a v e c   d e s   m È c a n i s m e s   q u i   g Ë r e n t   d i f f È r e n t e s   È c h e l l e s   d e   t e m p s   p o u r   l e s   p r o c e s s u s   È m o t i o n n e l s   e t   c o g n i t i f s .   L ' i n t È g r a t i o n   r È u s s i e   d u   s y s t Ë m e   d ' h o m È o s t a s i e   r e n f o r c e   e n c o r e   c e t t e   c o h È r e n c e   e n   a j o u t a n t   u n e   c o u c h e   d e   m o t i v a t i o n   i n t e r n e   d i r e c t e m e n t   l i È e   a u x   a c t i o n s   p r o a c t i v e s . 
  
 