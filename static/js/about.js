// Page À propos — animations supplémentaires
document.addEventListener('DOMContentLoaded', function() {
    // Compteurs animés pour les métriques du modèle
    const counters = document.querySelectorAll('[data-count]');
    counters.forEach(function(counter) {
        const target = parseFloat(counter.getAttribute('data-count'));
        let current = 0;
        const step = target / 60;
        const timer = setInterval(function() {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            counter.textContent = Number.isInteger(target)
                ? Math.round(current).toLocaleString('fr-FR')
                : current.toFixed(1);
        }, 16);
    });

    // Accordéon FAQ
    document.querySelectorAll('.faq-question').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const item = btn.closest('.faq-item');
            const wasOpen = item.classList.contains('open');
            document.querySelectorAll('.faq-item').forEach(function(i) {
                i.classList.remove('open');
            });
            if (!wasOpen) item.classList.add('open');
        });
    });
});
