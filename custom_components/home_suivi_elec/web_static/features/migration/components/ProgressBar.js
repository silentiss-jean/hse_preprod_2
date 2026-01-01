// features/migration/components/ProgressBar.js
"use strict";

import { createElement } from "../../../shared/utils/dom.js";

/**
 * Barre de progression pour la création automatique de helpers.
 *
 * new ProgressBar(totalHelpers, containerElement)
 */
export class ProgressBar {
  constructor(total, container) {
    this.total = total || 0;
    this.current = 0;
    this.container = container;
    this.element = null;

    this.render();
  }

  render() {
    this.element = createElement("div", {
      className: "progress-bar-container",
    });

    // Label "x/y helpers créés"
    this.label = createElement(
      "div",
      { className: "progress-label" },
      `0/${this.total} helpers créés`
    );

    // Barre + fill
    this.bar = createElement("div", { className: "progress-bar" });
    this.fill = createElement("div", { className: "progress-fill" });
    this.fill.style.width = "0%";
    this.fill.style.transition = "width 0.3s ease";

    this.bar.appendChild(this.fill);

    // Pourcentage
    this.percentage = createElement(
      "div",
      { className: "progress-percentage" },
      "0%"
    );

    this.element.appendChild(this.label);
    this.element.appendChild(this.bar);
    this.element.appendChild(this.percentage);

    if (this.container) {
      this.container.appendChild(this.element);
    }
  }

  /**
   * Met à jour la progression.
   *
   * @param {number} current Nombre de helpers créés
   * @param {number} total   Nombre total de helpers (optionnel)
   */
  update(current, total) {
    if (typeof total === "number") {
      this.total = total;
    }
    this.current = current;

    const safeTotal = this.total > 0 ? this.total : 1;
    const percent = Math.round((this.current / safeTotal) * 100);

    this.label.textContent = `${this.current}/${this.total} helpers créés`;
    this.fill.style.width = `${percent}%`;
    this.percentage.textContent = `${percent}%`;

    // Couleur selon progression
    if (percent >= 100) {
      this.fill.style.backgroundColor = "#28a745"; // vert
    } else if (percent >= 50) {
      this.fill.style.backgroundColor = "#17a2b8"; // bleu/teal
    } else {
      this.fill.style.backgroundColor = "#667eea"; // violet/bleu
    }
  }

  /**
   * Marque la progression comme terminée.
   */
  complete() {
    this.update(this.total, this.total);
    if (this.element) {
      this.element.classList.add("complete");
    }
  }

  /**
   * Supprime la barre du DOM.
   */
  remove() {
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
  }
}
