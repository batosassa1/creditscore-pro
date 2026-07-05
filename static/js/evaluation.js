let currentStep = 1;
const totalSteps = 3;

function updateProgress() {
    const fill = document.getElementById('progressFill');
    const steps = document.querySelectorAll('.progress-step');
    if (fill) fill.style.width = ((currentStep - 1) / (totalSteps - 1) * 100) + '%';
    steps.forEach((s, i) => {
        s.classList.toggle('active', i + 1 <= currentStep);
        s.classList.toggle('completed', i + 1 < currentStep);
    });
}

function nextStep(step) {
    if (!validateStep(currentStep)) {
        console.warn('[Évaluation] Validation échouée à l\'étape', currentStep);
        return;
    }
    // IMPORTANT : on cible bien .form-step[data-step="X"] et non n'importe quel
    // élément avec data-step (les pastilles .progress-step ont aussi cet attribut).
    const currentEl = document.querySelector(`.form-step[data-step="${currentStep}"]`);
    const nextEl = document.querySelector(`.form-step[data-step="${step}"]`);
    if (!currentEl || !nextEl) {
        console.error('[Évaluation] Étape de formulaire introuvable dans le DOM:', { currentStep, step, currentEl, nextEl });
        return;
    }
    currentEl.classList.remove('active', 'slide-back');
    currentStep = step;
    // On avance : glissement classique depuis la droite (slide-back retiré au cas où).
    nextEl.classList.remove('slide-back');
    // Forcer le navigateur à "oublier" l'état précédent pour rejouer l'animation CSS.
    void nextEl.offsetWidth;
    nextEl.classList.add('active');
    updateProgress();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function prevStep(step) {
    const currentEl = document.querySelector(`.form-step[data-step="${currentStep}"]`);
    const prevEl = document.querySelector(`.form-step[data-step="${step}"]`);
    if (!currentEl || !prevEl) return;
    currentEl.classList.remove('active', 'slide-back');
    currentStep = step;
    // On recule : glissement inversé depuis la gauche.
    void prevEl.offsetWidth;
    prevEl.classList.add('active', 'slide-back');
    updateProgress();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function validateStep(step) {
    const stepEl = document.querySelector(`.form-step[data-step="${step}"]`);
    if (!stepEl) {
        console.error('[Évaluation] Impossible de trouver .form-step[data-step="' + step + '"]');
        return false;
    }
    const inputs = stepEl.querySelectorAll('input[required], select[required]');
    let valid = true;
    inputs.forEach(input => {
        const errorEl = document.getElementById(input.id + 'Error');
        if (!input.value || !input.value.trim()) {
            if (errorEl) errorEl.textContent = 'Ce champ est requis.';
            input.style.borderColor = 'var(--danger, #C47B6E)';
            valid = false;
        } else {
            if (errorEl) errorEl.textContent = '';
            input.style.borderColor = '';
        }
    });
    return valid;
}

// Rendre les fonctions accessibles globalement (utilisées via onclick="" dans le HTML)
window.nextStep = nextStep;
window.prevStep = prevStep;

// Form submit
const evaluationForm = document.getElementById('evaluationForm');
let isSubmitting = false;  // Empêche toute double soumission (clic multiple, double listener, etc.)

if (evaluationForm) {
    evaluationForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        e.stopImmediatePropagation();  // Empêche tout autre listener "submit" dupliqué de s'exécuter

        if (isSubmitting) {
            console.warn('[Évaluation] Soumission déjà en cours, requête ignorée.');
            return;
        }
        if (!validateStep(3)) return;

        isSubmitting = true;
        const submitBtn = evaluationForm.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.style.display = 'flex';

        const formData = new FormData(e.target);
        const data = {};
        formData.forEach((v, k) => { data[k] = (v === '' || isNaN(v)) ? v : Number(v); });

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

        try {
            const res = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(data)
            });

            if (!res.ok) {
                // On essaie de lire le message d'erreur JSON renvoyé par le serveur
                // (session expirée, CSRF expiré, erreur 500, etc.) au lieu d'afficher
                // un message générique.
                let serverMessage = null;
                let loginRequired = false;
                try {
                    const errJson = await res.json();
                    serverMessage = errJson.error || errJson.message;
                    loginRequired = !!errJson.login_required;
                } catch (parseErr) {
                    // La réponse n'était pas du JSON (page d'erreur HTML par ex.)
                }
                console.error('[Évaluation] Erreur HTTP', res.status, serverMessage);
                if (overlay) overlay.style.display = 'none';

                if (res.status === 401 || loginRequired) {
                    alert((serverMessage || 'Votre session a expiré.') +
                          '\n\nVous allez être redirigé vers la page de connexion.');
                    window.location.href = '/login?next=/evaluation';
                    return;
                }
                if (res.status === 400 && serverMessage && serverMessage.includes('session')) {
                    alert(serverMessage + '\n\nLa page va se recharger.');
                    window.location.reload();
                    return;
                }
                alert(serverMessage || ('Erreur serveur (code ' + res.status + '). Vérifiez le terminal où tourne "python app.py" pour le détail.'));
                return;
            }

            const result = await res.json();
            if (result.success) {
                sessionStorage.setItem('predictionResult', JSON.stringify(result));
                window.location.href = '/results';
            } else {
                if (overlay) overlay.style.display = 'none';
                alert('Erreur : ' + (result.error || 'Veuillez réessayer.'));
            }
        } catch (err) {
            console.error('[Évaluation] Erreur lors de la prédiction:', err);
            console.error('[Évaluation] Détail technique:', err.name, '-', err.message);
            console.error('[Évaluation] Le fetch vers /predict a échoué AVANT de recevoir une réponse HTTP.');
            console.error('[Évaluation] Causes possibles : (1) le serveur Flask a planté/redémarré, ' +
                          '(2) un pare-feu/antivirus bloque la requête, (3) extension navigateur qui interfère.');
            if (overlay) overlay.style.display = 'none';
            alert('Erreur de connexion réseau (' + err.name + ': ' + err.message + ').\n\n' +
                  'Vérifiez que le terminal "python app.py" tourne toujours et n\'affiche pas d\'erreur.\n' +
                  'Si le terminal semble normal, essayez de rafraîchir la page (F5) et réessayez.');
        } finally {
            isSubmitting = false;
            if (submitBtn) submitBtn.disabled = false;
        }
    });
} else {
    console.error('[Évaluation] Formulaire #evaluationForm introuvable dans le DOM');
}

updateProgress();
