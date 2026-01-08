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

    // Thème courant stocké
    const storedThemeId = getCurrentTheme();
    const fallbackThemeId = storedThemeId || (THEMES.find((t) => t.default) || THEMES[0]).id;
    
    applyThemeClass(fallbackThemeId);

    // NOUVELLE GESTION : Clic direct sur les cartes compactes
    container.addEventListener("click", (e) => {
        const themeCard = e.target.closest(".theme-compact-card");
        if (themeCard) {
            const newThemeId = themeCard.dataset.theme;
            if (newThemeId) {
                // Retirer la classe active de toutes les cartes
                document.querySelectorAll(".theme-compact-card").forEach(card => {
                    card.classList.remove("is-active");
                });
                
                // Ajouter la classe active à la carte cliquée
                themeCard.classList.add("is-active");
                
                // Appliquer le thème
                setCurrentTheme(newThemeId);
                applyThemeClass(newThemeId);
                console.log("[customisation] Thème appliqué via carte compacte:", newThemeId);
            }
        }
    });

    // Marquer le thème actif au chargement
    const activeCard = container.querySelector(`[data-theme="${fallbackThemeId}"]`);
    if (activeCard) {
        activeCard.classList.add("is-active");
    }

    // Regroupement des capteurs
    const groupsContainer = container.querySelector("#hse-groups-panel");
    if (groupsContainer) {
        await renderGroupsPanel(groupsContainer);
    } else {
        console.error("[customisation] #hse-groups-panel introuvable");
    }
}
