"""
system_cleaner.py

Ce module fournit des fonctions pour effectuer des tâches de nettoyage système sur Windows,
en s'inspirant des scripts batch fournis par l'utilisateur.
Chaque fonction est conçue pour être aussi sûre que possible, en journalisant ses actions,
en vérifiant les permissions nécessaires et en gérant les erreurs.
"""

import os
import shutil
import subprocess
import ctypes
import psutil # NEW: Import psutil for disk space
from tools.logger import VeraLogger

logger = VeraLogger("system_cleaner")

def _get_dir_size(path):
    total_size = 0
    if os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    elif os.path.isfile(path):
        total_size = os.path.getsize(path)
    return total_size

def _is_admin():
    """Vérifie si le script est exécuté avec des privilèges d'administrateur."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _run_command(command: str, description: str) -> dict:
    """Exécute une commande shell et retourne un dictionnaire de statut."""
    logger.info(f"Exécution de la commande : {description}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            encoding='cp850', # Encodage pour la console Windows
            errors='ignore'
        )
        
        if result.returncode != 0:
            error_output = result.stderr.strip() if result.stderr else "Aucune erreur spécifique fournie par la commande."
            if result.stdout:
                error_output += f"\nStdout: {result.stdout.strip()}"
            error_message = f"Échec de la commande '{description}'. Code de retour: {result.returncode}. Erreur: {error_output}"
            logger.error(error_message)
            return {"status": "error", "message": error_message}
        
        success_message = f"Commande '{description}' exécutée avec succès."
        if result.stdout:
            success_message += f"\nOutput: {result.stdout.strip()}"
        logger.info(success_message)
        return {"status": "success", "message": success_message}
    except Exception as e:
        error_message = f"Exception lors de l'exécution de '{description}': {e}"
        logger.error(error_message, exc_info=True)
        return {"status": "error", "message": error_message}

def clear_folder_content(folder_path: str) -> dict:
    """
    Vide le contenu d'un dossier spécifié sans supprimer le dossier lui-même.
    C'est une fonction plus sûre que 'del /s /q' car elle utilise les appels système Python.
    Retourne des statistiques sur les éléments supprimés et la taille en octets.
    """
    if not os.path.isdir(folder_path):
        message = f"Le dossier spécifié n'existe pas : {folder_path}"
        logger.error(message)
        return {"status": "error", "message": message, "files_deleted": 0, "folders_deleted": 0, "errors": 0, "bytes_deleted": 0}

    logger.info(f"Début du nettoyage du dossier : {folder_path}")
    files_deleted = 0
    folders_deleted = 0
    errors = 0
    bytes_deleted = 0

    for item_name in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item_name)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                file_size = os.path.getsize(item_path)
                os.unlink(item_path)
                files_deleted += 1
                bytes_deleted += file_size
            elif os.path.isdir(item_path):
                dir_size = _get_dir_size(item_path) # Get size before deleting
                shutil.rmtree(item_path)
                folders_deleted += 1
                bytes_deleted += dir_size
        except (PermissionError, OSError) as e:
            logger.warning(f"Erreur de permission pour {item_path} (probablement en cours d'utilisation). Ignoré. Erreur: {e}")
            errors += 1
        except Exception as e:
            logger.error(f"Erreur inattendue en supprimant {item_path}: {e}. Ignoré.")
            errors += 1
    
    message = f"Nettoyage de {folder_path} terminé. {files_deleted} fichier(s), {folders_deleted} dossier(s) supprimés, et {bytes_deleted / (1024*1024):.2f} Mo libérés."
    if errors > 0:
        message += f" {errors} élément(s) n'ont pas pu être supprimés."
    
    logger.info(message)
    return {"status": "success", "message": message, "files_deleted": files_deleted, "folders_deleted": folders_deleted, "errors": errors, "bytes_deleted": bytes_deleted}

def clear_windows_temp() -> dict:
    """Vide le dossier temporaire de Windows (C:\\Windows\\Temp)."""
    win_temp = os.environ.get("SystemRoot", "C:\\Windows") + "\\Temp"
    result = clear_folder_content(win_temp)
    # Add bytes_deleted to result if not already present
    result.setdefault("bytes_deleted", 0) 
    return result

def clear_user_temp() -> dict:
    """Vide le dossier temporaire de l'utilisateur (%TEMP%)."""
    user_temp = os.environ.get("TEMP")
    if user_temp:
        result = clear_folder_content(user_temp)
        result.setdefault("bytes_deleted", 0)
        return result
    else:
        message = "Impossible de trouver le dossier temporaire de l'utilisateur (variable %TEMP% non définie)."
        logger.error(message)
        return {"status": "error", "message": message, "bytes_deleted": 0}

