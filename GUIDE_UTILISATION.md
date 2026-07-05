# Guide d'utilisation - CreditScore Pro

> Application web d'évaluation du risque de crédit par Machine Learning.
> Version en ligne : https://creditscore-pro-wsos.onrender.com

---

## 1. Accéder à l'application

### En ligne (recommandé)

Ouvrez simplement l'adresse suivante dans un navigateur (ordinateur ou téléphone) :

**https://creditscore-pro-wsos.onrender.com**

Remarque : l'hébergement gratuit met l'application en veille après 15 minutes
d'inactivité. Si la page met du temps à s'ouvrir (jusqu'à une minute), c'est
qu'elle se réveille ; patientez puis rechargez.

### En local (sur l'ordinateur du projet)

1. Double-cliquez sur `start.bat` (dossier `3-application`) ;
2. Ouvrez votre navigateur sur **http://localhost:5000**.

Le script vérifie l'environnement Python 3.12 et démarre le serveur. Pour
arrêter : Ctrl+C dans la fenêtre noire.

---

## 2. Parcours client

### Étape 1 : créer un compte

1. Cliquez sur **Connexion** puis **Créer un compte** (ou directement `/register`) ;
2. Renseignez prénom, nom, email, téléphone et un mot de passe ;
3. Connectez-vous avec votre email et votre mot de passe.

### Étape 2 : évaluer votre éligibilité

1. Cliquez sur **Évaluer mon score** (bouton vert de l'accueil) ;
2. Le formulaire comporte **3 étapes** :
   - **Informations personnelles** : âge, genre, éducation, situation matrimoniale ;
   - **Demande de crédit** : montant souhaité (en F CFA) et revenu mensuel ;
   - **Historique financier** : retards de paiement éventuels des 6 derniers mois,
     montants facturés et montants remboursés ;
3. Cliquez sur **Calculer mon score**.

### Étape 3 : lire vos résultats

La page de résultats affiche :

- **Le score** (0 à 100) : plus il est haut, plus le profil est solide ;
- **La décision** :
  - **Approuvé** (score ≥ 69) : profil éligible ;
  - **Conditionnel** (45 à 68) : dossier à examiner, garanties possibles ;
  - **Rejeté** (< 45) : risque trop élevé en l'état ;
- **Le graphique radar** : votre profil détaillé en 5 dimensions
  (historique de paiement, santé financière, capacité de crédit, âge, éducation) ;
- **Les recommandations personnalisées** pour améliorer votre profil ;
- **Le montant maximum estimé** pour votre demande.

### Votre tableau de bord

Le menu **Dashboard** conserve l'historique de toutes vos simulations, avec
l'évolution de votre score dans le temps et vos statistiques personnelles.

### Support

Le bouton flottant (bulle verte en bas à droite) permet d'envoyer une question
au support ; les réponses apparaissent dans **Mes questions**.

---

## 3. Parcours administrateur

### Connexion

1. Ouvrez **/admin/login** (page distincte de la connexion client) ;
2. Identifiant : `admin` ; mot de passe : celui défini à l'installation
   (variable d'environnement `ADMIN_PASSWORD` en production, `admin123`
   par défaut en local).

### Fonctions disponibles

- **Dashboard** : statistiques globales (utilisateurs, simulations, scores),
  état du modèle ML et ses métriques réelles (AUC, précision, rappel, F1,
  matrice de confusion) ;
- **Utilisateurs** : liste, détail et gestion des comptes clients ;
- **Simulations** : historique complet de toutes les évaluations ;
- **Support** : lecture et réponse aux tickets des clients ;
- **Exports CSV** : téléchargement des utilisateurs et des simulations ;
- **Documentation** : page technique réservée à l'administrateur.

---

## 4. Questions fréquentes

**Le score maximum est-il 100 ?**
Non : le maximum observable est d'environ 97,6. Le modèle ne délivre jamais de
certitude absolue, car un risque résiduel existe toujours (aléas de la vie
absents des données). C'est un comportement sain et voulu.

**Pourquoi les montants sont-ils convertis ?**
Le modèle a été entraîné sur des données en dollars taïwanais (TWD). L'application
convertit automatiquement vos montants en F CFA vers cette échelle : vous n'avez
rien à faire.

**Mon compte en ligne a disparu.**
L'hébergement gratuit réinitialise la base de données à chaque mise à jour de
l'application. Recréez simplement votre compte. (En production réelle, une base
persistante serait utilisée : voir chapitre 4 du mémoire.)

**La page « mot de passe oublié » n'envoie pas d'email.**
Par défaut l'application est en mode démonstration : le lien de réinitialisation
s'affiche à l'écran. L'envoi de vrais emails s'active en configurant les
variables `MAIL_USERNAME` et `MAIL_PASSWORD` (voir README.md).

**L'application est-elle utilisable sur téléphone ?**
Oui, l'interface est adaptative : le menu se replie dans le bouton ☰ en haut à
droite.

**Comment changer la langue ?**
Le bouton EN / FR dans le bandeau bascule l'interface entre français et anglais.
Le bouton lune/soleil bascule entre thème clair et thème sombre.

---

## 5. En cas de problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| La page en ligne met une minute à s'ouvrir | Application en veille (hébergement gratuit) | Patienter puis recharger |
| « Mode démo dégradé » sur le dashboard admin | Modèle ML non chargé (versions Python) | Réinstaller avec `pip install -r requirements.txt` sous Python 3.12 |
| Erreur au calcul du score | Session expirée | Se reconnecter puis réessayer |
| Les caractères accentués s'affichent mal dans la console locale | Encodage Windows | Lancer via `start.bat` (active l'UTF-8) |
