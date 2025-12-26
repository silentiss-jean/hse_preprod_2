// app.js - Point d'entrée principal (VERSION FINALE ROUTER)
"use strict";

console.log("✅ home_suivi_elec UI - Chargement");

/**
 * Initialisation au chargement du DOM
 */
document.addEventListener("DOMContentLoaded", async () => {
    console.log("🚀 Initialisation UI terminée - Router actif");
});

/**
 * Fonction globale de navigation entre onglets
 * ⚠️ Gère UNIQUEMENT l'activation CSS
 * Le chargement des modules est délégué au router.js
 */
window.showTab = function(tab) {
    console.log(`📍 Navigation CSS vers: ${tab}`);

    // Masquer tous les onglets
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.remove('active');
    });

    // Afficher l'onglet sélectionné
    const selected = document.getElementById(tab);
    if (selected) {
        selected.classList.add('active');
    }
};
