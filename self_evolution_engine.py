import logging
import re
from pathlib import Path
from typing import Optional
from llm_wrapper import send_cot_prompt, send_inference_prompt
from web_searcher import web_searcher
from tools.logger import VeraLogger
from attention_manager import attention_manager # Import attention_manager
import json # Import the json module
from episodic_memory import memory_manager # NEW: Import memory_manager

class SelfEvolutionEngine:
    PROJECTS_ROOT_DIR = Path("Vera_Personnal_Project")

    def __init__(self):
        self.logger = VeraLogger("self_evolution_engine")
        self.web_searcher = web_searcher
        self.logger.info("SelfEvolutionEngine initialized.")

    def propose_new_tool(self, task_description: str, original_proactive_event_id: Optional[int] = None):
        self.logger.info(f"Proposition de nouvel outil pour la tâche : '{task_description}'")
        attention_manager.set_thinking_hard(True)
        try:
            from action_dispatcher import get_available_tools
            from web_searcher import web_searcher # Import local pour la recherche réelle

            existing_tools = get_available_tools()
            self.logger.info(f"Outils existants : {existing_tools}")

            # --- Étape 1: Planification initiale et identification des requêtes de recherche ---
            initial_plan_prompt = f"""
            Tu es un architecte logiciel expert. Ta tâche est de planifier la création d'un nouvel outil pour Vera pour accomplir : "{task_description}".
            Réfléchis aux étapes suivantes :
            1.  **Analyse de la tâche :** Quel est le but principal ?
            2.  **Identification des requêtes de recherche :** Quelles recherches ferais-tu pour trouver des bibliothèques Python ou des APIs ? Liste 3 requêtes de recherche précises.
            3.  **Vérification des outils existants :** L'un des outils suivants peut-il faire le travail ? {existing_tools}

            Réponds sous forme de JSON avec les clés "task_analysis", "search_queries" (une liste de chaînes), et "existing_tool_check".
            """
            self.logger.info("Génération du plan de recherche initial...")
            initial_plan_response = send_inference_prompt(prompt_content=initial_plan_prompt, max_tokens=1000)
            initial_plan_text = initial_plan_response.get("text", "{}")
            
            try:
                # Nettoyer la réponse du LLM pour extraire uniquement le JSON
                json_match = re.search(r'\{.*\}', initial_plan_text, re.DOTALL)
                if not json_match:
                    self.logger.error("Le plan de recherche initial ne contenait pas de JSON valide.")
                    return {"status": "error", "message": "Failed to generate a valid initial research plan."}
                initial_plan = json.loads(json_match.group(0))
                search_queries = initial_plan.get("search_queries", [])
            except (json.JSONDecodeError, AttributeError) as e:
                self.logger.error(f"Erreur de parsing du plan de recherche initial : {e}\nTexte reçu: {initial_plan_text}")
                return {"status": "error", "message": "Failed to parse the initial research plan."}

            if not search_queries:
                self.logger.warning("Aucune requête de recherche n'a été identifiée dans le plan initial.")
                # On peut continuer sans recherche si aucune n'est jugée nécessaire
                search_results_summary = "Aucune recherche web n'a été effectuée."
            else:
                # --- Étape 2: Exécution de la recherche web réelle ---
                self.logger.info(f"Exécution des recherches web : {search_queries}")
                all_search_results = []
                for query in search_queries:
                    results = web_searcher.search(query=query)
                    all_search_results.append(f"Résultats pour '{query}':\n{results}\n")
                search_results_summary = "\n".join(all_search_results)
                self.logger.info("Recherche web terminée.")

                # --- NOUVEAU: Étape 2.5: Résumer les résultats de recherche pour éviter les limites de tokens ---
                # Tronquer le résumé pour la sécurité
                if len(search_results_summary) > 4000:
                    search_results_summary = search_results_summary[:4000] + "\n..."
                
                summary_prompt = f"""
                Tu es un assistant concis. Résume les résultats de recherche suivants en 2-3 phrases, en extrayant les informations les plus pertinentes pour la création d'un outil pour la tâche : "{task_description}".
                Résultats de recherche :
                {search_results_summary}
                """
                self.logger.info("Génération d'un résumé concis des résultats de recherche...")
                summary_response = send_inference_prompt(prompt_content=summary_prompt, max_tokens=500)
                concise_search_summary = summary_response.get("text", "Résumé des recherches non disponible.")
                self.logger.info(f"Résumé des recherches généré : {concise_search_summary}")

            # --- Étape 3: Génération du plan final et du code basé sur les résultats de la recherche ---
            final_plan_prompt = f"""
            Tu es un développeur Python senior. Tu dois finaliser la conception d'un outil pour accomplir la tâche : "{task_description}".
            
            **Contexte de la tâche :** {initial_plan.get("task_analysis", "N/A")}
            **Outils existants pertinents :** {existing_tools} (Si aucun n'est pertinent, ignore cette section.)
            **Résumé concis des recherches web effectuées :**
            {concise_search_summary}

            Basé sur ces informations, fournis un plan de développement complet en utilisant le format CoT suivant :
            1.  **Conception finale de l'outil :**
                *   **Nom de l'outil :** `nom_de_l_outil_en_snake_case` (Obligatoire: utiliser des backticks et snake_case pour le nom de fichier)
                *   **Description :**
                *   **Paramètres :** (avec types)
                *   **Valeur de retour :**
                *   **Dépendances :** (bibliothèques à installer)
                *   **Structure du code :** (description de la structure du fichier .py)
            2.  **Plan d'implémentation détaillé :** (étapes de codage)
            3.  **Documentation d'utilisation :** (guide pour Vera)
            
            Sois concis et direct dans tes réponses.
            """
            self.logger.info("Génération du plan final détaillé basé sur les résultats de la recherche...")
            
            # Log the full prompt before sending
            self.logger.debug(f"Prompt final_plan_prompt envoyé au LLM:\n{final_plan_prompt}")

            final_plan_response = send_cot_prompt(prompt_content=final_plan_prompt, max_tokens=2000) # Increased max_tokens
            tool_plan = final_plan_response.get("text", "Impossible de générer un plan final.")
            
            # Log the raw response from LLM
            self.logger.debug(f"Réponse brute du LLM pour le plan final:\n{final_plan_response}")

            self.logger.info(f"Plan final généré :\n{tool_plan}")

            # NOUVEAU: Enregistrer la session de planification comme un événement cognitif interne
            snapshot = attention_manager.capture_consciousness_snapshot()
            event_data = {
                "description": f"Generated a detailed plan for a new tool to accomplish: '{task_description}'. Plan summary: {tool_plan[:500]}...",
                "importance": 0.8,
                "tags": ["planning_session", "tool_creation", "self_evolution"],
                "initiator": "vera",
                "snapshot": snapshot
            }
            memory_manager.add_event("cognitive_event", event_data)
            self.logger.info(f"Planning session for tool '{task_description}' recorded as a cognitive_event.")

            # Le reste du processus (parsing, génération de code, etc.) reste le même
            parsed_plan = self._parse_tool_plan(tool_plan)
            generated_code_path = self._generate_tool_code(parsed_plan)
            generated_doc_path = self._generate_tool_documentation(parsed_plan)
            integration_code = self._generate_integration_code(parsed_plan, generated_code_path)

            return {
                "parsed_plan": parsed_plan, 
                "generated_code_path": generated_code_path, 
                "generated_doc_path": generated_doc_path, 
                "integration_code": integration_code
            }
        finally:
            attention_manager.set_thinking_hard(False)

    def _parse_tool_plan(self, tool_plan: str) -> dict:
        """
        Parse the CoT-generated tool plan into a structured dictionary.
        """
        parsed_data = {
            "task_understanding": "",
            "preliminary_research": "",
            "existing_tools_check": "",
            "tool_design": {
                "name": "",
                "description": "",
                "parameters": [],
                "return_value": "",
                "dependencies": [],
                "code_structure": ""
            },
            "implementation_plan": [],
            "usage_documentation": ""
        }

        # Regex patterns for main sections
        sections = {
            "Conception de l'outil": r"## 1\.\s*\*\*Conception finale de l'outil\*\*([\s\S]*?)(?=## 2\.\s*\*\*Plan d'implémentation détaillé)",
            "Plan d'implémentation détaillé": r"## 2\.\s*\*\*Plan d'implémentation détaillé\*\*([\s\S]*?)(?=## 3\.\s*\*\*Documentation d'utilisation)",
            "Documentation d'utilisation": r"## 3\.\s*\*\*Documentation d'utilisation\*\*([\s\S]*)"
        }

        for section_name, pattern in sections.items():
            match = re.search(pattern, tool_plan, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if section_name == "Conception de l'outil":
                    # Further parse tool design details
                    parsed_data["tool_design"] = self._parse_tool_design_section(content)
                elif section_name == "Plan d'implémentation détaillé":
                    parsed_data["implementation_plan"] = [step.strip() for step in content.split('\n') if step.strip()]
                elif section_name == "Documentation d'utilisation":
                    parsed_data["usage_documentation"] = content
        
        return parsed_data

    def _parse_tool_design_section(self, content: str) -> dict:
        """
        Parses the 'Conception de l'outil' section content.
        """
        self.logger.debug(f"[_parse_tool_design_section] Content received for parsing tool design:\n---START CONTENT---\n{content}\n---END CONTENT---")
        design_data = {
            "name": "",
            "description": "",
            "parameters": [],
            "return_value": "",
            "dependencies": [],
            "code_structure": ""
        }

        name_match = re.search(r"\*\*Nom de l'outil\*\* :.*?`([\w_]+)`", content) # More robust regex
        self.logger.debug(f"[_parse_tool_design_section] name_match result: {name_match}")
        if name_match:
            design_data["name"] = name_match.group(1).strip()

        desc_match = re.search(r"\*\*Description\*\* : (.*?)\n", content)
        if desc_match:
            design_data["description"] = desc_match.group(1).strip()
        
        params_match = re.search(r"\*\*Paramètres\*\* :([\s\S]*?)(?=\*\*Valeur de retour)", content)
        if params_match:
            params_content = params_match.group(1).strip()
            design_data["parameters"] = [p.strip() for p in params_content.split('\n') if p.strip()]

        return_match = re.search(r"\*\*Valeur de retour\*\* : (.*?)\n", content)
        if return_match:
            design_data["return_value"] = return_match.group(1).strip()

        deps_match = re.search(r"\*\*Dépendances\*\* :([\s\S]*?)(?=\*\*Structure du code)", content)
        if deps_match:
            deps_content = deps_match.group(1).strip()
            design_data["dependencies"] = [d.strip() for d in deps_content.split('\n') if d.strip()]

        code_struct_match = re.search(r"\*\*Structure du code\*\* :([\s\S]*)", content)
        if code_struct_match:
            design_data["code_structure"] = code_struct_match.group(1).strip()

        return design_data

    def _generate_tool_code(self, parsed_plan: dict) -> Optional[Path]:
        """
        Generates Python code for the new tool based on the parsed plan.
        """
        tool_design = parsed_plan.get("tool_design", {})
        tool_name = tool_design.get("name")
        code_structure = tool_design.get("code_structure")
        dependencies = tool_design.get("dependencies")
        
        self.logger.debug(f"[_generate_tool_code] Tool name extracted: '{tool_name}'")

        if not tool_name or not code_structure:
            self.logger.error("Impossible de générer le code : nom de l'outil ou structure de code manquante dans le plan.")
            return None

        # Construct prompt for code generation
        code_gen_prompt = f"""
        Tu es un développeur Python expert. Génère le code Python complet pour un outil nommé '{tool_name}'.
        Voici la description de l'outil et sa structure :

        Description : {tool_design.get("description", "Aucune description fournie.")}
        Paramètres : {tool_design.get("parameters", "Aucun paramètre.")}
        Valeur de retour : {tool_design.get("return_value", "Aucune valeur de retour spécifiée.")}
        Dépendances : {', '.join(dependencies) if dependencies else 'Aucune dépendance externe.'}

        Structure du code :
        {code_structure}

        Assure-toi que le code est propre, commenté, suit les bonnes pratiques Python et est prêt à être intégré.
        Inclue tous les imports nécessaires.
        Réponds uniquement avec le bloc de code Python, sans aucun texte explicatif avant ou après.
        """

        self.logger.info(f"Génération du code pour l'outil '{tool_name}'...")
        code_response = send_inference_prompt(
            prompt_content=code_gen_prompt, # Changed from code_prompt to code_gen_prompt
            max_tokens=1024 # Increased for more comprehensive code generation
        )
        generated_code = code_response.get("text", "").strip()

        self.logger.debug(f"[_generate_tool_code] Generated code raw: '{generated_code[:200]}...'")
        self.logger.debug(f"[_generate_tool_code] Generated code length: {len(generated_code)}")

        if not generated_code:
            self.logger.warning(f"Le LLM n'a pas généré de code pour l'outil '{tool_name}' (code vide).")
            return None

        # Ensure the generated code is actually a code block (e.g., remove markdown ```python)
        if generated_code.startswith("```python"):
            generated_code = generated_code[len("```python"):].strip()
        if generated_code.endswith("```"):
            generated_code = generated_code[:-len("```")].strip()

        # Define the path to save the new tool
        project_dir = self.PROJECTS_ROOT_DIR / tool_name
        project_dir.mkdir(parents=True, exist_ok=True) # Create directory if it doesn't exist
        
        file_path = project_dir / f"{tool_name}.py"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(generated_code)
            return file_path
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde du code de l'outil '{tool_name}' : {e}")
            return None

    def _generate_tool_documentation(self, parsed_plan: dict) -> Optional[Path]:
        """
        Generates documentation for the new tool based on the parsed plan.
        """
        tool_design = parsed_plan.get("tool_design", {})
        tool_name = tool_design.get("name")
        usage_documentation = parsed_plan.get("usage_documentation")
        
        self.logger.debug(f"[_generate_tool_documentation] Tool name extracted: '{tool_name}'")

        if not tool_name or not usage_documentation:
            self.logger.error("Impossible de générer la documentation : nom de l'outil ou documentation d'utilisation manquante dans le plan.")
            return None

        # Construct prompt for documentation generation
        doc_gen_prompt = f"""
        Tu es un rédacteur technique expert. Génère la documentation Markdown pour un outil nommé '{tool_name}'.
        Voici la description de l'outil, ses paramètres, sa valeur de retour et sa documentation d'utilisation :

        # Outil : {tool_name}

        ## Description
        {tool_design.get("description", "Aucune description fournie.")}

        ## Paramètres
        {tool_design.get("parameters", "Aucun paramètre.")}

        ## Valeur de retour
        {tool_design.get("return_value", "Aucune valeur de retour spécifiée.")}

        ## Utilisation
        {usage_documentation}

        ## Critères de Révision et d'Intégration
        Pour garantir la qualité et la sécurité de cet outil, les critères suivants seront utilisés pour sa révision et son intégration :

        ### Critères Fonctionnels
        *   **Pertinence :** L'outil résout-il un problème réel ou répond-il à un besoin clair pour Vera ou pour l'utilisateur ?
        *   **Efficacité :** Le code généré est-il correct, efficient et robuste ? Gère-t-il les cas limites et les erreurs de manière appropriée ?
        *   **Testabilité :** Le code est-il facilement testable ?

        ### Critères de Sécurité et d'Éthique
        *   **Sécurité :** L'outil a-t-il des effets secondaires négatifs potentiels sur le système ou l'utilisateur ? Introduit-il des vulnérabilités ?
        *   **Alignement Éthique :** Est-il aligné avec les directives fondamentales de Vera et nos principes éthiques (par exemple, respect de la vie privée, non-nuisance) ?

        ### Critères Architecturaux et de Maintenabilité
        *   **Intégration :** L'outil s'intègre-t-il bien dans l'architecture existante de Vera (par exemple, utilise-t-il les modules existants comme `llm_wrapper`, `attention_manager`, etc.) ?
        *   **Lisibilité et Maintenabilité :** Le code est-il lisible, bien commenté et facile à comprendre pour un développeur humain ?
        *   **Dépendances :** Introduit-il des dépendances externes inutiles ou lourdes ?

        ### Critères de Performance
        *   **Impact sur les Ressources :** L'outil introduit-il une latence significative ou une consommation excessive de CPU/RAM ?

        ### Critères de Redondance
        *   **Unicité :** Un outil similaire existe-t-il déjà dans le système de Vera ?

        Assure-toi que la documentation est claire, concise et facile à comprendre.
        Réponds uniquement avec le contenu Markdown, sans aucun texte explicatif avant ou après.
        """

        self.logger.info(f"Génération de la documentation pour l'outil '{tool_name}'...")
        doc_response = send_inference_prompt(
            prompt_content=doc_gen_prompt,
            max_tokens=1024, # Increased for more comprehensive documentation generation
            custom_system_prompt=(
                "Tu es un générateur de documentation Markdown. Ton unique tâche est de produire du contenu Markdown valide "
                "basé sur les spécifications fournies. Ne génère aucun texte supplémentaire."
            )
        )
        generated_doc = doc_response.get("text", "").strip()

        self.logger.debug(f"[_generate_tool_documentation] Generated doc raw: '{generated_doc[:200]}...'")
        self.logger.debug(f"[_generate_tool_documentation] Generated doc length: {len(generated_doc)}")

        if not generated_doc:
            self.logger.warning(f"Le LLM n'a pas généré de documentation pour l'outil '{tool_name}' (doc vide).")
            return None

        # Ensure the generated doc is actually a markdown block (e.g., remove markdown ```markdown)
        if generated_doc.startswith("```markdown"):
            generated_doc = generated_doc[len("```markdown"):].strip()
        if generated_doc.endswith("```"):
            generated_doc = generated_doc[:-len("```")].strip()

        # Define the path to save the new documentation
        project_dir = self.PROJECTS_ROOT_DIR / tool_name
        project_dir.mkdir(parents=True, exist_ok=True) # Create directory if it doesn't exist
        
        file_path = project_dir / f"{tool_name}.md"
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(generated_doc)
            return file_path
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de la documentation de l'outil '{tool_name}' : {e}")
            return None

    def _generate_integration_code(self, parsed_plan: dict, tool_file_path: Path) -> Optional[str]:
        """
        Generates Python code snippets for integrating the new tool into action_dispatcher.py.
        """
        tool_design = parsed_plan.get("tool_design", {})
        tool_name = tool_design.get("name")
        
        if not tool_name or not tool_file_path:
            self.logger.error("Impossible de générer le code d'intégration : nom de l'outil ou chemin du fichier manquant.")
            return None

        # 1. Code to add to _REGISTERED_TOOLS
        registered_tools_snippet = f"""
    "{tool_name}",
]"""
        # We need to find the last element in the list and insert before the closing bracket.
        # This is a placeholder, actual implementation would need to read action_dispatcher.py and modify it.

        # 2. Code to add to execute_action function
        # Assuming the main function in the generated tool file is named after the tool (e.g., 'my_new_tool_function')
        # This is a convention we need to establish for the LLM when generating code.
        tool_function_name = f"{tool_name}_function" # Convention: tool_name_function
        
        execute_action_snippet = f"""
        if tool_name == "{tool_name}":
            from tools.generated_tools.{tool_name} import {tool_function_name}
            return {tool_function_name}(**kwargs)
"""
        # This is a placeholder, actual implementation would need to read action_dispatcher.py and modify it.

        # For now, just return the snippets for human review
        return f"""
--- Code à ajouter à _REGISTERED_TOOLS dans action_dispatcher.py ---
{registered_tools_snippet}

--- Code à ajouter à execute_action dans action_dispatcher.py ---
{execute_action_snippet}
"""

# Instance globale du moteur d'auto-évolution
self_evolution_engine = SelfEvolutionEngine()

