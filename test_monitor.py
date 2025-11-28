import pprint
from system_monitor import get_system_usage, get_cpu_temperature, get_running_processes

# Ce script est conçu pour tester les fonctions du module system_monitor de manière isolée.

if __name__ == "__main__":
    print("--- Lancement du test de system_monitor.py ---")
    
    print("\n1. Test de get_system_usage():")
    usage_data = get_system_usage()
    pprint.pprint(usage_data)
    
    print("\n2. Test de get_cpu_temperature():")
    temp_data = get_cpu_temperature()
    print(f"Température CPU: {temp_data}")

    print("\n3. Test de get_running_processes():")
    processes = get_running_processes(limit=5)
    print("Top 5 des processus par utilisation mémoire:")
    pprint.pprint(processes)

    print("\n--- Test terminé ---")
