"""
Script de migration de données pour Vera.

Ce script convertit le fichier de mapping de connaissances externe (un gros JSON)
en une base de données SQLite pour un accès efficace et une faible consommation de RAM.
"""
import json
import sqlite3
import os
import sys

# --- Configuration ---
JSON_INPUT_PATH = "data/external_knowledge_map.json"
SQLITE_OUTPUT_PATH = "data/knowledge_map.db"

def main():
    """Fonction principale du script de migration."""
    print("*****************************************************************")
    print("*  Migration du mapping de connaissances (JSON -> SQLite)       *")
    print("*****************************************************************")
    
    if not os.path.exists(JSON_INPUT_PATH):
        print(f"\nERREUR: Le fichier d'entrée '{JSON_INPUT_PATH}' n'a pas été trouvé.")
        print("La migration est annulée.")
        return

    # Avertissement sur l'utilisation de la mémoire
    print("\nAVERTISSEMENT: Ce script va charger le fichier JSON en mémoire.")
    print("L'opération peut être lente et consommer beaucoup de RAM.")
    print("Veuillez fermer les autres applications gourmandes en mémoire.")
    
    # Demande de confirmation à l'utilisateur
    try:
        # sys.stdin.isatty() vérifie si le script est exécuté dans un terminal interactif
        if sys.stdin.isatty():
            response = input("Voulez-vous continuer ? (o/n) : ").lower()
            if response != 'o':
                print("Migration annulée par l'utilisateur.")
                return
        else:
            print("Exécution non-interactive, continuation automatique.")
    except (EOFError, KeyboardInterrupt):
         print("\nMigration annulée par l'utilisateur.")
         return


    # 1. Chargement du fichier JSON
    print(f"\n--- Chargement du fichier JSON '{JSON_INPUT_PATH}'... ---")
    try:
        with open(JSON_INPUT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Fichier JSON chargé. {len(data)} enregistrements trouvés.")
    except MemoryError:
        print("\nERREUR CRITIQUE: Manque de mémoire vive (RAM) pour charger le fichier JSON.")
        print("La migration a échoué. Veuillez vous assurer d'avoir au moins 2 Go de RAM libre.")
        return
    except Exception as e:
        print(f"\nERREUR CRITIQUE: Impossible de charger le fichier JSON. Erreur: {e}")
        return

    # 2. Création de la base de données SQLite
    print(f"\n--- Création et remplissage de la base de données '{SQLITE_OUTPUT_PATH}'... ---")
    
    if os.path.exists(SQLITE_OUTPUT_PATH):
        print(f"La base de données '{SQLITE_OUTPUT_PATH}' existe déjà. Elle sera supprimée et recréée.")
        os.remove(SQLITE_OUTPUT_PATH)

    try:
        conn = sqlite3.connect(SQLITE_OUTPUT_PATH)
        cursor = conn.cursor()

        # Création de la table
        cursor.execute("""
        CREATE TABLE knowledge (
            id INTEGER PRIMARY KEY,
            text TEXT,
            source TEXT,
            metadata TEXT
        )
        """)

        # Insertion des données
        print("Insertion des données... (cela peut prendre plusieurs minutes)")
        for i, item in enumerate(data):
            # On stocke les métadonnées en tant que chaîne JSON
            metadata_str = json.dumps(item.get("metadata", {}))
            
            cursor.execute(
                "INSERT INTO knowledge (id, text, source, metadata) VALUES (?, ?, ?, ?)",
                (i, item.get("text"), item.get("source"), metadata_str)
            )
            
            # Afficher la progression
            if (i + 1) % 10000 == 0:
                print(f"  {i + 1} / {len(data)} enregistrements insérés...")

        conn.commit()
        conn.close()
        print(f"\n{len(data)} enregistrements insérés avec succès.")

    except Exception as e:
        print(f"\nERREUR CRITIQUE: Une erreur est survenue lors de la création de la base de données. Erreur: {e}")
        if os.path.exists(SQLITE_OUTPUT_PATH):
            os.remove(SQLITE_OUTPUT_PATH) # Nettoyage en cas d'erreur
        return

    print("\n**********************************************")
    print("*         Migration terminée avec succès !         *")
    print("**********************************************")
    print(f"La nouvelle base de données est prête : '{SQLITE_OUTPUT_PATH}'")
    print("\nProchaine étape : Mettre à jour le code de Vera pour utiliser cette base de données.")

if __name__ == "__main__":
    main()
