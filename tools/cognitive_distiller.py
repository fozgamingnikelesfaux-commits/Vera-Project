"""
Cognitive Distiller
Ce module analyse le journal des décisions du LLM (`logs/decisions.jsonl`)
pour en extraire des règles heuristiques simples.
"""
import json
from collections import defaultdict

def analyze_decisions(log_file="logs/decisions.jsonl"):
    """
    Analyse le fichier de log des décisions et tente d'en extraire des règles.
    """
    print("Démarrage de l'analyse du journal des décisions...")
    
    patterns = defaultdict(list)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line)
                    thought = log_entry.get("input_context", {}).get("thought", "")
                    decision = log_entry.get("llm_decision", {})
                    
                    if thought and decision:
                        # Pour l'instant, une logique de pattern très simple :
                        # On groupe les décisions par leur résultat.
                        decision_key = (decision.get("categorie"), decision.get("valeur"))
                        patterns[decision_key].append(thought)
                        
                except json.JSONDecodeError:
                    print(f"Erreur de décodage JSON pour la ligne : {line.strip()}")
                    continue
    except FileNotFoundError:
        print(f"Le fichier de log '{log_file}' n'a pas été trouvé.")
        return

    print(f"Analyse terminée. {len(patterns)} schémas de décision uniques trouvés.")
    
    # Afficher les schémas trouvés pour le débogage
    for (categorie, valeur), thoughts in patterns.items():
        if len(thoughts) > 1: # On ne s'intéresse qu'aux décisions récurrentes
            print(f"\n--- Schéma Récurrent Détecté ---")
            print(f"Décision: Catégorie='{categorie}', Valeur='{valeur}'")
            print(f"Déclenché {len(thoughts)} fois par des pensées comme :")
            for t in thoughts[:2]: # Montrer les 2 premiers exemples
                print(f"  - '{t[:80]}...'")

    # La prochaine étape sera de générer et sauvegarder les règles distillées.
    generate_and_save_rules(patterns)

def find_common_keywords(thoughts: list) -> list:
    """
    Trouve les mots-clés communs (simpliste) dans une liste de pensées.
    """
    if not thoughts:
        return []
    
    # Nettoyer, tokeniser et trouver les mots communs
    sets_of_words = []
    for thought in thoughts:
        # Enlever la ponctuation simple et mettre en minuscule
        cleaned_thought = thought.replace("*", "").replace("?", "").lower()
        sets_of_words.append(set(cleaned_thought.split()))
        
    if not sets_of_words:
        return []
        
    # Trouver l'intersection de tous les sets
    common_words = set.intersection(*sets_of_words)
    
    # Exclure les mots très communs (stop words)
    stop_words = {'ma', 'pensée', 'est', 'le', 'la', 'les', 'un', 'une', 'de', 'des', 'et', 'en', 'pour', 'que', 'qui', 'sur', 'avec', 'ce', 'ça', 'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles'}
    
    return list(common_words - stop_words)

def generate_and_save_rules(patterns: defaultdict, output_file="data/distilled_rules.json"):
    """
    Génère des règles à partir des schémas et les sauvegarde.
    """
    rules = []
    print("\nGénération des règles distillées...")

    for (categorie, valeur), thoughts in patterns.items():
        if len(thoughts) < 2: # Seuil de confiance minimal
            continue

        common_keywords = find_common_keywords(thoughts)
        
        if not common_keywords:
            continue # Pas de mots-clés communs trouvés, on ne peut pas créer de règle fiable

        # Calcul de confiance simple
        confidence = 1.0 - (1.0 / (len(thoughts)))

        rule = {
            "trigger": {
                "type": "thought_contains_all_keywords",
                "value": common_keywords
            },
            "decision": {
                "categorie": categorie,
                "valeur": valeur
            },
            "confidence": round(confidence, 2),
            "source_log_count": len(thoughts)
        }
        rules.append(rule)
        print(f"  - Règle créée pour la décision '{categorie}':'{valeur}' basée sur les mots-clés: {common_keywords}")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=4, ensure_ascii=False)
        print(f"\n{len(rules)} règles distillées ont été sauvegardées dans '{output_file}'.")
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des règles : {e}")

if __name__ == "__main__":
    analyze_decisions()
