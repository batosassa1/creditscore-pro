// ── Vide le sessionStorage si l'ancien format (avec "F CFA" dans les valeurs) est détecté ──
(function() {
    const raw = sessionStorage.getItem('predictionResult');
    if (raw && raw.includes('F CFA')) {
        sessionStorage.removeItem('predictionResult');
        window.location.href = '/evaluation';
    }
})();

const result = JSON.parse(sessionStorage.getItem('predictionResult') || 'null');

if (!result) {
    window.location.href = '/evaluation';
} else {
    const score = result.score;

    // ── Formate un nombre en F CFA (défensif : accepte string ou number) ──
    const formatCFA = function(val) {
        const n = typeof val === 'string'
            ? parseFloat(val.replace(/[^0-9.-]/g, ''))
            : val;
        if (isNaN(n)) return '0 F CFA';
        return Math.round(n).toLocaleString('fr-FR') + '\u00a0F\u00a0CFA';
    };

    // ── Couleurs des graphiques adaptées au thème clair/sombre ─────────────
    // Lit l'attribut data-theme posé sur <html> par main.js (theme toggle).
    function getChartTheme() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
            isDark: isDark,
            textColor:    isDark ? '#e8f5ee' : '#0f2d1e',
            gridColor:    isDark ? 'rgba(46,204,113,0.18)' : 'rgba(26,92,56,0.12)',
            mutedGrid:    isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)',
            radarFill:    isDark ? 'rgba(46,204,113,0.25)' : 'rgba(196,168,130,0.2)',
            radarBorder:  isDark ? '#2ecc71' : 'rgba(196,168,130,1)',
            radarPoint:   isDark ? '#2ecc71' : 'rgba(196,168,130,1)',
            pointBorder:  isDark ? '#0a1f13' : '#fff',
        };
    }

    let gaugeChart = null;
    let radarChart = null;

    // ── Gauge ──────────────────────────────────────────────────────────────
    function renderGauge() {
        const canvas = document.getElementById('scoreGauge');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const theme = getChartTheme();
        const color = score >= 65 ? '#2ecc71' : score >= 45 ? '#f39c12' : '#e74c3c';

        if (gaugeChart) gaugeChart.destroy();
        gaugeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [score, 100 - score],
                    backgroundColor: [color, theme.mutedGrid],
                    borderWidth: 0,
                    circumference: 180,
                    rotation: 270,
                }]
            },
            options: {
                responsive: true,
                cutout: '75%',
                plugins: { legend: { display: false }, tooltip: { enabled: false } }
            }
        });
    }

    // ── Radar chart ────────────────────────────────────────────────────────
    function renderRadar() {
        const canvas = document.getElementById('radarChart');
        if (!canvas || !result.details) return;
        const ctx = canvas.getContext('2d');
        const theme = getChartTheme();
        const d = result.details;
        const radarLang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
        const radarLabels = radarLang === 'en'
            ? ['Payment\nHistory', 'Financial\nHealth', 'Credit\nCapacity', 'Age\nProfile', 'Education']
            : ['Historique\nPaiement', 'Santé\nFinancière', 'Capacité\nCrédit', 'Profil\nÂge', 'Éducation'];
        const radarDatasetLabel = radarLang === 'en' ? 'Your profile' : 'Votre profil';

        if (radarChart) radarChart.destroy();
        radarChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: radarLabels,
                datasets: [{
                    label: radarDatasetLabel,
                    data: [
                        d.historique_paiement || 0,
                        d.sante_financiere    || 0,
                        d.capacite_credit     || 0,
                        d.profil_age          || 0,
                        d.education_score     || 0,
                    ],
                    backgroundColor: theme.radarFill,
                    borderColor: theme.radarBorder,
                    pointBackgroundColor: theme.radarPoint,
                    pointBorderColor: theme.pointBorder,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                scales: {
                    r: {
                        beginAtZero: true, max: 100, ticks: { stepSize: 25, color: theme.textColor, backdropColor: 'transparent' },
                        angleLines: { color: theme.gridColor },
                        grid: { color: theme.gridColor },
                        pointLabels: { color: theme.textColor, font: { size: 11 } }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    // ── Légende en langage simple sous le radar ────────────────────────────
    // Traduit les scores bruts (0-100) en mots compréhensibles, avec une
    // pastille de couleur, pour les utilisateurs non familiers des graphiques
    // de type "radar". Évite que le client doive interpréter lui-même un
    // diagramme technique.
    function renderRadarLegend() {
        const legendEl = document.getElementById('radarLegend');
        if (!legendEl || !result.details) return;
        const d = result.details;
        const lang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';

        function levelInfo(value) {
            if (value >= 75) return { key: 'excellent', color: '#2ecc71' };
            if (value >= 50) return { key: 'good',      color: '#34d178' };
            if (value >= 25) return { key: 'fair',       color: '#f39c12' };
            return                { key: 'weak',        color: '#e74c3c' };
        }

        const levelLabels = {
            fr: { excellent: 'Excellent', good: 'Bon', fair: 'Moyen', weak: 'À améliorer' },
            en: { excellent: 'Excellent', good: 'Good', fair: 'Fair', weak: 'Needs improvement' }
        };

        const criteria = [
            { value: d.historique_paiement, fr: 'Historique de paiement', en: 'Payment history' },
            { value: d.sante_financiere,    fr: 'Santé financière',       en: 'Financial health' },
            { value: d.capacite_credit,     fr: 'Capacité de crédit',     en: 'Credit capacity' },
            { value: d.profil_age,          fr: 'Profil âge',             en: 'Age profile' },
            { value: d.education_score,     fr: 'Éducation',              en: 'Education' },
        ];

        legendEl.innerHTML = criteria.map(function(c) {
            const v = c.value || 0;
            const level = levelInfo(v);
            const label = lang === 'en' ? c.en : c.fr;
            const levelText = levelLabels[lang === 'en' ? 'en' : 'fr'][level.key];
            return '<div class="radar-legend-item">'
                + '<span class="radar-legend-dot" style="background:' + level.color + '"></span>'
                + '<span class="radar-legend-label">' + label + '</span>'
                + '<span class="radar-legend-value" style="color:' + level.color + '">' + levelText + '</span>'
                + '</div>';
        }).join('');
    }

    function renderCharts() {
        renderGauge();
        renderRadar();
        renderRadarLegend();
    }

    renderCharts();

    // Redessine les graphiques quand l'utilisateur change de thème (sans recharger la page).
    // main.js modifie data-theme sur <html> ; on observe ce changement via MutationObserver.
    const themeObserver = new MutationObserver(function(mutations) {
        for (const m of mutations) {
            if (m.attributeName === 'data-theme') {
                renderCharts();
            }
        }
    });
    themeObserver.observe(document.documentElement, { attributes: true });

    // ── Compteur animé ─────────────────────────────────────────────────────
    const scoreVal = document.getElementById('scoreValue');
    if (scoreVal) {
        let n = 0;
        const timer = setInterval(function() {
            n += 2;
            if (n >= score) { n = score; clearInterval(timer); }
            scoreVal.textContent = Math.round(n);
        }, 20);
    }

    // ── Verdict ────────────────────────────────────────────────────────────
    const verdictText = document.getElementById('verdictText');
    const verdictDesc = document.getElementById('verdictDescription');
    const scoreCard   = document.getElementById('scoreCard');

    // Retraduit le label d'éligibilité côté client à partir de la clé technique
    // stable (result.eligibility), au lieu d'utiliser result.eligibility_label
    // qui est figé dans la langue active au moment du calcul initial.
    const ELIGIBILITY_LABELS = {
        approved:    { fr: 'Éligible',                    en: 'Eligible' },
        conditional: { fr: 'Éligible sous conditions',     en: 'Eligible with conditions' },
        rejected:    { fr: 'Non éligible',                 en: 'Not eligible' },
    };

    if (verdictText) {
        const verdictLang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
        const labelEntry = ELIGIBILITY_LABELS[result.eligibility];
        const eligibilityLabel = labelEntry ? labelEntry[verdictLang] : result.eligibility_label;

        if (result.eligibility === 'approved') {
            verdictText.textContent = '✅ ' + eligibilityLabel;
            if (scoreCard) scoreCard.style.borderTop = '5px solid #2ecc71';
        } else if (result.eligibility === 'conditional') {
            verdictText.textContent = '⚠️ ' + eligibilityLabel;
            if (scoreCard) scoreCard.style.borderTop = '5px solid #f39c12';
        } else {
            verdictText.textContent = '❌ ' + eligibilityLabel;
            if (scoreCard) scoreCard.style.borderTop = '5px solid #e74c3c';
        }
    }
    if (verdictDesc) {
        const lang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
        if (lang === 'en') {
            verdictDesc.textContent = score >= 65
                ? "Your financial profile meets the eligibility criteria."
                : score >= 45
                ? "Your application requires additional guarantees."
                : "Your current profile does not meet the criteria. Follow the recommendations below.";
        } else {
            verdictDesc.textContent = score >= 65
                ? "Votre profil financier répond aux critères d'éligibilité."
                : score >= 45
                ? "Votre dossier nécessite des garanties supplémentaires."
                : "Votre profil actuel ne satisfait pas les critères. Suivez les recommandations ci-dessous.";
        }
    }

    // ── Montants ───────────────────────────────────────────────────────────
    // Section masquee en cas de rejet : afficher un "montant recommande"
    // apres un refus de credit est contradictoire pour l'utilisateur.
    var amountSection = document.getElementById('amountSection');
    if (result.eligibility === 'rejected') {
        if (amountSection) amountSection.style.display = 'none';
    } else if (result.max_amount) {
        if (amountSection) amountSection.style.display = '';
        var el = function(id) { return document.getElementById(id); };
        if (el('minAmount'))         el('minAmount').textContent         = formatCFA(result.max_amount.min);
        if (el('recommendedAmount')) el('recommendedAmount').textContent = formatCFA(result.max_amount.recommended);
        if (el('maxAmount'))         el('maxAmount').textContent         = formatCFA(result.max_amount.max);
        if (el('monthlyValue'))      el('monthlyValue').textContent      = formatCFA(result.max_amount.monthly_payment);
    }

    // ── Recommandations ────────────────────────────────────────────────────
    // Important : ces textes sont mis en cache dans sessionStorage au moment
    // du calcul initial (/predict), dans la langue active à CE moment-là.
    // Si l'utilisateur change de langue sur la page résultats, le HTML statique
    // se retraduit automatiquement (rechargement Jinja), mais ce contenu
    // dynamique resterait figé dans l'ancienne langue sans la table ci-dessous.
    // On retraduit donc côté client à partir de l'icône (clé stable, identique
    // quelle que soit la langue) plutôt que de réafficher le texte tel quel.
    const RECOMMENDATION_TRANSLATIONS = {
        'fas fa-calendar-check': {
            fr: { title: 'Améliorez votre historique', text: 'Assurez-vous de payer vos échéances à temps.' },
            en: { title: 'Improve your payment history', text: 'Make sure to pay your installments on time.' }
        },
        'fas fa-money-bill-wave': {
            fr: { title: 'Réduisez le montant demandé', text: 'Le montant dépasse votre capacité de remboursement estimée.' },
            en: { title: 'Reduce the requested amount', text: 'The amount exceeds your estimated repayment capacity.' }
        },
        'fas fa-check-circle': {
            fr: { title: 'Profil solide', text: 'Votre profil financier est favorable pour ce crédit.' },
            en: { title: 'Strong profile', text: 'Your financial profile is favorable for this credit.' }
        },
        'fas fa-piggy-bank': {
            fr: { title: 'Constituez une épargne', text: 'Une épargne régulière améliore votre profil emprunteur.' },
            en: { title: 'Build savings', text: 'Regular savings improve your borrower profile.' }
        },
        'fas fa-thumbs-up': {
            fr: { title: 'Continuez ainsi', text: 'Maintenez vos bonnes habitudes financières.' },
            en: { title: 'Keep it up', text: 'Maintain your good financial habits.' }
        },
    };

    const grid = document.getElementById('recommendationsGrid');
    if (grid && result.recommendations) {
        const currentLang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
        grid.innerHTML = result.recommendations.map(function(r) {
            // On essaie de retrouver la traduction correcte via l'icône (clé stable).
            // Si l'icône n'est pas reconnue, on retombe sur le texte original du serveur.
            const translation = RECOMMENDATION_TRANSLATIONS[r.icon];
            const title = translation ? translation[currentLang].title : r.title;
            const text  = translation ? translation[currentLang].text  : r.text;
            return '<div class="recommendation-card">'
                + '<div class="rec-icon"><i class="' + r.icon + '"></i></div>'
                + '<h3>' + title + '</h3>'
                + '<p>' + text + '</p>'
                + '</div>';
        }).join('');
    }

    // ── Explication SHAP : pourquoi ce score ─────────────────────────────────
    const explanationSection = document.getElementById('explanationSection');
    const explanationList = document.getElementById('explanationList');
    if (explanationSection && explanationList && result.explanation && result.explanation.length > 0) {
        explanationSection.style.display = '';
        explanationList.innerHTML = result.explanation.map(function(f) {
            const positif = f.sens === 'positive';
            const couleur = positif ? 'var(--accent-primary, #1a5c38)' : '#c0392b';
            const icone = positif ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down';
            return '<div class="explanation-item">'
                + '<div class="explanation-header">'
                + '<span class="explanation-label"><i class="fas ' + icone + '" style="color:' + couleur + ';margin-right:8px;"></i>' + f.label + '</span>'
                + '<span class="explanation-effect" style="color:' + couleur + ';">' + f.effet + ' · ' + f.poids + '%</span>'
                + '</div>'
                + '<div class="explanation-bar-bg">'
                + '<div class="explanation-bar" style="width:' + Math.min(100, f.poids) + '%;background:' + couleur + ';"></div>'
                + '</div>'
                + '</div>';
        }).join('');
    }

    // ── Téléchargement du rapport PDF ────────────────────────────────────────
    const pdfBtn = document.getElementById('downloadPdfBtn');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', async function() {
            const originalHTML = pdfBtn.innerHTML;
            const lang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
            pdfBtn.disabled = true;
            pdfBtn.innerHTML = '<i class="fas fa-spinner"></i> ' +
                (lang === 'en' ? 'Generating...' : 'Génération...');

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

            try {
                const res = await fetch('/results/pdf', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(result)
                });

                if (!res.ok) {
                    let msg = 'Erreur lors de la génération du PDF.';
                    try {
                        const errJson = await res.json();
                        msg = errJson.error || msg;
                        console.error('[PDF] Erreur serveur (status ' + res.status + '):', msg);
                    } catch (e) {
                        console.error('[PDF] Erreur serveur (status ' + res.status + '), réponse non-JSON');
                    }
                    throw new Error(msg);
                }

                const blob = await res.blob();
                if (!blob || blob.size === 0) {
                    throw new Error('Le fichier PDF généré est vide.');
                }
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'creditscore_rapport.pdf';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } catch (err) {
                console.error('[PDF] Erreur:', err.name, '-', err.message);
                alert(lang === 'en'
                    ? 'Failed to generate PDF report. Please try again.'
                    : 'Échec de la génération du rapport PDF. Veuillez réessayer.');
            } finally {
                pdfBtn.disabled = false;
                pdfBtn.innerHTML = originalHTML;
            }
        });
    }
}
