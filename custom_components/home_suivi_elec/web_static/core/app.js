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

  // 1) Panels
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  const selected = document.getElementById(tab);
  if (selected) selected.classList.add('active');

  // 2) Buttons (fiabilisé)
  const buttons = Array.from(document.querySelectorAll('#tabs .subtab-btn'));
  buttons.forEach(b => b.classList.remove('active'));

  const activeBtn = buttons.find(b => (b.dataset.tab || '') === tab);
  if (activeBtn) activeBtn.classList.add('active');
};

