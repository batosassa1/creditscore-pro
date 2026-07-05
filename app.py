import os
import json
import csv
import io
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask_mail import Mail, Message
import joblib
import numpy as np
import pandas as pd

# ── App setup ─────────────────────────────────────────────────────────────
app = Flask(__name__)
SECRET_KEY_FALLBACK = 'creditscore-pro-secret-2024-memoire'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', SECRET_KEY_FALLBACK)
if app.config['SECRET_KEY'] == SECRET_KEY_FALLBACK:
    print('⚠️  AVERTISSEMENT : Utilisation de la clé secrète (SECRET_KEY) par défaut.')
    print('    Veuillez définir la variable d\'environnement SECRET_KEY en production.')
# Chemin ABSOLU vers la base de données : peu importe le dossier depuis lequel
# vous lancez "python app.py", la base sera toujours au même endroit.
# Sans cela, lancer l'app depuis un dossier différent créait une NOUVELLE base
# vide à chaque fois, donnant l'impression que les comptes "disparaissaient".
_basedir = os.path.abspath(os.path.dirname(__file__))
_instance_dir = os.path.join(_basedir, 'instance')
os.makedirs(_instance_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(_instance_dir, 'credit_scoring.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True

# ── Configuration email (réinitialisation de mot de passe) ───────────────────
# Pour activer l'envoi de vrais emails, définissez ces variables d'environnement :
#   MAIL_USERNAME=votre.email@gmail.com
#   MAIL_PASSWORD=mot_de_passe_application_gmail   (PAS votre mot de passe Gmail normal !)
# Voir README.md pour les instructions de création d'un "mot de passe d'application" Gmail.
# Si ces variables ne sont pas définies, l'app reste en mode démo (lien affiché à l'écran).
app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

EMAIL_ENABLED = bool(app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD'])
mail = Mail(app)

# ── "Se souvenir de moi" : durée du cookie de session persistante ────────────
from datetime import timedelta as _timedelta
app.config['REMEMBER_COOKIE_DURATION'] = _timedelta(days=30)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = _timedelta(days=30)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ── Cohérence du nom d'hôte ────────────────────────────────────────────────
# Le navigateur traite "localhost:5000" et "127.0.0.1:5000" comme deux origines
# DIFFÉRENTES, donc deux jeux de cookies différents. Si l'utilisateur navigue
# entre les deux (lien, favori, copier-coller d'URL), il perd silencieusement
# sa session de connexion sans aucun message d'erreur — symptôme observé :
# "Erreur de connexion" au clic sur Calculer Mon Score après avoir bien rempli
# le formulaire. On force ici une redirection systématique vers localhost.
@app.before_request
def _enforce_consistent_host():
    if request.host.startswith('127.0.0.1'):
        new_url = request.url.replace('127.0.0.1', 'localhost', 1)
        return redirect(new_url, code=302)


# ── Gestion d'erreurs explicite pour les requêtes AJAX ────────────────────────
# Sans cela, une erreur CSRF (token expiré) ou une erreur serveur renvoie une
# page HTML d'erreur que le JavaScript ne peut pas lire, et qui s'affiche comme
# un vague "Erreur de connexion" sans indication de la vraie cause.
from flask_wtf.csrf import CSRFError

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    print('❌ Erreur CSRF :', e.description)
    if request.path.startswith('/predict') or request.path.startswith('/support') or request.is_json:
        return jsonify({
            'success': False,
            'status': 'error',
            'error': "Votre session a expiré. Veuillez rafraîchir la page (F5) et réessayer.",
            'message': "Votre session a expiré. Veuillez rafraîchir la page (F5) et réessayer."
        }), 400
    flash("Votre session a expiré. Veuillez réessayer.", 'error')
    return redirect(url_for('login'))

@app.errorhandler(500)
def handle_internal_error(e):
    import traceback
    print('❌ ERREUR 500 sur', request.path, ':', str(e))
    traceback.print_exc()
    if request.is_json or request.path.startswith('/predict') or request.path.startswith('/support'):
        return jsonify({
            'success': False,
            'status': 'error',
            'error': 'Une erreur interne est survenue. Vérifiez le terminal du serveur pour le détail.',
            'message': 'Une erreur interne est survenue.'
        }), 500
    return e

# ── Traductions FR/EN ─────────────────────────────────────────────────────────
TRANSLATIONS = {
    'fr': {
        'login_required': 'Veuillez vous connecter pour accéder à cette page.',
        'login_required_support': 'Vous devez être connecté pour envoyer un message au support.',
        'login_error': 'Email ou mot de passe incorrect.',
        'register_success': 'Compte créé avec succès ! Connectez-vous.',
        'logout_success': 'Vous avez été déconnecté.',
        'profile_updated': 'Profil mis à jour.',
        'admin_only': 'Accès réservé aux administrateurs.',
        'client_only': 'Accès réservé aux clients.',
        'reset_sent': 'Si cet email existe, vous recevrez un lien de réinitialisation.',
        'reset_invalid': 'Ce lien est invalide ou expiré.',
        'reset_success': 'Mot de passe modifié avec succès. Connectez-vous.',
        'support_sent': 'Message envoyé. Nous vous répondrons bientôt.',
        'support_empty': 'Le message ne peut pas être vide.',
        'eligibility_approved': 'Éligible',
        'eligibility_conditional': 'Éligible sous conditions',
        'eligibility_rejected': 'Non éligible',
        'rec_payment': {'title': 'Améliorez votre historique', 'text': 'Assurez-vous de payer vos échéances à temps.'},
        'rec_amount': {'title': 'Réduisez le montant demandé', 'text': 'Le montant dépasse votre capacité de remboursement estimée.'},
        'rec_good': {'title': 'Profil solide', 'text': 'Votre profil financier est favorable pour ce crédit.'},
        'rec_saving': {'title': 'Constituez une épargne', 'text': 'Une épargne régulière améliore votre profil emprunteur.'},
        'rec_default': {'title': 'Continuez ainsi', 'text': 'Maintenez vos bonnes habitudes financières.'},
    },
    'en': {
        'login_required': 'Please log in to access this page.',
        'login_required_support': 'You must be logged in to send a support message.',
        'login_error': 'Incorrect email or password.',
        'register_success': 'Account created successfully! Please log in.',
        'logout_success': 'You have been logged out.',
        'profile_updated': 'Profile updated.',
        'admin_only': 'Access restricted to administrators.',
        'client_only': 'Access restricted to clients.',
        'reset_sent': 'If this email exists, you will receive a reset link.',
        'reset_invalid': 'This link is invalid or expired.',
        'reset_success': 'Password changed successfully. Please log in.',
        'support_sent': 'Message sent. We will get back to you soon.',
        'support_empty': 'Message cannot be empty.',
        'eligibility_approved': 'Eligible',
        'eligibility_conditional': 'Eligible with conditions',
        'eligibility_rejected': 'Not eligible',
        'rec_payment': {'title': 'Improve your payment history', 'text': 'Make sure to pay your installments on time.'},
        'rec_amount': {'title': 'Reduce the requested amount', 'text': 'The amount exceeds your estimated repayment capacity.'},
        'rec_good': {'title': 'Strong profile', 'text': 'Your financial profile is favorable for this credit.'},
        'rec_saving': {'title': 'Build savings', 'text': 'Regular savings improve your borrower profile.'},
        'rec_default': {'title': 'Keep it up', 'text': 'Maintain your good financial habits.'},
    }
}

def t(key):
    """Retourne la traduction pour la langue active."""
    lang = session.get('lang', 'fr')
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, key)

def t_nested(key, subkey):
    lang = session.get('lang', 'fr')
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, {}).get(subkey, key)

@app.context_processor
def inject_lang():
    """Injecte la langue et les traductions dans tous les templates."""
    lang = session.get('lang', 'fr')
    return dict(lang=lang, t=t, translations=TRANSLATIONS.get(lang, TRANSLATIONS['fr']))

@app.route('/set-lang/<lang>')
def set_lang(lang):
    """Bascule la langue FR ↔ EN."""
    if lang in ('fr', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# ── ML Model (classifier_gs_model.pkl) ───────────────────────────────────────
_model = None
_model_load_error = None
_model_load_attempted = False  # Distingue "pas encore essayé" de "fichier absent"

def get_model():
    """Charge le modèle ML une seule fois (mise en cache).
    En cas d'échec (ex: version numpy/scikit-learn incompatible avec celle
    utilisée pour entraîner le modèle), l'application bascule automatiquement
    en mode démo au lieu de planter, et explique l'erreur dans le terminal."""
    global _model, _model_load_error, _model_load_attempted
    if not _model_load_attempted:
        _model_load_attempted = True
        # Modèle final (HistGradientBoosting + feature engineering, voir
        # 1-modelisation/entrainement_final.py). Si absent, on retombe sur
        # l'ancien modèle Random Forest (classifier_gs_model.pkl).
        _model_dir = os.path.join(os.path.dirname(__file__), 'model')
        model_path = os.path.join(_model_dir, 'classifier_final_model.pkl')
        if not os.path.exists(model_path):
            model_path = os.path.join(_model_dir, 'classifier_gs_model.pkl')
        if os.path.exists(model_path):
            try:
                _model = joblib.load(model_path)
                print('✅ Modèle ML chargé avec succès.')
            except Exception as exc:
                _model_load_error = str(exc)
                print('⚠️  ATTENTION : impossible de charger le modèle ML.')
                print('    Erreur :', exc)
                print('    Cause probable : versions numpy/scikit-learn différentes')
                print('    de celles utilisées pour entraîner le modèle.')
                print('    Solution : réinstallez les dépendances avec les versions exactes :')
                print('      pip install -r requirements.txt --force-reinstall')
                print('    L\'application continue de fonctionner en MODE DÉMO')
                print('    (score calculé par une formule simplifiée, pas par le vrai modèle).')
        else:
            _model_load_error = 'Fichier model/classifier_gs_model.pkl introuvable.'
            print('⚠️  ATTENTION : fichier model/classifier_gs_model.pkl introuvable.')
            print('    L\'application fonctionne en MODE DÉMO (score simplifié).')
    return _model


def get_model_status():
    """Retourne l'état du modèle ML pour affichage dans le dashboard admin.
    Appelle get_model() pour s'assurer que la tentative de chargement a eu lieu."""
    get_model()
    return {
        'loaded': _model is not None,
        'error': _model_load_error,
    }


# ── Database Models ───────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name    = db.Column(db.String(80), nullable=False)
    last_name     = db.Column(db.String(80), nullable=False)
    phone         = db.Column(db.String(30))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)
    reset_token   = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    simulations   = db.relationship('Simulation', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'u_{self.id}'

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def is_reset_token_valid(self, token):
        return (self.reset_token == token and
                self.reset_token_expiry and
                datetime.utcnow() < self.reset_token_expiry)


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_login    = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'a_{self.id}'


class Simulation(db.Model):
    __tablename__ = 'simulations'
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score             = db.Column(db.Float, nullable=False)
    eligibility       = db.Column(db.String(20), nullable=False)
    loan_amount       = db.Column(db.Float, default=0)
    max_amount        = db.Column(db.Float, default=0)
    employment_status = db.Column(db.String(50), default='N/A')
    details           = db.Column(db.Text)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)


class SupportTicket(db.Model):
    __tablename__ = 'support_tickets'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Obligatoire maintenant
    subject    = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    reply      = db.Column(db.Text)
    replied_at = db.Column(db.DateTime)
    status     = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_rel   = db.relationship('User', foreign_keys=[user_id])


# ── Login manager ─────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    if not user_id or '_' not in user_id:
        return None
    prefix, _, raw_id = user_id.partition('_')
    try:
        int_id = int(raw_id)
    except ValueError:
        return None
    if prefix == 'u':
        return db.session.get(User, int_id)
    if prefix == 'a':
        return db.session.get(Admin, int_id)
    return None

@login_manager.unauthorized_handler
def unauthorized():
    # Pour les requêtes AJAX (predict, support), renvoyer du JSON clair
    # au lieu d'une redirection HTML — sinon le fetch() JavaScript échoue
    # silencieusement avec une erreur réseau peu explicite.
    if request.path.startswith('/predict') or request.path.startswith('/support') or request.is_json:
        msg = t('login_required')
        return jsonify({
            'success': False,
            'status': 'error',
            'error': msg,
            'message': msg,
            'login_required': True
        }), 401
    flash(t('login_required'), 'info')
    return redirect(url_for('login', next=request.path))

# ── Decorators ────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Admin):
            flash(t('admin_only'), 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

def user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, User):
            flash(t('client_only'), 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── Prediction logic ──────────────────────────────────────────────────────────
EDUCATION_MAP = {
    'graduate_school': 'Graduate school',
    'bachelor':        'University',
    'high_school':     'High school',
    'master':          'Graduate school',
    'phd':             'Graduate school',
    'associate':       'University',
    'other':           'Others',
}
GENDER_MAP  = {'male': 'Male', 'female': 'Female'}
MARRIAGE_MAP = {'married': 'Married', 'single': 'Single', 'divorced': 'Others', 'widowed': 'Others'}

FCFA_TO_TWD = 19.0  # 1 TWD ≈ 19 F CFA

def _safe_float(value, default=0.0):
    """Convertit en float de façon sûre : gère None, '', et valeurs invalides
    sans jamais lever d'exception (évite les erreurs 500 sur formulaire incomplet)."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    """Convertit en int de façon sûre (voir _safe_float)."""
    return int(_safe_float(value, default))


def predict_score(data, lang='fr'):
    model = get_model()

    loan_amount_fcfa = _safe_float(data.get('loan_amount'), 9500000)
    monthly_income   = _safe_float(data.get('monthly_income'), 500000)
    age              = _safe_int(data.get('age'), 30)
    education_raw    = data.get('education') or 'bachelor'
    gender_raw       = data.get('gender') or 'male'
    marital_raw      = data.get('marital_status') or 'single'
    pay_0 = _safe_int(data.get('pay_0'))
    pay_2 = _safe_int(data.get('pay_2'))
    pay_3 = _safe_int(data.get('pay_3'))
    pay_4 = _safe_int(data.get('pay_4'))
    pay_5 = _safe_int(data.get('pay_5'))
    pay_6 = _safe_int(data.get('pay_6'))

    # Conversion F CFA → TWD pour le modèle (sécurisée contre champs vides)
    def twd(x): return _safe_float(data.get(x)) / FCFA_TO_TWD

    education = EDUCATION_MAP.get(education_raw, 'University')
    sex       = GENDER_MAP.get(gender_raw, 'Male')
    marriage  = MARRIAGE_MAP.get(marital_raw, 'Single')

    if model is not None:
        limit_bal_twd = loan_amount_fcfa / FCFA_TO_TWD
        bills    = [twd('bill_amt1'), twd('bill_amt2'), twd('bill_amt3'),
                    twd('bill_amt4'), twd('bill_amt5'), twd('bill_amt6')]
        payments = [twd('pay_amt1'), twd('pay_amt2'), twd('pay_amt3'),
                    twd('pay_amt4'), twd('pay_amt5'), twd('pay_amt6')]
        statuses = [pay_0, pay_2, pay_3, pay_4, pay_5, pay_6]

        # ── Variables métier (feature engineering, voir entrainement_final.py) ──
        utilisation = (sum(bills) / len(bills)) / limit_bal_twd if limit_bal_twd else 0.0
        utilisation = max(-5.0, min(5.0, utilisation))
        total_bills = sum(bills)
        ratio_remb  = (sum(payments) / total_bills) if total_bills > 0 else 1.0
        ratio_remb  = max(0.0, min(5.0, ratio_remb))

        features = pd.DataFrame([{
            'limit_bal':            limit_bal_twd,
            'sex':                  sex,
            'education':            education,
            'marriage':             marriage,
            'age':                  age,
            'payment_status_sep':   pay_0,
            'payment_status_aug':   pay_2,
            'payment_status_jul':   pay_3,
            'payment_status_jun':   pay_4,
            'payment_status_may':   pay_5,
            'payment_status_apr':   pay_6,
            'bill_statement_sep':   bills[0],
            'bill_statement_aug':   bills[1],
            'bill_statement_jul':   bills[2],
            'bill_statement_jun':   bills[3],
            'bill_statement_may':   bills[4],
            'bill_statement_apr':   bills[5],
            'previous_payment_sep': payments[0],
            'previous_payment_aug': payments[1],
            'previous_payment_jul': payments[2],
            'previous_payment_jun': payments[3],
            'previous_payment_may': payments[4],
            'previous_payment_apr': payments[5],
            'utilisation_credit':   utilisation,
            'ratio_remboursement':  ratio_remb,
            'retard_max':           max(statuses),
            'nb_mois_retard':       sum(1 for s in statuses if s > 0),
            'tendance_retard':      pay_0 - pay_6,
        }])
        proba = model.predict_proba(features)[0]
        score = round(float(proba[0]) * 100, 1)
    else:
        score = _demo_score(pay_0, pay_2, pay_3, monthly_income, loan_amount_fcfa, age)

    tr = TRANSLATIONS.get(lang, TRANSLATIONS['fr'])

    # Seuil "approuvé" à 69 : correspond au seuil de décision optimisé de 0.31
    # sur la probabilité de défaut (voir 1-modelisation/benchmark_modeles.py).
    if score >= 69:
        eligibility = 'approved'
        eligibility_label = tr['eligibility_approved']
    elif score >= 45:
        eligibility = 'conditional'
        eligibility_label = tr['eligibility_conditional']
    else:
        eligibility = 'rejected'
        eligibility_label = tr['eligibility_rejected']

    payment_score    = max(0, 100 - (max(pay_0, pay_2, pay_3) * 20))
    financial_health = min(100, (monthly_income / max(loan_amount_fcfa, 1)) * 200) if loan_amount_fcfa > 0 else 70
    credit_capacity  = min(100, score * 1.1)
    details = {
        'historique_paiement': round(payment_score, 1),
        'sante_financiere':    round(min(100, financial_health), 1),
        'capacite_credit':     round(min(100, credit_capacity), 1),
        'profil_age':          min(100, max(20, (age - 18) * 2)),
        'education_score':     {'Graduate school': 85, 'University': 70, 'High school': 55, 'Others': 45}.get(education, 60),
    }

    recs = []
    if pay_0 > 0:
        recs.append({'icon': 'fas fa-calendar-check', **tr['rec_payment']})
    if loan_amount_fcfa > monthly_income * 24:
        recs.append({'icon': 'fas fa-money-bill-wave', **tr['rec_amount']})
    if score >= 69:
        recs.append({'icon': 'fas fa-check-circle', **tr['rec_good']})
    if score < 45:
        recs.append({'icon': 'fas fa-piggy-bank', **tr['rec_saving']})
    if not recs:
        recs.append({'icon': 'fas fa-thumbs-up', **tr['rec_default']})

    return {
        'score': score,
        'eligibility': eligibility,
        'eligibility_label': eligibility_label,
        'details': details,
        'recommendations': recs,
    }


def _demo_score(pay_0, pay_2, pay_3, monthly_income, loan_amount, age):
    base = 70
    base -= pay_0 * 12
    base -= pay_2 * 8
    base -= pay_3 * 6
    if loan_amount > 0 and monthly_income > 0:
        ratio = loan_amount / (monthly_income * 12)
        if ratio > 5: base -= 15
        elif ratio > 3: base -= 8
    if age < 25: base -= 5
    elif age > 50: base += 5
    return round(max(5, min(98, base)), 1)


def calculate_max_amount(monthly_income, score, requested_amount):
    monthly_income   = float(monthly_income or 0)
    score            = float(score or 0)
    requested_amount = float(requested_amount or 0)
    capacity         = monthly_income * 12 * (score / 100) * 0.8 if monthly_income > 0 else requested_amount * (score / 100)
    # Le montant "recommandé" ne doit jamais dépasser ce que le client a demandé :
    # suggérer un montant supérieur à la demande initiale est contre-intuitif pour
    # l'utilisateur et pourrait être interprété comme une incitation à emprunter
    # davantage que nécessaire. On recommande donc le minimum entre sa capacité
    # réelle et sa demande — jamais plus que ce qu'il a demandé.
    recommended      = min(capacity, requested_amount)
    return {
        'min':             round(recommended * 0.5),
        'recommended':     round(recommended),
        'max':             round(capacity),
        'monthly_payment': round(recommended / 36) if recommended > 0 else 0,
    }


# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    total_sims = Simulation.query.count()
    avg_score  = db.session.query(db.func.avg(Simulation.score)).scalar() or 0
    approved   = Simulation.query.filter_by(eligibility='approved').count()
    rate       = round(approved / total_sims * 100, 1) if total_sims > 0 else 0
    return render_template('index.html', total_simulations=total_sims,
                           avg_score=round(float(avg_score), 1), approval_rate=rate)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/documentation')
def documentation():
    return render_template('documentation.html')

@app.route('/history')
def history():
    if current_user.is_authenticated and isinstance(current_user, User):
        return redirect(url_for('dashboard'))
    return render_template('history_public.html')

@app.route('/evaluation')
@login_required
def evaluation():
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))

    # ── Calcul des 6 derniers mois réels à partir d'aujourd'hui ──────────────
    # Mois 1 = mois en cours (le plus récent), Mois 6 = il y a 5 mois.
    # Ces noms sont uniquement pour l'affichage : les champs du formulaire
    # restent pay_0/pay_2/pay_3/pay_4/pay_5/pay_6 (compatibilité avec le modèle UCI).
    lang = session.get('lang', 'fr')
    months_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    months_en = ['January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
    month_names_list = months_en if lang == 'en' else months_fr

    today = datetime.utcnow()
    last_six_months = []
    for i in range(6):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        last_six_months.append(f'{month_names_list[month - 1]} {year}')

    return render_template('evaluation.html', last_six_months=last_six_months)

@app.route('/results')
def results():
    return render_template('results.html')


@app.route('/results/pdf', methods=['POST'])
@login_required
def results_pdf():
    """Génère un rapport PDF du résultat d'évaluation.
    Les données du résultat (score, montants, recommandations, détails radar)
    sont envoyées par le navigateur car elles sont déjà dans le sessionStorage
    côté client — on évite ainsi de devoir les sauvegarder côté serveur."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.spider import SpiderChart

    try:
        data = request.get_json(force=True)
        lang = session.get('lang', 'fr')

        score             = _safe_float(data.get('score'))
        eligibility       = data.get('eligibility', '')
        eligibility_label = data.get('eligibility_label', '')
        max_amount        = data.get('max_amount', {}) or {}
        details           = data.get('details', {}) or {}
        recommendations   = data.get('recommendations', []) or []

        # ── Couleurs cohérentes avec le thème vert de l'application ──────────
        GREEN_DARK  = HexColor('#1a5c38')
        GREEN_LIGHT = HexColor('#2ecc71')
        GREY_TEXT   = HexColor('#4a6657')

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                 topMargin=20*mm, bottomMargin=20*mm,
                                 leftMargin=20*mm, rightMargin=20*mm)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('TitleGreen', parent=styles['Title'],
                                      textColor=GREEN_DARK, fontSize=22, spaceAfter=4)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                         textColor=GREY_TEXT, fontSize=11, spaceAfter=18)
        h2_style = ParagraphStyle('H2Green', parent=styles['Heading2'],
                                   textColor=GREEN_DARK, fontSize=14, spaceBefore=16, spaceAfter=8)
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14)
        score_style = ParagraphStyle('ScoreBig', parent=styles['Normal'],
                                      fontSize=42, textColor=GREEN_DARK, alignment=TA_CENTER, leading=46)
        verdict_style = ParagraphStyle('Verdict', parent=styles['Normal'],
                                        fontSize=13, alignment=TA_CENTER, textColor=GREEN_DARK, spaceAfter=4)

        is_en = (lang == 'en')
        story = []

        # ── En-tête ────────────────────────────────────────────────────────
        story.append(Paragraph('CreditScore Pro', title_style))
        story.append(Paragraph(
            'Rapport d\'évaluation de crédit' if not is_en else 'Credit Evaluation Report',
            subtitle_style))
        story.append(HRFlowable(width='100%', thickness=1, color=HexColor('#d4e8d8')))
        story.append(Spacer(1, 14))

        # ── Infos client + date ───────────────────────────────────────────
        client_name = f'{current_user.first_name} {current_user.last_name}' if isinstance(current_user, User) else ''
        date_str = datetime.utcnow().strftime('%d/%m/%Y' if not is_en else '%m/%d/%Y')
        info_label = 'Client' if not is_en else 'Client'
        date_label = 'Date' if not is_en else 'Date'
        story.append(Paragraph(f'<b>{info_label} :</b> {client_name}', body_style))
        story.append(Paragraph(f'<b>{date_label} :</b> {date_str}', body_style))
        story.append(Spacer(1, 16))

        # ── Score et verdict ───────────────────────────────────────────────
        story.append(Paragraph(f'{round(score)}<font size="14">/100</font>', score_style))
        story.append(Paragraph(eligibility_label, verdict_style))
        story.append(Spacer(1, 10))

        # ── Graphique radar (natif PDF, pas une capture d'écran) ─────────────
        radar_labels_fr = ['Historique\nPaiement', 'Santé\nFinancière', 'Capacité\nCrédit', 'Profil\nÂge', 'Éducation']
        radar_labels_en = ['Payment\nHistory', 'Financial\nHealth', 'Credit\nCapacity', 'Age\nProfile', 'Education']
        radar_labels = radar_labels_en if is_en else radar_labels_fr
        radar_values = [
            details.get('historique_paiement', 0),
            details.get('sante_financiere', 0),
            details.get('capacite_credit', 0),
            details.get('profil_age', 0),
            details.get('education_score', 0),
        ]

        story.append(Paragraph(
            'Analyse Détaillée' if not is_en else 'Detailed Analysis', h2_style))

        drawing = Drawing(400, 220)
        spider = SpiderChart()
        spider.x = 100
        spider.y = 10
        spider.width = 200
        spider.height = 200
        spider.data = [radar_values]
        spider.labels = radar_labels
        spider.strands[0].strokeColor = GREEN_DARK
        spider.strands[0].fillColor = HexColor('#2ecc7133')
        spider.strands[0].strokeWidth = 2
        spider.spokes.strokeColor = HexColor('#d4e8d8')
        spider.spokeLabels.fontSize = 8
        spider.spokeLabels.fontName = 'Helvetica'
        drawing.add(spider)
        story.append(drawing)
        story.append(Spacer(1, 10))

        # ── Montants disponibles ──────────────────────────────────────────
        story.append(Paragraph(
            'Montants Disponibles' if not is_en else 'Available Amounts', h2_style))

        def fmt_cfa(v):
            return f'{round(_safe_float(v)):,} F CFA'.replace(',', ' ')

        amount_table_data = [
            ['Minimum' if not is_en else 'Minimum',
             'Recommandé' if not is_en else 'Recommended',
             'Maximum' if not is_en else 'Maximum'],
            [fmt_cfa(max_amount.get('min')), fmt_cfa(max_amount.get('recommended')), fmt_cfa(max_amount.get('max'))]
        ]
        amount_table = Table(amount_table_data, colWidths=[150, 150, 150])
        amount_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (1, 1), (1, 1), HexColor('#eaf7ee')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#d4e8d8')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(amount_table)
        story.append(Spacer(1, 6))
        monthly = fmt_cfa(max_amount.get('monthly_payment'))
        monthly_label = 'Mensualité estimée' if not is_en else 'Estimated monthly payment'
        story.append(Paragraph(f'<b>{monthly_label} :</b> {monthly}/mois' if not is_en else f'<b>{monthly_label}:</b> {monthly}/month', body_style))

        # ── Recommandations ────────────────────────────────────────────────
        if recommendations:
            story.append(Paragraph(
                'Recommandations Personnalisées' if not is_en else 'Personalized Recommendations', h2_style))
            for rec in recommendations:
                title = rec.get('title', '')
                text = rec.get('text', '')
                story.append(Paragraph(f'<b>&#8226; {title}</b> — {text}', body_style))
                story.append(Spacer(1, 4))

        # ── Pied de page / mention légale ────────────────────────────────
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width='100%', thickness=0.5, color=HexColor('#d4e8d8')))
        story.append(Spacer(1, 8))
        footer_text = (
            "Ce rapport est généré automatiquement par CreditScore Pro à titre indicatif. "
            "Il ne constitue pas un engagement de crédit. Pour toute démarche, présentez ce "
            "document à votre conseiller bancaire."
        ) if not is_en else (
            "This report is automatically generated by CreditScore Pro for informational "
            "purposes only. It does not constitute a credit commitment. Present this document "
            "to your bank advisor for further steps."
        )
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                                       textColor=GREY_TEXT, alignment=TA_LEFT)
        story.append(Paragraph(footer_text, footer_style))

        doc.build(story)
        buffer.seek(0)

        filename = f'creditscore_rapport_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.pdf'
        return Response(
            buffer.read(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        import traceback
        print('❌ ERREUR génération PDF :', str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── AUTH ROUTES ───────────────────────────────────────────────────────────────
# Simple in-memory tracker for rate limiting login attempts
_login_attempts = {}

def get_lockout_info(ip):
    if ip in _login_attempts:
        count, lockout_until = _login_attempts[ip]
        if lockout_until and datetime.utcnow() < lockout_until:
            return True, int((lockout_until - datetime.utcnow()).total_seconds() / 60) + 1
    return False, 0

def record_failed_attempt(ip):
    now = datetime.utcnow()
    if ip not in _login_attempts:
        _login_attempts[ip] = (1, None)
    else:
        count, lockout_until = _login_attempts[ip]
        if lockout_until and now >= lockout_until:
            _login_attempts[ip] = (1, None)
        else:
            new_count = count + 1
            if new_count >= 5:
                # Bloquer pendant 5 minutes
                _login_attempts[ip] = (new_count, now + timedelta(minutes=5))
            else:
                _login_attempts[ip] = (new_count, None)

def reset_attempts(ip):
    _login_attempts.pop(ip, None)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard') if isinstance(current_user, Admin) else url_for('index'))

    if request.method == 'POST':
        ip = request.remote_addr
        is_locked, minutes_remaining = get_lockout_info(ip)
        if is_locked:
            flash(f"Trop de tentatives de connexion. Réessayez dans {minutes_remaining} minute(s)." if session.get('lang','fr')=='fr' else f"Too many login attempts. Try again in {minutes_remaining} minute(s).", 'error')
            return render_template('auth/login.html')

        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember_me'))
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            reset_attempts(ip)
            session.permanent = remember  # Active la durée de 30 jours si "Se souvenir de moi" est coché
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(request.args.get('next') or url_for('index'))
        
        record_failed_attempt(ip)
        flash(t('login_error'), 'error')

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email      = request.form.get('email', '').strip().lower()
        password   = request.form.get('password', '')
        confirm    = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name  = request.form.get('last_name', '').strip()
        phone      = request.form.get('phone', '').strip()

        errors = []
        if not email or '@' not in email:
            errors.append('Email invalide.' if session.get('lang','fr')=='fr' else 'Invalid email.')
        if len(password) < 8:
            errors.append('Mot de passe trop court (min. 8 caractères).' if session.get('lang','fr')=='fr' else 'Password too short (min. 8 characters).')
        if password != confirm:
            errors.append('Les mots de passe ne correspondent pas.' if session.get('lang','fr')=='fr' else 'Passwords do not match.')
        if not first_name or not last_name:
            errors.append('Prénom et nom requis.' if session.get('lang','fr')=='fr' else 'First and last name required.')
        if User.query.filter_by(email=email).first():
            errors.append('Cet email est déjà utilisé.' if session.get('lang','fr')=='fr' else 'This email is already used.')

        if errors:
            for e in errors: flash(e, 'error')
            return render_template('auth/login.html', register_mode=True)

        user = User(email=email, first_name=first_name, last_name=last_name, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(t('register_success'), 'success')
        return redirect(url_for('login'))

    return render_template('auth/login.html', register_mode=True)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash(t('logout_success'), 'info')
    return redirect(url_for('index'))


# ── MOT DE PASSE OUBLIÉ ───────────────────────────────────────────────────────
def send_reset_email(user, reset_url, lang='fr'):
    """Envoie un vrai email de réinitialisation via SMTP (asynchrone)."""
    if lang == 'en':
        subject = 'CreditScore Pro — Password Reset'
        body = f"""Hello {user.first_name},

You requested a password reset for your CreditScore Pro account.

Click the link below to choose a new password (valid for 1 hour):
{reset_url}

If you did not request this, you can safely ignore this email.

— CreditScore Pro Team
"""
    else:
        subject = 'CreditScore Pro — Réinitialisation de mot de passe'
        body = f"""Bonjour {user.first_name},

Vous avez demandé la réinitialisation du mot de passe de votre compte CreditScore Pro.

Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe (valable 1 heure) :
{reset_url}

Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité.

— L'équipe CreditScore Pro
"""
    msg = Message(subject=subject, recipients=[user.email], body=body)
    from threading import Thread
    def send_async_email(app_context, email_msg):
        with app_context.app_context():
            mail.send(email_msg)
    Thread(target=send_async_email, args=(app, msg)).start()


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        lang  = session.get('lang', 'fr')

        if user:
            token = user.generate_reset_token()
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)

            if EMAIL_ENABLED:
                # ── Mode production : envoi d'un vrai email ──────────────────
                try:
                    send_reset_email(user, reset_url, lang=lang)
                    flash(t('reset_sent'), 'success')
                except Exception as exc:
                    # En cas d'échec d'envoi (ex: identifiants SMTP invalides),
                    # on retombe sur l'affichage du lien pour ne pas bloquer l'utilisateur.
                    print(f'⚠️ Échec envoi email : {exc}')
                    if lang == 'en':
                        flash(f'<strong>Email sending failed</strong> ({exc}). '
                              f'Here is your reset link instead: '
                              f'<a href="{reset_url}">{reset_url}</a>', 'warning')
                    else:
                        flash(f"<strong>Échec de l'envoi email</strong> ({exc}). "
                              f"Voici votre lien de réinitialisation à la place : "
                              f'<a href="{reset_url}">{reset_url}</a>', 'warning')
            else:
                # ── Mode démo : aucun service SMTP configuré ──────────────────
                if lang == 'en':
                    flash(f'<strong>Demo mode</strong> — no email service is configured. '
                          f'Click here to reset your password: '
                          f'<a href="{reset_url}">{reset_url}</a>', 'info')
                else:
                    flash(f'<strong>Mode démo</strong> — aucun service email n\'est configuré. '
                          f'Cliquez ici pour réinitialiser votre mot de passe : '
                          f'<a href="{reset_url}">{reset_url}</a>', 'info')
        else:
            flash(t('reset_sent'), 'info')  # Ne pas révéler si l'email existe
    return render_template('auth/forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.is_reset_token_valid(token):
        flash(t('reset_invalid'), 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Mot de passe trop court (min. 8 caractères).' if session.get('lang','fr')=='fr' else 'Password too short.', 'error')
            return render_template('auth/reset_password.html', token=token)
        if password != confirm:
            flash('Les mots de passe ne correspondent pas.' if session.get('lang','fr')=='fr' else 'Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
        user.set_password(password)
        user.reset_token        = None
        user.reset_token_expiry = None
        db.session.commit()
        flash(t('reset_success'), 'success')
        return redirect(url_for('login'))

    return render_template('auth/reset_password.html', token=token)


# ── CLIENT ROUTES ─────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
@user_required
def dashboard():
    simulations = current_user.simulations.order_by(Simulation.created_at.desc()).all()
    total       = len(simulations)
    approved    = sum(1 for s in simulations if s.eligibility == 'approved')
    conditional = sum(1 for s in simulations if s.eligibility == 'conditional')
    rejected    = sum(1 for s in simulations if s.eligibility == 'rejected')
    avg_score   = round(sum(s.score for s in simulations) / total, 1) if total > 0 else 0
    rate        = round(approved / total * 100, 1) if total > 0 else 0
    return render_template('user_dashboard.html', user=current_user, simulations=simulations,
                           total_simulations=total, approved=approved, conditional=conditional,
                           rejected=rejected, avg_score=avg_score, approval_rate=rate)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
@user_required
def profile():
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name).strip()
        current_user.last_name  = request.form.get('last_name', current_user.last_name).strip()
        current_user.phone      = request.form.get('phone', current_user.phone).strip()
        db.session.commit()
        flash(t('profile_updated'), 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)


@app.route('/support/tickets')
@login_required
@user_required
def user_tickets():
    tickets = SupportTicket.query.filter_by(user_id=current_user.id)\
                .order_by(SupportTicket.created_at.desc()).all()
    return render_template('user_tickets.html', tickets=tickets)


# ── PREDICT API ───────────────────────────────────────────────────────────────
@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        data   = request.get_json(force=True)
        lang   = session.get('lang', 'fr')
        result = predict_score(data, lang=lang)
        max_amount = calculate_max_amount(
            _safe_float(data.get('monthly_income')), result['score'], _safe_float(data.get('loan_amount')))

        if isinstance(current_user, User):
            sim = Simulation(
                user_id=current_user.id, score=result['score'],
                eligibility=result['eligibility'],
                loan_amount=_safe_float(data.get('loan_amount')),
                max_amount=_safe_float(max_amount.get('recommended')),
                employment_status=data.get('employment_status') or 'N/A',
                details=json.dumps(data),
            )
            db.session.add(sim)
            db.session.commit()

        return jsonify({'success': True, 'score': result['score'],
                        'eligibility': result['eligibility'],
                        'eligibility_label': result['eligibility_label'],
                        'max_amount': max_amount,
                        'details': result['details'],
                        'recommendations': result['recommendations']})
    except Exception as e:
        # Affiche l'erreur complète dans le terminal pour diagnostic,
        # même en mode debug=False (sinon l'erreur reste invisible).
        import traceback
        print('❌ ERREUR /predict :', str(e))
        traceback.print_exc()

        return jsonify({'success': False, 'error': str(e)}), 500


# ── SUPPORT API (connectés uniquement) ───────────────────────────────────────
@app.route('/support/send', methods=['POST'])
@login_required
def send_support():
    if not isinstance(current_user, User):
        return jsonify({'status': 'error', 'message': t('login_required_support')}), 403
    try:
        data    = request.get_json(force=True)
        subject = data.get('subject', '').strip() or ('Question' if session.get('lang','fr')=='fr' else 'Question')
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'status': 'error', 'message': t('support_empty')}), 400

        ticket = SupportTicket(user_id=current_user.id, subject=subject, message=message)
        db.session.add(ticket)
        db.session.commit()
        return jsonify({'status': 'success', 'message': t('support_sent')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── ADMIN ROUTES ──────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        ip = request.remote_addr
        is_locked, minutes_remaining = get_lockout_info(ip)
        if is_locked:
            flash(f"Trop de tentatives de connexion. Réessayez dans {minutes_remaining} minute(s)." if session.get('lang','fr')=='fr' else f"Too many login attempts. Try again in {minutes_remaining} minute(s).", 'error')
            return render_template('auth/admin_login.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin = Admin.query.filter(
            (Admin.username == username) | (Admin.email == username.lower())
        ).first()
        if admin and admin.check_password(password):
            reset_attempts(ip)
            login_user(admin)
            admin.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        
        record_failed_attempt(ip)
        flash('Identifiants incorrects.' if session.get('lang','fr')=='fr' else 'Incorrect credentials.', 'error')
    return render_template('auth/admin_login.html')


@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    from sqlalchemy import func as sqlfunc
    total_users = User.query.count()
    stats = db.session.query(
        sqlfunc.count(Simulation.id),
        sqlfunc.sum((Simulation.eligibility == 'approved').cast(db.Integer)),
        sqlfunc.sum((Simulation.eligibility == 'conditional').cast(db.Integer)),
        sqlfunc.sum((Simulation.eligibility == 'rejected').cast(db.Integer)),
        sqlfunc.avg(Simulation.score),
    ).one()
    total_sims  = stats[0] or 0
    approved    = stats[1] or 0
    conditional = stats[2] or 0
    rejected    = stats[3] or 0
    avg_score   = round(float(stats[4] or 0), 1)
    rate        = round(approved / total_sims * 100, 1) if total_sims > 0 else 0
    recent_sims = Simulation.query.order_by(Simulation.created_at.desc()).limit(50).all()
    top_users   = db.session.query(User, db.func.count(Simulation.id).label('sim_count'))\
        .join(Simulation, User.id == Simulation.user_id).group_by(User.id)\
        .order_by(db.desc('sim_count')).limit(10).all()
    # ── Statut réel du modèle ML (chargé / mode démo) ─────────────────────────
    model_status = get_model_status()

    # ── Vraies métriques du modèle ML (chargées depuis model_stats.pkl) ──────
    model_metrics = {
        'roc_auc': None, 'accuracy': None, 'precision': None,
        'recall': None, 'f1': None,
        'data_source': 'UCI Machine Learning Repository' if model_status['loaded'] else 'Mode démo (modèle non chargé)'
    }
    try:
        stats_path = os.path.join(os.path.dirname(__file__), 'model', 'model_stats.pkl')
        if os.path.exists(stats_path):
            loaded_stats = joblib.load(stats_path)
            # Normalisation des métriques (si elles sont stockées en pourcentage > 1.0)
            for k in ['roc_auc', 'accuracy', 'precision', 'recall', 'f1']:
                if k in loaded_stats and loaded_stats[k] is not None:
                    val = float(loaded_stats[k])
                    if val > 1.0:
                        loaded_stats[k] = val / 100.0
            model_metrics.update(loaded_stats)
    except Exception:
        pass

    # ── Vraies données de simulations sur les 7 derniers jours ───────────────
    from datetime import timedelta as _td
    today = datetime.utcnow().date()
    week_labels = []
    week_counts = []
    for i in range(6, -1, -1):
        day = today - _td(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + _td(days=1)
        count = Simulation.query.filter(
            Simulation.created_at >= day_start,
            Simulation.created_at < day_end
        ).count()
        week_labels.append(day.strftime('%d/%m'))
        week_counts.append(count)


    return render_template('dashboard.html', total_users=total_users, total_simulations=total_sims,
                           approved=approved, conditional=conditional, rejected=rejected,
                           avg_score=avg_score, approval_rate=rate,
                           recent_simulations=recent_sims, top_users=top_users,
                           model_metrics=model_metrics, model_status=model_status,
                           week_labels=week_labels, week_counts=week_counts)


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    return render_template('users.html', users=User.query.order_by(User.created_at.desc()).all())


@app.route('/admin/users/<int:user_id>')
@login_required
@admin_required
def admin_user_detail(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('Utilisateur introuvable.', 'error')
        return redirect(url_for('admin_users'))
    sims = user.simulations.order_by(Simulation.created_at.desc()).all()
    avg_score = round(sum(sim.score for sim in sims) / len(sims), 1) if sims else 0.0
    return render_template('user_detail.html', user=user, simulations=sims, avg_score=avg_score)


@app.route('/admin/support')
@login_required
@admin_required
def admin_support():
    return render_template('support.html',
                           tickets=SupportTicket.query.order_by(SupportTicket.created_at.desc()).all())


@app.route('/admin/support/reply/<int:ticket_id>', methods=['POST'])
@login_required
@admin_required
def admin_reply(ticket_id):
    ticket = db.session.get(SupportTicket, ticket_id)
    if not ticket:
        return jsonify({'status': 'error', 'message': 'Ticket introuvable'}), 404
    data = request.get_json(force=True)
    ticket.reply      = data.get('reply', '')
    ticket.replied_at = datetime.utcnow()
    ticket.status     = 'closed'
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/admin/export/simulations')
@login_required
@admin_required
def admin_export_simulations():
    sims   = Simulation.query.order_by(Simulation.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Utilisateur', 'Email', 'Score', 'Éligibilité', 'Montant', 'Max Accordé', 'Date'])
    for s in sims:
        writer.writerow([s.id, f'{s.user.first_name} {s.user.last_name}', s.user.email,
                         s.score, s.eligibility, s.loan_amount, s.max_amount,
                         s.created_at.strftime('%d/%m/%Y %H:%M')])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=simulations.csv'})


@app.route('/admin/export/users')
@login_required
@admin_required
def admin_export_users():
    users  = User.query.order_by(User.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Prénom', 'Nom', 'Email', 'Téléphone', 'Simulations', 'Inscrit le', 'Dernière connexion'])
    for u in users:
        writer.writerow([u.id, u.first_name, u.last_name, u.email, u.phone or '',
                         u.simulations.count(), u.created_at.strftime('%d/%m/%Y'),
                         u.last_login.strftime('%d/%m/%Y') if u.last_login else ''])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=utilisateurs.csv'})


@app.route('/api/stats')
def api_stats():
    total    = Simulation.query.count()
    avg      = db.session.query(db.func.avg(Simulation.score)).scalar() or 0
    approved = Simulation.query.filter_by(eligibility='approved').count()
    rate     = round(approved / total * 100, 1) if total > 0 else 0
    return jsonify({'total_simulations': total, 'avg_score': round(float(avg), 1), 'approval_rate': rate})


# ── DB Init ───────────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        if not Admin.query.filter_by(username='admin').first():
            # En production, definir ADMIN_PASSWORD dans les variables
            # d'environnement (Render : onglet Environment). Le mot de passe
            # par defaut n'est utilise qu'en developpement local.
            admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
            admin = Admin(username='admin', email='admin@creditscore.pro')
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            if admin_password == 'admin123':
                print('✅ Admin créé : admin / admin123 (mot de passe par défaut, DEV uniquement)')
                print('⚠️  En production, définissez la variable d\'environnement ADMIN_PASSWORD.')
            else:
                print('✅ Admin créé avec le mot de passe défini par ADMIN_PASSWORD.')
        print('✅ Base de données initialisée.')


# Initialisation de la base au chargement du module : indispensable en production
# (gunicorn importe l'app sans exécuter le bloc __main__). L'opération est
# idempotente : les tables et l'admin ne sont créés que s'ils n'existent pas.
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'🚀 CreditScore Pro démarre sur http://localhost:{port}')
    app.run(debug=False, host='0.0.0.0', port=port)
