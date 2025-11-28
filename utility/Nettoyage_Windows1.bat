@echo off
title Nettoyage Windows - Libération d’espace disque
color 0A

echo ================================
echo  Nettoyage en cours...
echo ================================

:: Supprimer fichiers temporaires Windows
echo Nettoyage des fichiers temporaires...
del /s /f /q %windir%\Temp\* >nul 2>&1
rd /s /q %windir%\Temp >nul 2>&1
md %windir%\Temp >nul 2>&1

:: Supprimer fichiers temporaires utilisateur sauf dossier V.E.R.A
echo Nettoyage Temp utilisateur...
for /d %%D in ("%userprofile%\AppData\Local\Temp\*") do (
    if /I not "%%~nxD"=="V.E.R.A" rd /s /q "%%D"
)
del /s /f /q "%userprofile%\AppData\Local\Temp\*" >nul 2>&1

:: Nettoyer Prefetch
echo Nettoyage Prefetch...
del /s /f /q %windir%\Prefetch\* >nul 2>&1

:: Nettoyer Windows Update cache
echo Nettoyage Windows Update cache...
net stop wuauserv >nul 2>&1
rd /s /q %windir%\SoftwareDistribution\Download >nul 2>&1
net start wuauserv >nul 2>&1

:: Nettoyer logs système
echo Nettoyage logs Windows...
del /s /f /q %windir%\Logs\CBS\* >nul 2>&1
del /s /f /q %windir%\Logs\DISM\* >nul 2>&1
del /s /f /q %windir%\*.log >nul 2>&1

:: Vider corbeille
echo Nettoyage Corbeille...
rd /s /q %systemdrive%\$Recycle.bin >nul 2>&1

:: Supprimer fichiers dump mémoire
echo Nettoyage fichiers DMP...
del /s /f /q %systemroot%\MEMORY.DMP >nul 2>&1
del /s /f /q %systemroot%\Minidump\* >nul 2>&1

:: Supprimer cache miniatures
echo Nettoyage cache miniatures...
del /s /f /q "%userprofile%\AppData\Local\Microsoft\Windows\Explorer\thumbcache_*.db" >nul 2>&1

:: Lancer nettoyage disque silencieux
echo Nettoyage disque (cleanmgr)...
cleanmgr /sagerun:1 >nul 2>&1

echo ================================
echo  Nettoyage terminé !
echo ================================
pause
