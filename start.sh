#!/bin/bash
echo "===================================="
echo "   CreditScore Pro - Démarrage"
echo "===================================="
echo ""

# Install dependencies
echo "Installation des dépendances..."
pip install -r requirements.txt --quiet

echo ""
echo "Démarrage de l'application..."
echo "Ouvrez votre navigateur sur : http://localhost:5000"
echo ""
echo "Identifiants Admin par défaut :"
echo "  URL     : http://localhost:5000/admin/login"
echo "  Login   : admin"
echo "  Mot de passe : admin123"
echo ""
echo "Pour arrêter le serveur : Ctrl+C"
echo ""

python app.py