def clear_prefetch() -> dict:
    """Vide le dossier Prefetch de Windows."""
    prefetch_folder = os.environ.get("SystemRoot", "C:\\Windows") + "\\Prefetch"
    if _is_admin():
        result = clear_folder_content(prefetch_folder)
        result.setdefault("bytes_deleted", 0)
        return result
    else:
        message = "Le nettoyage de Prefetch nécessite des privilèges d'administrateur."
        logger.warning(message)
        return {"status": "error", "message": message, "bytes_deleted": 0}

def clear_windows_update_cache() -> dict:
    """Arrête les services, vide le cache de Windows Update et redémarre les services."""
    logger.info("Début du nettoyage du cache de Windows Update.")
    
    _run_command("net stop wuauserv", "Arrêt du service Windows Update")
    _run_command("net stop bits", "Arrêt du service BITS")
    
    cleanup_result = clear_folder_content(os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SoftwareDistribution", "Download"))
    
    _run_command("net start wuauserv", "Démarrage du service Windows Update")
    _run_command("net start bits", "Démarrage du service BITS")
    
    logger.info("Nettoyage du cache de Windows Update terminé.")
    return cleanup_result

def empty_recycle_bin() -> dict:
    """
    Vide la corbeille en utilisant une commande PowerShell et rapporte l'espace libéré.
    """
    logger.info("Tentative de vidage de la corbeille.")
    
    # 1. Obtenir l'espace libre avant l'opération
    free_bytes_before = 0
    try:
        disk_usage_before = psutil.disk_usage('C:\\')
        free_bytes_before = disk_usage_before.free
    except Exception as e:
        logger.warning(f"Impossible de récupérer l'espace disque avant le vidage de la corbeille: {e}. Continuons sans cette information.")

    # 2. Exécuter la commande de vidage de la corbeille
    command_result = _run_command('powershell.exe -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"', "Vidage de la corbeille")

    # Spécialement pour Clear-RecycleBin: un returncode de 1 signifie souvent que la corbeille est vide, pas une erreur critique.
    if command_result["status"] == "error" and "Code de retour: 1." in command_result["message"]:
        if "Aucune erreur spécifique fournie par la commande." in command_result["message"] or not command_result["message"].strip().endswith("Erreur:"):
            logger.info("Interprétation spéciale: Clear-RecycleBin a retourné 1, probablement car la corbeille était déjà vide. Traité comme succès.")
            command_result["status"] = "success"
            command_result["message"] = "Corbeille déjà vide ou vidée avec succès (Code 1 interprété comme non-erreur)."

    bytes_freed = 0
    if command_result["status"] == "success":
        # 3. Obtenir l'espace libre après l'opération
        try:
            disk_usage_after = psutil.disk_usage('C:\\')
            free_bytes_after = disk_usage_after.free
            bytes_freed = free_bytes_after - free_bytes_before
            
            if bytes_freed > 0:
                # Convertir en Mo ou Go pour une meilleure lisibilité
                if bytes_freed > (1024**3): # Si plus de 1 Go
                    space_freed_str = f"{bytes_freed / (1024**3):.2f} Go"
                else: # Sinon en Mo
                    space_freed_str = f"{bytes_freed / (1024**2):.2f} Mo"
                command_result["message"] = f"Corbeille vidée avec succès. J'ai libéré environ {space_freed_str} d'espace !"
            else:
                command_result["message"] = "Corbeille vidée avec succès. Il n'y avait rien ou très peu à libérer."
        except Exception as e:
            logger.warning(f"Impossible de calculer l'espace libéré après le vidage de la corbeille: {e}. Message par défaut.")
            command_result["message"] = "Corbeille vidée avec succès."
    
    command_result["bytes_deleted"] = bytes_freed
    return command_result

def cleanup_winsxs() -> dict:
    """Exécute DISM pour nettoyer le magasin de composants WinSxS."""
    if not _is_admin():
        message = "Le nettoyage de WinSxS (DISM) nécessite des privilèges d'administrateur."
        logger.error(message)
        return {"status": "error", "message": message}
    
    return _run_command(
        'Dism.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase',
        "Nettoyage du magasin de composants WinSxS"
    )

def uninstall_superseded_updates() -> dict:
    """Désinstalle les mises à jour Windows remplacées via DISM."""
    if not _is_admin():
        message = "La désinstallation des mises à jour remplacées (DISM) nécessite des privilèges d'administrateur."
        logger.error(message)
        return {"status": "error", "message": message}
    return _run_command(
        'Dism.exe /Online /Cleanup-Image /SPSuperseded',
        "Désinstallation des mises à jour remplacées"
    )

def clear_system_logs() -> dict:
    """Nettoie divers journaux système de Windows."""
    logger.info("Nettoyage des journaux système.")
    windir = os.environ.get("SystemRoot", "C:\\Windows")
    cbs_logs = os.path.join(windir, "Logs", "CBS")
    dism_logs = os.path.join(windir, "Logs", "DISM")
    
    total_bytes_deleted = 0
    total_files_deleted = 0
    total_folders_deleted = 0
    total_errors = 0

    result1 = clear_folder_content(cbs_logs)
    result2 = clear_folder_content(dism_logs)
    
    total_bytes_deleted += result1.get("bytes_deleted", 0) + result2.get("bytes_deleted", 0)
    total_files_deleted += result1.get("files_deleted", 0) + result2.get("files_deleted", 0)
    total_folders_deleted += result1.get("folders_deleted", 0) + result2.get("folders_deleted", 0)
    total_errors += result1.get("errors", 0) + result2.get("errors", 0)

    # Combine results for message and status
    message = f"Nettoyage des journaux système terminé. {total_files_deleted} fichier(s), {total_folders_deleted} dossier(s) supprimés, et {total_bytes_deleted / (1024*1024):.2f} Mo libérés."
    if total_errors > 0:
        message += f" {total_errors} élément(s) n'ont pas pu être supprimés."

    status = "success"
    if result1['status'] == 'error' or result2['status'] == 'error' or total_errors > 0:
        status = "error"
    
    return {"status": status, "message": message, "bytes_deleted": total_bytes_deleted, "files_deleted": total_files_deleted, "folders_deleted": total_folders_deleted, "errors": total_errors}

def clear_memory_dumps() -> dict:
    """Supprime les fichiers de vidage mémoire."""
    logger.info("Suppression des fichiers de vidage mémoire.")
    windir = os.environ.get("SystemRoot", "C:\\Windows")
    memory_dmp = os.path.join(windir, "MEMORY.DMP")
    minidump_folder = os.path.join(windir, "Minidump")
    
    total_bytes_deleted = 0
    total_files_deleted = 0
    total_folders_deleted = 0
    total_errors = 0

    if os.path.exists(memory_dmp):
        try:
            file_size = os.path.getsize(memory_dmp)
            os.unlink(memory_dmp)
            logger.info(f"Fichier {memory_dmp} supprimé.")
            total_files_deleted += 1
            total_bytes_deleted += file_size
        except Exception as e:
            logger.warning(f"Impossible de supprimer {memory_dmp}: {e}")
            total_errors += 1
            
    if os.path.isdir(minidump_folder):
        result = clear_folder_content(minidump_folder)
        total_bytes_deleted += result.get("bytes_deleted", 0)
        total_files_deleted += result.get("files_deleted", 0)
        total_folders_deleted += result.get("folders_deleted", 0)
        total_errors += result.get("errors", 0)
        if result['status'] == 'error':
            total_errors += 1 # Add to error count if sub-operation had errors

    message = f"Nettoyage des fichiers de vidage mémoire terminé. {total_files_deleted} fichier(s), {total_folders_deleted} dossier(s) supprimés, et {total_bytes_deleted / (1024*1024):.2f} Mo libérés."
    if total_errors > 0:
        message += f" {total_errors} élément(s) n'ont pas pu être supprimés."

    status = "success" if total_errors == 0 else "error"
    
    return {"status": status, "message": message, "bytes_deleted": total_bytes_deleted, "files_deleted": total_files_deleted, "folders_deleted": total_folders_deleted, "errors": total_errors}

def clear_thumbnail_cache() -> dict:
    """Nettoie le cache des miniatures de l'explorateur Windows."""
    logger.info("Nettoyage du cache des miniatures.")
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        return {"status": "error", "message": "Impossible de trouver le profil utilisateur.", "bytes_deleted": 0, "files_deleted": 0, "errors": 0}
        
    thumb_cache_path = os.path.join(user_profile, "AppData", "Local", "Microsoft", "Windows", "Explorer")
    total_errors = 0
    total_files_deleted = 0
    total_bytes_deleted = 0
    
    if os.path.isdir(thumb_cache_path):
        for item_name in os.listdir(thumb_cache_path):
            if item_name.startswith("thumbcache_") and item_name.endswith(".db"):
                item_path = os.path.join(thumb_cache_path, item_name)
                try:
                    file_size = os.path.getsize(item_path)
                    os.unlink(item_path)
                    total_files_deleted += 1
                    total_bytes_deleted += file_size
                    logger.info(f"Cache miniature supprimé : {item_path}")
                except Exception as e:
                    logger.warning(f"Impossible de supprimer le cache miniature {item_path}: {e}")
                    total_errors += 1
        
        message = f"Nettoyage du cache miniature terminé. {total_files_deleted} fichier(s) supprimés, et {total_bytes_deleted / (1024*1024):.2f} Mo libérés."
        if total_errors > 0:
            message += f" {total_errors} élément(s) n'ont pas pu être supprimés."
        
        status = "success" if total_errors == 0 else "error"
        return {"status": status, "message": message, "bytes_deleted": total_bytes_deleted, "files_deleted": total_files_deleted, "errors": total_errors}
    else:
        return {"status": "success", "message": "Dossier du cache miniature non trouvé, aucune action nécessaire.", "bytes_deleted": 0, "files_deleted": 0, "errors": 0}

def run_alphaclean() -> dict:
    """
    Exécute une séquence complète de nettoyage du système, alias "AlphaClean".
    Les actions sont ordonnées de la moins à la plus impactante, avec la corbeille en dernier.
    """
    logger.info("Lancement de la séquence de nettoyage complète 'AlphaClean'.")
    
    full_report = []
    total_bytes_freed = 0
    total_files_deleted_overall = 0
    total_folders_deleted_overall = 0
    total_errors_overall = 0
    
    # Liste ordonnée des fonctions de nettoyage à exécuter
    cleanup_sequence = [
        ("Nettoyage des fichiers temporaires utilisateur", clear_user_temp),
        ("Nettoyage des fichiers temporaires Windows", clear_windows_temp),
        ("Nettoyage du cache des miniatures", clear_thumbnail_cache),
        ("Nettoyage des journaux système", clear_system_logs),
        ("Nettoyage des vidages mémoire", clear_memory_dumps),
        ("Nettoyage du cache de Windows Update", clear_windows_update_cache),
        ("Nettoyage de Prefetch (Admin)", clear_prefetch),
        ("Désinstallation des mises à jour obsolètes (Admin)", uninstall_superseded_updates),
        ("Nettoyage des composants WinSxS (Admin)", cleanup_winsxs),
        ("Vidage de la corbeille", empty_recycle_bin)
    ]
    
    for description, clean_function in cleanup_sequence:
        logger.info(f"AlphaClean - Étape en cours : {description}")
        result = clean_function()
        status = result.get('status', 'error')
        message = result.get('message', 'Aucun message de retour.')
        
        # Aggregate stats
        total_bytes_freed += result.get("bytes_deleted", 0)
        total_files_deleted_overall += result.get("files_deleted", 0)
        total_folders_deleted_overall += result.get("folders_deleted", 0)
        total_errors_overall += result.get("errors", 0)

        # Formater le rapport pour cette étape
        report_line = f"- {description}: {status.capitalize()}."
        if "nécessite des privilèges d'administrateur" in message and not _is_admin():
            report_line += " (Ignoré, droits admin requis)"
        elif status == 'error':
             report_line += f" (Détail: {message})"
        elif result.get("bytes_deleted", 0) > 0:
            report_line += f" ({result.get('bytes_deleted', 0) / (1024*1024):.2f} Mo libérés)"

        full_report.append(report_line)

    final_message_header = "Séquence de nettoyage AlphaClean terminée."
    if total_bytes_freed > 0:
        final_message_header += f" Total libéré : {total_bytes_freed / (1024*1024):.2f} Mo."
    
    final_message = final_message_header + "\n" + "\n".join(full_report)
    logger.info(final_message)
    
    final_status = "success" if total_errors_overall == 0 else "error"
    return {"status": final_status, "message": final_message, "bytes_deleted": total_bytes_freed, "files_deleted": total_files_deleted_overall, "folders_deleted": total_folders_deleted_overall, "errors": total_errors_overall}
        
    