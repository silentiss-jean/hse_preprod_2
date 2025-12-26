"use strict";

/**
 * Crée un header avec flèche de toggle pour plier/déplier un panel.
 * L'état ouvert/fermé est géré via deux callbacks getFold/setFold.
 *
 * @param {function(string, string): boolean} getFold - retourne true si ouvert
 * @param {function(string, string, boolean): void} setFold - enregistre l'état
 * @param {string} storageKeyOrIntegration - clé principale (integration ou section)
 * @param {string} columnKey - clé secondaire (colonne/section)
 * @param {string} titleHTML - HTML du titre
 * @param {HTMLElement} panelEl - élément à plier/déplier
 * @returns {HTMLElement} header DOM
 */
export function makeToggleHeader(getFold, setFold, storageKeyOrIntegration, columnKey, titleHTML, panelEl) {
  const header = document.createElement("div");
  header.className = "duplicate-header";
  header.style.display = "flex";
  header.style.alignItems = "center";
  header.style.justifyContent = "space-between";
  header.style.gap = "8px";

  const left = document.createElement("div");
  left.className = "dup-title";
  left.style.display = "flex";
  left.style.alignItems = "center";

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "toggle-btn";
  btn.style = "margin-right:8px; border:none; background:none; cursor:pointer; font-size:14px;";

  const opened = !!getFold(storageKeyOrIntegration, columnKey);
  btn.textContent = opened ? "▼" : "▶";
  panelEl.style.display = opened ? "block" : "none";

  btn.onclick = () => {
    const isOpen = panelEl.style.display !== "none";
    panelEl.style.display = isOpen ? "none" : "block";
    btn.textContent = isOpen ? "▶" : "▼";
    setFold(storageKeyOrIntegration, columnKey, !isOpen);
  };

  left.appendChild(btn);
  const span = document.createElement("span");
  span.innerHTML = titleHTML;
  left.appendChild(span);

  header.appendChild(left);
  return header;
}

