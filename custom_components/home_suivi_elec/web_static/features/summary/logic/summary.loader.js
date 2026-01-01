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
      <div class="hse-loader-container">
        <div class="hse-loader-spinner"></div>
        <div class="hse-loader-text" id="loaderStatus">
          Chargement des données...
        </div>
        <div class="hse-progress-container">
          <div class="hse-progress-bar" id="loaderProgress">
            <div class="hse-progress-fill" style="width: 0%"></div>
          </div>
          <div class="hse-progress-label" id="loaderPercentage">0%</div>
        </div>
        <div class="hse-loader-details" id="loaderDetails"></div>
      </div>
    `;

    this.progressBar = this.container.querySelector(".hse-progress-fill");
    this.statusText = document.getElementById("loaderStatus");
    this.detailsText = document.getElementById("loaderDetails");
    this.percentageText = document.getElementById("loaderPercentage");
  }

  /**
   * Met à jour la progression
   */
  updateProgress(percent, status = null, details = null) {
    if (this.progressBar) {
      this.progressBar.style.width = `${Math.min(100, Math.max(0, percent))}%`;

      // Animation de la couleur selon progression
      if (percent < 30) {
        this.progressBar.style.background =
          "linear-gradient(90deg, #0078d4, #005fa3)";
      } else if (percent < 70) {
        this.progressBar.style.background =
          "linear-gradient(90deg, #0078d4, #00bcf2)";
      } else {
        this.progressBar.style.background =
          "linear-gradient(90deg, #28a745, #20c997)";
      }
    }

    if (this.percentageText) {
      this.percentageText.textContent = `${Math.round(percent)}%`;
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
    if (this.container) {
      const loader = this.container.querySelector(".hse-loader-container");
      if (loader) {
        loader.classList.add("hse-loader-fade-out");
        setTimeout(() => loader.remove(), 300);
      }
    }
  }

  /**
   * Affiche une erreur
   */
  showError(message) {
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="hse-error-container">
        <div class="hse-error-icon">⚠️</div>
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

  let ageText = "";
  if (ageMin > 0) {
    ageText = `${ageMin}min`;
  } else {
    ageText = `${ageSec}s`;
  }

  return `
    <span class="hse-cache-badge" title="Données en cache (âge: ${ageText})">
      ⚡ ${ageText}
    </span>
  `;
}
