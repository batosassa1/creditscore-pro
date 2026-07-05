# Tests fonctionnels de CreditScore Pro
# Valide le parcours complet de l'application : pages publiques, inscription,
# connexion, prédiction du modèle ML, cohérence métier des scores, protection
# des pages réservées.
#
# Usage : python test_app.py
# (utilise le client de test Flask : aucun serveur à lancer)
import unittest
import time

import app as application


class TestCreditScorePro(unittest.TestCase):
    """Tests de bout en bout de l'application via le client de test Flask."""

    @classmethod
    def setUpClass(cls):
        application.app.config['TESTING'] = True
        # Le client de test ne rend pas le JavaScript : on désactive le jeton
        # CSRF pour pouvoir poster les formulaires directement.
        application.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = application.app.test_client()
        # Un email unique par exécution pour ne pas heurter la base locale
        cls.email = f'test.auto.{int(time.time())}@example.com'
        cls.mot_de_passe = 'MotDePasseTest123!'

    # ── 1. Pages publiques ────────────────────────────────────────────────────
    def test_01_pages_publiques(self):
        for route in ['/', '/about', '/login', '/register', '/admin/login']:
            reponse = self.client.get(route, follow_redirects=True)
            self.assertEqual(reponse.status_code, 200,
                             f'La page {route} doit être accessible')

    # ── 2. Le modèle ML est bien chargé ──────────────────────────────────────
    def test_02_modele_charge(self):
        modele = application.get_model()
        self.assertIsNotNone(modele, 'Le modèle de production doit se charger')

    # ── 3. Inscription puis connexion ────────────────────────────────────────
    def test_03_inscription_et_connexion(self):
        reponse = self.client.post('/register', data={
            'first_name': 'Test', 'last_name': 'Automatique',
            'email': self.email, 'phone': '70000000',
            'password': self.mot_de_passe, 'confirm_password': self.mot_de_passe,
        }, follow_redirects=True)
        self.assertEqual(reponse.status_code, 200)

        reponse = self.client.post('/login', data={
            'email': self.email, 'password': self.mot_de_passe,
        }, follow_redirects=True)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(
            b'logout' in reponse.data or 'déconnexion'.encode() in reponse.data.lower()
            or b'dashboard' in reponse.data.lower(),
            'Après connexion, la page doit refléter une session ouverte')

    # ── 4. Prédiction : profil sain ──────────────────────────────────────────
    def _predire(self, retards):
        donnees = {
            'loan_amount': '5000000', 'monthly_income': '400000', 'age': '28',
            'gender': 'female', 'education': 'bachelor', 'marital_status': 'single',
            'bill_amt1': '150000', 'bill_amt2': '140000', 'bill_amt3': '130000',
            'bill_amt4': '120000', 'bill_amt5': '110000', 'bill_amt6': '100000',
            'pay_amt1': '50000', 'pay_amt2': '50000', 'pay_amt3': '50000',
            'pay_amt4': '50000', 'pay_amt5': '50000', 'pay_amt6': '50000',
        }
        for cle in ['pay_0', 'pay_2', 'pay_3', 'pay_4', 'pay_5', 'pay_6']:
            donnees[cle] = str(retards)
        reponse = self.client.post('/predict', json=donnees)
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.get_json()
        self.assertTrue(corps.get('success'), f'La prédiction doit réussir : {corps}')
        return corps

    def test_04_prediction_profil_sain(self):
        resultat = self._predire(retards=0)
        self.assertGreaterEqual(resultat['score'], 69,
                                'Un profil sans retard doit être bien noté')
        self.assertEqual(resultat['eligibility'], 'approved')

    # ── 5. Prédiction : profil risqué ────────────────────────────────────────
    def test_05_prediction_profil_risque(self):
        resultat = self._predire(retards=3)
        self.assertLess(resultat['score'], 45,
                        'Un profil avec 3 mois de retard partout doit être mal noté')
        self.assertEqual(resultat['eligibility'], 'rejected')

    # ── 6. Cohérence métier : plus de retards = score plus bas ──────────────
    def test_06_coherence_metier(self):
        score_sain = self._predire(retards=0)['score']
        score_moyen = self._predire(retards=1)['score']
        score_risque = self._predire(retards=3)['score']
        self.assertGreater(score_sain, score_moyen)
        self.assertGreater(score_moyen, score_risque)

    # ── 7. Les pages réservées sont protégées ────────────────────────────────
    def test_07_pages_protegees(self):
        client_anonyme = application.app.test_client()  # session vierge
        for route in ['/dashboard', '/admin/dashboard', '/documentation', '/profile']:
            reponse = client_anonyme.get(route, follow_redirects=False)
            self.assertIn(reponse.status_code, (301, 302),
                          f'{route} doit rediriger les visiteurs non connectés')


if __name__ == '__main__':
    unittest.main(verbosity=2)
