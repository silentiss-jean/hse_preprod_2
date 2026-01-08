"use strict";

/**
 * Module Customisation
 */

import { renderCustomisationLayout } from "./customisation.view.js";
import { getCurrentTheme, setCurrentTheme } from "./customisation.state.js";
import { THEMES } from "./logic/themesRegistry.js";
import { renderGroupsPanel } from "./panels/groupsPanel.js";

console.log("[customisation] Module chargé");

function applyThemeClass(themeId) {
  const root = document.body;

  // Nettoyer toutes les classes de thème
  THEMES.forEach((t) => root.classList.remove(t.id));

  // Appliquer le thème choisi
  if (themeId) {
    root.classList.add(themeId);
  }
}

/**
 * Point d'entrée principal
 */
export async function loadCustomisation() {
  console.log("[customisation] loadCustomisation appelé");

  const container = document.getElementById("customisation");
  if (!container) {
    console.error("[customisation] Container #customisation introuvable");
    return;
  }

  // Injecter le layout HTML
  container.innerHTML = renderCustomisationLayout();
  console.log("[customisation] Layout injecté");

  const selectEl = container.querySelector("#hse-theme-select");
  if (!selectEl) {
    console.error("[customisation] Select de thème introuvable");
    return;
  }

  // Thème courant stocké (id de la classe, ex: "hse_dark")
  const storedThemeId = getCurrentTheme(); // doit retourner une string type "hse_dark"
  const fallbackThemeId =
    storedThemeId || (THEMES.find((t) => t.default) || THEMES[0]).id;

  selectEl.value = fallbackThemeId;
  applyThemeClass(fallbackThemeId);

  // Réagir aux changements utilisateur
  selectEl.addEventListener("change", (e) => {
    const newThemeId = e.target.value;
    setCurrentTheme(newThemeId); // sauvegarde l'id dans localStorage
    applyThemeClass(newThemeId);
    console.log("[customisation] Thème appliqué:", newThemeId);
  });

  // Réagir aux clics sur les boutons "Appliquer" des cartes de prévisualisation
  container.addEventListener("click", (e) => {
    const applyBtn = e.target.closest(".apply-theme-btn");
    if (applyBtn) {
      const newThemeId = applyBtn.dataset.theme;
      if (newThemeId) {
        // Mettre à jour le select
        selectEl.value = newThemeId;
        // Sauvegarder et appliquer
        setCurrentTheme(newThemeId);
        applyThemeClass(newThemeId);
        console.log("[customisation] Thème appliqué via bouton:", newThemeId);
      }
    }
  });

  // === Regroupement des capteurs ===
  const groupsContainer = container.querySelector("#hse-groups-panel");
  if (groupsContainer) {
    await renderGroupsPanel(groupsContainer);
  } else {
    console.error("[customisation] #hse-groups-panel introuvable");
  }
}
