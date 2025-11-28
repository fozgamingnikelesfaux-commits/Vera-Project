@echo off
title Nettoyage Windows - Optimisation espace disque
echo ===============================================
echo       Script de nettoyage et optimisation
echo ===============================================
echo.

:: 1) Nettoyage des fichiers temporaires Windows et utilisateur
echo [1/5] Suppression des fichiers temporaires...
del /s /q /f %temp%\* 2>nul
rd /s /q %temp% 2>nul
md %temp%
del /s /q /f C:\Windows\Temp\* 2>nul
echo OK.
echo.

:: 2) Nettoyage du cache de Windows Update
echo [2/5] Nettoyage du cache Windows Update...
net stop wuauserv >nul 2>&1
net stop bits >nul 2>&1
rd /s /q C:\Windows\SoftwareDistribution\Download 2>nul
net start wuauserv >nul 2>&1
net start bits >nul 2>&1
echo OK.
echo.

:: 3) Nettoyage de WinSxS (fichiers systèmes obsolètes)
echo [3/5] Nettoyage de WinSxS (composants inutiles)...
Dism.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase
echo OK.
echo.

:: 4) Désinstallation des anciennes mises à jour remplacées
echo [4/5] Désinstallation des anciennes mises à jour remplacées...
Dism.exe /Online /Cleanup-Image /SPSuperseded
echo OK.
echo.

:: 5) Lancement de l’outil de nettoyage disque automatique
echo [5/5] Lancement du nettoyage disque Windows...
cleanmgr /sagerun:1
echo OK.
echo.

echo ===============================================
echo   Nettoyage terminé ! Redémarre ton PC si besoin
echo ===============================================
pause
