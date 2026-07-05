# CreditScore Pro 🏦

Application web de credit scoring avec IA — Flask + Modèle ML entraîné.

---

## 📧 Activer l'envoi de vrais emails (mot de passe oublié)

Par défaut, la fonctionnalité "Mot de passe oublié" fonctionne en **mode démo** : le lien de réinitialisation s'affiche directement à l'écran au lieu d'être envoyé par email.

Pour activer l'envoi de **vrais emails** via Gmail :

**1 — Créer un mot de passe d'application Gmail**
1. Allez sur [myaccount.google.com/security](https://myaccount.google.com/security)
2. Activez la **validation en deux étapes** (obligatoire pour les mots de passe d'application)
3. Allez dans **Mots de passe des applications** (`myaccount.google.com/apppasswords`)
4. Créez un mot de passe pour "Mail" — vous obtenez un code à 16 caractères

**2 — Définir les variables d'environnement avant de lancer l'app**

Sur Windows (PowerShell) :
```powershell
$env:MAIL_USERNAME="votre.email@gmail.com"
$env:MAIL_PASSWORD="le-code-16-caracteres"
python app.py
```

Sur Mac/Linux :
```bash
export MAIL_USERNAME="votre.email@gmail.com"
export MAIL_PASSWORD="le-code-16-caracteres"
python app.py
```

**Important :** utilisez bien le mot de passe d'application à 16 caractères, **pas** votre mot de passe Gmail habituel — Google le refusera sinon.

Si ces variables ne sont pas définies, l'application continue de fonctionner normalement en mode démo (aucun crash).

## 🚀 Démarrage rapide

### Windows
Double-cliquez sur `start.bat`

### Mac / Linux
```bash
chmod +x start.sh
./start.sh
```

### Manuel
```bash
pip install -r requirements.txt
python app.py
```

Puis ouvrez : **http://localhost:5000**

---

## 🔑 Identifiants par défaut

| Rôle | URL | Login | Mot de passe |
|------|-----|-------|--------------|
| Admin | `/admin/login` | `admin` | `admin123` |
| Client | `/register` | (créer un compte) | — |

---

## 📁 Structure du projet

```
credit_scoring_app/
├── app.py                    ← Application Flask principale
├── requirements.txt          ← Dépendances Python
├── start.bat                 ← Démarrage Windows
├── start.sh                  ← Démarrage Mac/Linux
├── model/
│   └── classifier_gs_model.pkl  ← ⚠️ À placer ici !
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── evaluation.html
│   ├── results.html
│   ├── dashboard.html        ← Dashboard Admin
│   ├── user_dashboard.html   ← Dashboard Client
│   ├── auth/
│   │   ├── login.html
│   │   └── admin_login.html
│   └── ...
├── static/
│   ├── css/style.css
│   └── js/
│       ├── main.js
│       ├── evaluation.js
│       └── results.js
└── instance/
    └── credit_scoring.db     ← Créé automatiquement
```

---

## ⚠️ Important : Placer le modèle ML

Copiez votre fichier `classifier_gs_model.pkl` dans le dossier `model/` :

```
credit_scoring_app/
└── model/
    └── classifier_gs_model.pkl   ← ICI
```

**Sans ce fichier**, l'application fonctionne en mode démonstration (scores calculés par heuristique).

---

## 🌐 Pages disponibles

| Page | URL | Accès |
|------|-----|-------|
| Accueil | `/` | Public |
| Évaluation | `/evaluation` | Connecté |
| Résultats | `/results` | Connecté |
| Mon Dashboard | `/dashboard` | Client |
| Mon Profil | `/profile` | Client |
| Dashboard Admin | `/admin/dashboard` | Admin |
| Gestion Utilisateurs | `/admin/users` | Admin |
| Support | `/admin/support` | Admin |
| Documentation | `/documentation` | Public |

---

## 📊 Variables du modèle

Le modèle `classifier_gs_model.pkl` attend ces colonnes :

- `limit_bal` — Limite de crédit
- `sex` — 'Male' / 'Female'
- `education` — 'Graduate school' / 'University' / 'High school' / 'Others'
- `marriage` — 'Married' / 'Single' / 'Others'
- `age` — Âge en années
- `payment_status_sep` à `payment_status_apr` — Statut de paiement (−2 à 9)
- `bill_statement_sep` à `bill_statement_apr` — Montants des factures
- `previous_payment_sep` à `previous_payment_apr` — Montants payés

---

Développé dans le cadre d'un mémoire L3 Big Data — Bamako, Mali.
