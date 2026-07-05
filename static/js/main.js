// Theme Toggle
const themeToggle = document.getElementById('themeToggle');
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
if (themeToggle) {
    themeToggle.querySelector('i').className = savedTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    themeToggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        themeToggle.querySelector('i').className = next === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    });
}

// Hamburger menu
const hamburger = document.getElementById('hamburger');
const navMenu = document.getElementById('navMenu');
if (hamburger && navMenu) {
    hamburger.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        hamburger.classList.toggle('active');
    });
}

// AOS init
if (typeof AOS !== 'undefined') AOS.init({ duration: 800, once: true });

// Support modal
const openSupport = document.getElementById('openSupport');
const supportModal = document.getElementById('supportModal');
const closeSupport = document.getElementById('closeSupport');
if (openSupport && supportModal) {
    openSupport.addEventListener('click', () => supportModal.classList.add('active'));
    closeSupport && closeSupport.addEventListener('click', () => supportModal.classList.remove('active'));
    document.addEventListener('click', (e) => {
        if (e.target === supportModal) supportModal.classList.remove('active');
    });
}

// Send support message
const sendSupport = document.getElementById('sendSupport');
if (sendSupport) {
    sendSupport.addEventListener('click', () => {
        const subject = document.getElementById('supportSubject').value.trim() || 'Question';
        const message = document.getElementById('supportMessage').value.trim();
        if (!message) { alert('Veuillez écrire votre message.'); return; }

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        fetch('/support/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ subject, message })
        }).then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }).then(d => {
            if (d.status === 'success') {
                document.getElementById('supportSubject').value = '';
                document.getElementById('supportMessage').value = '';
                supportModal.classList.remove('active');
                alert('✅ Message envoyé ! Nous vous répondrons bientôt.');
            } else {
                alert('Erreur : ' + (d.message || 'Veuillez réessayer.'));
            }
        }).catch((err) => {
            console.error('Erreur envoi support:', err);
            alert('Erreur lors de l\'envoi. Veuillez réessayer.');
        });
    });
}

// Animated counters for index page
function animateCounter(el, target, suffix = '') {
    target = Number(target);
    if (!isFinite(target)) target = 0;  // Protection contre NaN/undefined

    if (target === 0) {
        el.textContent = '0' + suffix;
        return;
    }

    let start = 0;
    const duration = 1500;
    const steps = duration / 16;
    const step = target / steps;
    const timer = setInterval(() => {
        start += step;
        if (start >= target) { start = target; clearInterval(timer); }
        el.textContent = Math.round(start) + suffix;
    }, 16);
}

// Stats on index page (loaded from API)
const statTotal    = document.getElementById('statTotalSimulations');
const statAvg      = document.getElementById('statAvgScore');
const statApproval = document.getElementById('statApprovalRate');

if (statTotal || statAvg || statApproval) {
    // ?_=timestamp empêche le navigateur de servir une réponse mise en cache
    // pour cette requête GET, ce qui pourrait afficher d'anciennes statistiques
    // (par exemple "0" mis en cache avant qu'une première simulation existe).
    fetch('/api/stats?_=' + Date.now(), { cache: 'no-store' })
        .then(r => {
            console.log('[Stats] Réponse /api/stats : status', r.status);
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        })
        .then(d => {
            console.log('[Stats] Données reçues :', d);
            if (statTotal)    animateCounter(statTotal, d.total_simulations);
            if (statAvg)      animateCounter(statAvg, d.avg_score);
            if (statApproval) animateCounter(statApproval, d.approval_rate, '%');
        })
        .catch(err => {
            console.error('[Stats] Erreur chargement statistiques :', err.name, '-', err.message);
            // En cas d'échec, afficher 0 plutôt que de laisser bloqué
            if (statTotal)    statTotal.textContent = '0';
            if (statAvg)      statAvg.textContent = '0';
            if (statApproval) statApproval.textContent = '0%';
        });
}

// Legal modal
function showLegalModal(type) {
    const lang = (typeof CURRENT_LANG !== 'undefined') ? CURRENT_LANG : 'fr';
    let content;
    if (type === 'mentions') {
        content = lang === 'en'
            ? '<h2>Legal Notice</h2><p>Application developed as part of an L3 Big Data academic thesis, Bamako, Mali.</p>'
            : '<h2>Mentions légales</h2><p>Application développée dans le cadre d\'un mémoire académique L3 Big Data, Bamako, Mali.</p>';
    } else {
        content = lang === 'en'
            ? '<h2>Privacy Policy</h2><p>Your data is not shared with third parties. It is used solely for your credit evaluation.</p>'
            : '<h2>Politique de confidentialité</h2><p>Vos données ne sont pas partagées avec des tiers. Elles sont utilisées uniquement pour votre évaluation de crédit.</p>';
    }
    const closeLabel = lang === 'en' ? 'Close' : 'Fermer';

    const modal = document.createElement('div');
    modal.className = 'legal-modal-overlay';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = `<div class="legal-modal-box" style="background:white;padding:40px;border-radius:15px;max-width:500px;width:90%;position:relative;">${content}<button type="button" class="legal-modal-close" style="margin-top:20px;padding:10px 20px;background:#1a5c38;color:white;border:none;border-radius:8px;cursor:pointer;">${closeLabel}</button></div>`;

    document.body.appendChild(modal);

    // Fermeture via le bouton
    modal.querySelector('.legal-modal-close').addEventListener('click', () => modal.remove());
    // Fermeture en cliquant sur le fond gris (en dehors de la boîte blanche)
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
    // Fermeture avec la touche Échap
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            modal.remove();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}
