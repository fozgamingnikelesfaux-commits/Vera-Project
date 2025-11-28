@echo off
:: Section pour vérifier et obtenir les privilèges d'administrateur
:check_permissions
    net session >nul 2>&1
    if %errorLevel% == 0 (
        goto :admin_actions
    ) else (
        echo Demande des privilèges d'administrateur...
        powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
        exit /b
    )

:admin_actions
    echo Privilèges d'administrateur obtenus.
    
    :: Se déplace dans le répertoire du script batch
    cd /d "%~dp0"
    
    echo Activation de l'environnement virtuel...
    call ".\venv\Scripts\activate.bat"
    
    echo Lancement de Vera...
    python run.py
    
    echo.
    echo Vera s'est terminée. Appuyez sur une touche pour fermer cette fenêtre.
    pause >nul
