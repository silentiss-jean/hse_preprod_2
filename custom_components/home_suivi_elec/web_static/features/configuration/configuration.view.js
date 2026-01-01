// configuration.view.js — Legacy (compatibilité uniquement)
// Toute la logique d'affichage a été migrée vers :
// - panels/selectionPanel.js
// - panels/duplicatesPanel.js
// Ce module est conservé pour ne pas casser d'anciens imports éventuels.

"use strict";

/**
 * Ancien helper qui remontait le bloc de config utilisateur dans le DOM.
 * La nouvelle architecture crée le layout dans configuration.js,
 * donc cette fonction est désormais un no-op.
 */
export function ensureUserConfigAbove() {
  console.debug("[config.view] ensureUserConfigAbove (legacy) — no-op");
}

/**
 * Ancien rendu du panneau \"Doublons par appareil\".
 * La vue est maintenant gérée par panels/duplicatesPanel.js et
 * appelée directement depuis configuration.js (renderDuplicatesPanel).
 *
 * On garde cette fonction vide pour compat, au cas où un ancien code l'appelle encore.
 */
export function renderDuplicatesColumn(parentEl, cfg) {
  console.debug("[config.view] renderDuplicatesColumn (legacy) — remplacé par renderDuplicatesPanel", {
    hasParent: !!parentEl,
    cfgKeys: cfg ? Object.keys(cfg) : [],
  });
  // Intentionnellement aucun rendu ici.
}
