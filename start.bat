@echo off
echo ====================================
echo    CreditScore Pro - Demarrage
echo ====================================
echo.

:: Mode UTF-8 pour eviter les erreurs d'encodage des emojis dans la console
set PYTHONUTF8=1

:: Utiliser l'environnement virtuel Python 3.12 du projet
:: (le modele ML exige scikit-learn 1.3.2 / numpy 1.26.4, donc Python 3.12, PAS 3.13)
set VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo ERREUR: environnement virtuel introuvable : %VENV_PYTHON%
    echo Creez-le avec :  py -3.12 -m venv ..\.venv
    echo Puis installez : ..\.venv\Scripts\pip install -r requirements.txt scikit-learn==1.3.2 numpy==1.26.4 setuptools
    pause
    exit /b 1
)

echo.
echo Demarrage de l'application...
echo Ouvrez votre navigateur sur : http://localhost:5000
echo.
echo Identifiants Admin par defaut :
echo   URL     : http://localhost:5000/admin/login
echo   Login   : admin
echo   Pass    : admin123
echo.
echo Pour arreter le serveur : Ctrl+C
echo.

"%VENV_PYTHON%" "%~dp0app.py"
pause
