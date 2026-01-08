"use strict";
import { renderCustomisationLayout } from "./customisation.view.js";
import { getCurrentTheme, setCurrentTheme } from "./customisation.state.js";
import { THEMES } from "./logic/themesRegistry.js";
import { renderGroupsPanel } from "./panels/groupsPanel.js";

console.log("[customisation] Module chargé");

function applyThemeClass(themeId) {
  const root = document.body;
  
  // CORRECTION : Utiliser data-theme au lieu de classes
  if (themeId) {
    root.setAttribute('data-theme', themeId);
    console.log("[customisation] Thème appliqué via data-theme:", themeId);
  } else {
    root.removeAttribute('data-theme');
  }
}

export async function loadCustomisation() {
  console.log("[customisation] loadCustomisation appelé");
  
  const container = document.getElementById("customisation");
  if (!container) {
    console.error("[customisation] Container #customisation introuvable");
    return;
  }

  container.innerHTML = renderCustomisationLayout();
  console.log("[customisation] Layout injecté");

  const selectEl = container.querySelector("#hse-theme-select");
  if (!selectEl) {
    console.error("[customisation] Select de thème introuvable");
    return;
  }

  // Thème courant stocké
  const storedThemeId = getCurrentTheme();
  const fallbackThemeId = storedThemeId || (THEMES.find((t) => t.default) || THEMES[0]).id;
  
  selectEl.value = fallbackThemeId;
  applyThemeClass(fallbackThemeId);

  // Réagir aux changements dans le dropdown
  selectEl.addEventListener("change", (e) => {
    const newThemeId = e.target.value;
    setCurrentTheme(newThemeId);
    applyThemeClass(newThemeId);
    console.log("[customisation] Thème appliqué via select:", newThemeId);
  });

  // CORRECTION : Ajouter l'écouteur pour les boutons "Appliquer"
  container.addEventListener("click", (e) => {
    const applyBtn = e.target.closest(".apply-theme-btn");
    if (applyBtn) {
      const newThemeId = applyBtn.dataset.theme;
      if (newThemeId) {
        selectEl.value = newThemeId;
        setCurrentTheme(newThemeId);
        applyThemeClass(newThemeId);
        console.log("[customisation] Thème appliqué via bouton:", newThemeId);
      }
    }
  });

  // Regroupement des capteurs
  const groupsContainer = container.querySelector("#hse-groups-panel");
  if (groupsContainer) {
    await renderGroupsPanel(groupsContainer);
  } else {
    console.error("[customisation] #hse-groups-panel introuvable");
  }
}

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
