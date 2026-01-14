"use strict";

/**
 * Gestionnaire d'état de chargement avec progression
 */

export class LoadingManager {
  constructor() {
    this.container = null;
    this.progressBar = null;
    this.statusText = null;
    this.detailsText = null;
    this.percentageText = null;
  }

  /**
   * Affiche l'état de chargement initial
   */
  show(containerId = "summaryContent") {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="hse-loader-container" role="status" aria-live="polite">
        <div class="hse-loader-spinner" aria-hidden="true"></div>

        <div class="hse-loader-text" id="loaderStatus">
          Chargement des données...
        </div>

        <div class="hse-progress-container">
          <div class="hse-progress-bar" id="loaderProgress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <div class="hse-progress-fill" style="width: 0%"></div>
          </div>
          <div class="hse-progress-label" id="loaderPercentage">0%</div>
        </div>

        <div class="hse-loader-details" id="loaderDetails"></div>
      </div>
    `;

    // Scope au container (évite collisions si plusieurs écrans réutilisent ces ids)
    this.progressBar = this.container.querySelector(".hse-progress-fill");
    this.statusText = this.container.querySelector("#loaderStatus");
    this.detailsText = this.container.querySelector("#loaderDetails");
    this.percentageText = this.container.querySelector("#loaderPercentage");
  }

  /**
   * Met à jour la progression
   */
  updateProgress(percent, status = null, details = null) {
    const p = Math.min(100, Math.max(0, Number(percent) || 0));

    if (this.progressBar) {
      this.progressBar.style.width = `${p}%`;

      // Couleur pilotée par tokens (pas de hardcode hex)
      // low -> info, mid -> primary, high -> success
      const gradientVar =
        p < 30 ? "--hse-gradient-info" : p < 70 ? "--hse-gradient-primary" : "--hse-gradient-success";

      this.progressBar.style.background = `var(${gradientVar})`;
    }

    if (this.container) {
      const bar = this.container.querySelector("#loaderProgress");
      if (bar) bar.setAttribute("aria-valuenow", String(Math.round(p)));
    }

    if (this.percentageText) {
      this.percentageText.textContent = `${Math.round(p)}%`;
    }

    if (status && this.statusText) {
      this.statusText.textContent = status;
    }

    if (details && this.detailsText) {
      this.detailsText.innerHTML = details;
    }
  }

  /**
   * Masque l'état de chargement avec animation
   */
  hide() {
    if (!this.container) return;

    const loader = this.container.querySelector(".hse-loader-container");
    if (!loader) return;

    loader.classList.add("hse-loader-fade-out");
    setTimeout(() => loader.remove(), 300);
  }

  /**
   * Affiche une erreur
   */
  showError(message) {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="hse-error-container">
        <div class="hse-error-icon" aria-hidden="true">⚠️</div>
        <div class="hse-error-message">${message}</div>
        <button class="btn-secondary hse-error-retry" onclick="window.location.reload()">
          🔄 Recharger
        </button>
      </div>
    `;
  }
}

/**
 * Affiche un badge "from cache" sur les valeurs
 */
export function showCacheBadge(fromCache, age = 0) {
  if (!fromCache) return "";

  const ageMin = Math.floor(age / 60);
  const ageSec = Math.floor(age % 60);

  const ageText = ageMin > 0 ? `${ageMin}min` : `${ageSec}s`;

  return `
    <span class="hse-cache-badge" title="Données en cache (âge: ${ageText})">
      ⚡ ${ageText}
    </span>
  `;
}
