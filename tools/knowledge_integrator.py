import sys
import os
import json
import textwrap

# Add project root to the Python path to allow imports from other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from external_knowledge_base import external_knowledge_base
from filelock import FileLock

UNVERIFIED_FILE = "data/unverified_knowledge.json"
LOCK_FILE = "data/unverified_knowledge.json.lock"

def review_and_integrate():
    """
    Script interactif pour valider les connaissances en quarantaine et les intégrer
    à la base de données principale.
    """
    lock = FileLock(LOCK_FILE, timeout=10)

    try:
        with lock:
            if not os.path.exists(UNVERIFIED_FILE) or os.path.getsize(UNVERIFIED_FILE) == 0:
                print("Le fichier de connaissances en quarantaine est vide. Aucune action requise.")
                return

            with open(UNVERIFIED_FILE, 'r', encoding='utf-8') as f:
                unverified_knowledge = json.load(f)

            if not unverified_knowledge:
                print("Le fichier de connaissances en quarantaine ne contient aucune entrée valide. Aucune action requise.")
                return

            print(f"Début de la validation de {len(unverified_knowledge)} nouvelle(s) connaissance(s).")
            print("Pour chaque entrée, tapez 'o' (oui) pour approuver, 'n' (non) pour rejeter, ou 'q' pour quitter.")
            
            remaining_knowledge = []
            
            for i, concept in enumerate(unverified_knowledge):
                print("\n" + "="*80)
                print(f"Connaissance {i+1}/{len(unverified_knowledge)}")
                print(f"  Sujet  : {concept.get('topic')}")
                print(f"  Titre  : {concept.get('title')}")
                print(f"  Source : {concept.get('source')}")
                print("-" * 80)
                print("  Résumé :")
                # Wrap the summary text for better readability
                summary = concept.get('summary', 'Aucun résumé.')
                wrapped_summary = textwrap.fill(summary, width=78, initial_indent='  ', subsequent_indent='  ')
                print(wrapped_summary)
                print("="*80)
                
                while True:
                    choice = input("Approuver cette connaissance ? (o/n/q) > ").lower()
                    if choice in ['o', 'n', 'q']:
                        break
                    print("Entrée invalide. Veuillez choisir 'o', 'n', ou 'q'.")

                if choice == 'q':
                    print("Validation interrompue. Les connaissances restantes seront conservées pour la prochaine fois.")
                    # Garder les connaissances non traitées
                    remaining_knowledge.extend(unverified_knowledge[i:])
                    break
                
                if choice == 'o':
                    print("Approbation... Intégration à la base de données principale.")
                    # Le texte à insérer combine le titre et le résumé pour une recherche FTS plus riche
                    text_to_insert = f"Titre: {concept.get('title', '')}. Résumé: {concept.get('summary', '')}"
                    
                    success = external_knowledge_base.add_entry(
                        text=text_to_insert,
                        source=concept.get('source', 'Unknown'),
                        metadata={
                            "topic": concept.get('topic'),
                            "original_title": concept.get('title'),
                            "learned_at": concept.get('learned_at')
                        }
                    )
                    if success:
                        print("Intégration réussie.")
                    else:
                        print("ERREUR: L'intégration a échoué. Cette connaissance sera conservée pour une nouvelle tentative.")
                        remaining_knowledge.append(concept) # Garder en cas d'échec
                
                elif choice == 'n':
                    print("Rejeté. Cette connaissance sera supprimée.")

            # Réécrire le fichier de quarantaine avec les connaissances restantes (celles non traitées ou en erreur)
            with open(UNVERIFIED_FILE, 'w', encoding='utf-8') as f:
                json.dump(remaining_knowledge, f, indent=2, ensure_ascii=False)
            
            if not remaining_knowledge:
                print("\nToutes les connaissances ont été traitées. Le fichier de quarantaine est maintenant vide.")
            else:
                print(f"\n{len(remaining_knowledge)} connaissance(s) restante(s) dans le fichier de quarantaine.")
    
    except json.JSONDecodeError:
        print(f"ERREUR: Le fichier '{UNVERIFIED_FILE}' contient du JSON invalide. Veuillez le corriger ou le supprimer.")
    except Exception as e:
        print(f"Une erreur inattendue est survenue : {e}")


if __name__ == "__main__":
    review_and_integrate()
