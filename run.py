import os
import subprocess
import sys

# Définir la variable d'environnement pour contourner le problème de DLL de PyTorch
# KMP_DUPLICATE_LIB_OK=TRUE permet à la bibliothèque OpenMP (utilisée par PyTorch)
# de se charger même si une autre version est déjà en mémoire.
print("Définition de KMP_DUPLICATE_LIB_OK=TRUE pour la compatibilité PyTorch...")
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Chemin vers l'exécutable Python dans l'environnement virtuel
python_executable = os.path.join(os.path.dirname(sys.executable), 'python.exe')

# Commande pour lancer l'application principale (main.py)
command = [python_executable, 'main.py']

print(f"Lancement de l'application principale: {' '.join(command)}")

try:
    # Exécuter la commande en tant que sous-processus
    # Les sorties (stdout, stderr) seront affichées en temps réel dans la console
    process = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
    
    # Attendre que le processus se termine
    process.wait()

except KeyboardInterrupt:
    print("\nInterruption par l'utilisateur. Arrêt du processus...")
    process.terminate()
    process.wait()
except Exception as e:
    print(f"Une erreur est survenue lors de l'exécution de main.py: {e}")

print("Le script run.py a terminé.")
